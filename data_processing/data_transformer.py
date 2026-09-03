import logging

import numpy as np
import pandas as pd

from database.schema import PARAMETER_RANGES

logger = logging.getLogger(__name__)

MEASUREMENT_COLS = [
    "temperature", "salinity", "pressure", "depth",
    "oxygen", "nitrate", "ph", "chlorophyll",
    "potential_temperature", "density", "mixed_layer_depth",
]


class DataTransformer:
    """Cleans, validates, and enriches measurement DataFrames."""

    def clean_measurements(self, df: pd.DataFrame) -> pd.DataFrame:
        """Drop all-null rows, range-validate, remove duplicate depths, sort."""
        if df.empty:
            return df

        # Drop rows where ALL measurement columns are null
        meas_present = [c for c in MEASUREMENT_COLS if c in df.columns]
        if meas_present:
            df = df.dropna(subset=meas_present, how="all")

        # Apply PARAMETER_RANGES: set out-of-range values to NaN
        for param, (low, high) in PARAMETER_RANGES.items():
            if param in df.columns:
                mask = df[param].notna() & ~df[param].between(low, high)
                if mask.any():
                    df.loc[mask, param] = np.nan
                    if "quality_flag" in df.columns:
                        df.loc[mask, "quality_flag"] = 4
                    logger.debug(
                        "Set %d out-of-range %s values to NaN", mask.sum(), param
                    )

        # Remove duplicate depths (keep first occurrence)
        depth_col = "depth" if "depth" in df.columns else "pressure"
        if depth_col in df.columns:
            df = df.drop_duplicates(subset=[depth_col], keep="first")
            df = df.sort_values(depth_col).reset_index(drop=True)

        return df

    def interpolate_missing_depth(self, df: pd.DataFrame) -> pd.DataFrame:
        """If depth is missing but pressure exists, approximate depth = pressure."""
        if "depth" not in df.columns or df["depth"].isna().all():
            if "pressure" in df.columns:
                df = df.copy()
                df["depth"] = df["pressure"]
                logger.debug("Interpolated depth from pressure")
        return df

    def calculate_derived_parameters(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute potential_temperature, density, and mixed_layer_depth."""
        if df.empty:
            return df
        df = df.copy()

        # Potential temperature
        if "temperature" in df.columns and "pressure" in df.columns:
            df["potential_temperature"] = df["temperature"] - 0.1 * (
                df["pressure"] / 1000.0
            )

        # Density (simplified linear approximation)
        if "salinity" in df.columns and "temperature" in df.columns:
            df["density"] = (
                1000.0
                + 0.8 * df["salinity"].fillna(35.0)
                - 0.2 * df["temperature"].fillna(20.0)
            )

        # Mixed layer depth: depth where T drops >0.2°C below surface mean (top 10m)
        if "temperature" in df.columns and "depth" in df.columns:
            df["mixed_layer_depth"] = np.nan
            try:
                surface_mask = df["depth"] <= 10.0
                if surface_mask.any():
                    surface_temp = df.loc[surface_mask, "temperature"].mean()
                    if not np.isnan(surface_temp):
                        below_mld = df["temperature"] < (surface_temp - 0.2)
                        if below_mld.any():
                            mld = df.loc[below_mld, "depth"].min()
                        else:
                            mld = df["depth"].max()
                        df["mixed_layer_depth"] = mld
            except Exception:
                logger.debug("Could not compute mixed_layer_depth")

        return df

    def create_profile_summary(self, df: pd.DataFrame, metadata: dict) -> dict:
        """Create natural-language summary_text for ChromaDB plus a stats dict."""
        float_id = metadata.get("float_id", "UNKNOWN")
        lat = metadata.get("latitude", 0.0)
        lon = metadata.get("longitude", 0.0)
        date = metadata.get("measurement_date", "")
        if hasattr(date, "strftime"):
            date_str = date.strftime("%d %b %Y")
        else:
            date_str = str(date)[:10]

        lat_dir = "N" if lat >= 0 else "S"
        lon_dir = "E" if lon >= 0 else "W"

        parts = [
            f"ARGO float {float_id} at {abs(lat):.2f}°{lat_dir} {abs(lon):.2f}°{lon_dir} "
            f"on {date_str}."
        ]

        stats = {}

        # Depth range
        depth_col = "depth" if "depth" in df.columns else "pressure"
        if depth_col in df.columns and df[depth_col].notna().any():
            dmin = df[depth_col].min()
            dmax = df[depth_col].max()
            parts.append(f"Depth range {dmin:.0f}m to {dmax:.0f}m.")
            stats["depth"] = {"min": float(dmin), "max": float(dmax)}

        # Parameters
        param_labels = {
            "temperature": ("Temperature", "°C"),
            "salinity": ("Salinity", "PSU"),
            "oxygen": ("Dissolved oxygen", "µmol/kg"),
            "nitrate": ("Nitrate", "µmol/kg"),
            "ph": ("pH", ""),
            "chlorophyll": ("Chlorophyll-a", "mg/m³"),
        }
        for param, (label, unit) in param_labels.items():
            if param in df.columns and df[param].notna().any():
                mn = df[param].min()
                mx = df[param].max()
                mean = df[param].mean()
                unit_str = f" {unit}" if unit else ""
                parts.append(f"{label} {mn:.2f} to {mx:.2f}{unit_str}.")
                stats[param] = {"min": float(mn), "max": float(mx), "mean": float(mean)}

        # MLD
        if "mixed_layer_depth" in df.columns and df["mixed_layer_depth"].notna().any():
            mld = df["mixed_layer_depth"].iloc[0]
            if not np.isnan(mld):
                parts.append(f"Mixed layer depth {mld:.0f}m.")
                stats["mixed_layer_depth"] = float(mld)

        summary_text = " ".join(parts)
        return {
            "summary_text": summary_text,
            "statistics": stats,
            "float_id": float_id,
            "latitude": lat,
            "longitude": lon,
            "measurement_date": metadata.get("measurement_date"),
        }

    def detect_anomalies(self, df: pd.DataFrame, parameter: str) -> pd.DataFrame:
        """Flag anomalies using Z-score and IQR methods."""
        if df.empty or parameter not in df.columns:
            return df
        df = df.copy()
        col = df[parameter].dropna()
        if len(col) < 4:
            return df

        # Z-score
        mean = col.mean()
        std = col.std()
        if std > 0:
            z_scores = (df[parameter] - mean) / std
            z_flag = z_scores.abs() > 3
        else:
            z_flag = pd.Series(False, index=df.index)

        # IQR
        q1 = col.quantile(0.25)
        q3 = col.quantile(0.75)
        iqr = q3 - q1
        iqr_flag = (df[parameter] < (q1 - 1.5 * iqr)) | (
            df[parameter] > (q3 + 1.5 * iqr)
        )

        df["anomaly_flag"] = z_flag | iqr_flag
        if std > 0:
            df["z_score"] = z_scores
        else:
            df["z_score"] = 0.0

        n_anomalies = df["anomaly_flag"].sum()
        if n_anomalies > 0:
            logger.debug(
                "Detected %d anomalies in parameter '%s'", n_anomalies, parameter
            )
        return df
