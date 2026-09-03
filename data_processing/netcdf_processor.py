import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import xarray as xr

logger = logging.getLogger(__name__)

# ─── Variable name mappings ────────────────────────────────────────────────────

VARIABLE_MAPPINGS = {
    "temperature": [
        "TEMP", "TEMP_ADJUSTED", "temp_adjusted", "temp", "temperature",
        "T", "sea_water_temperature", "TEMPERATURE",
    ],
    "pressure": [
        "PRES", "PRES_ADJUSTED", "pres_adjusted", "pres", "pressure",
        "P", "sea_water_pressure", "PRESSURE",
    ],
    "salinity": [
        "PSAL", "PSAL_ADJUSTED", "psal_adjusted", "psal", "salinity",
        "S", "sea_water_salinity", "SALINITY",
    ],
    "oxygen": [
        "DOXY", "DOXY_ADJUSTED", "doxy_adjusted", "doxy", "oxygen",
        "o2", "O2", "dissolved_oxygen", "OXYGEN",
    ],
    "latitude": ["LATITUDE", "latitude", "lat", "LAT", "y", "Y"],
    "longitude": ["LONGITUDE", "longitude", "lon", "LON", "x", "X"],
    "time": ["JULD", "time", "TIME", "t", "T", "date", "DATE"],
    "depth": ["DEPTH", "depth", "z", "Z", "level", "LEVEL"],
    "nitrate": ["NITRATE", "nitrate", "NO3", "no3"],
    "ph": ["PH_IN_SITU_TOTAL", "ph", "pH", "PH"],
    "chlorophyll": ["CHLA", "chla", "chlorophyll", "CHL", "chl"],
    "float_id": [
        "PLATFORM_NUMBER", "platform_number", "float_id", "FLOAT_ID",
        "WMO_ID", "wmo_id",
    ],
    "cycle_number": ["CYCLE_NUMBER", "cycle_number", "cycle", "CYCLE"],
    "data_mode": ["DATA_MODE", "data_mode"],
}


class NetCDFProcessor:
    """Processes NetCDF files (ARGO and generic) into structured profile dicts."""

    def detect_file_type(self, ds: xr.Dataset) -> str:
        """Detect whether file is argo, oceanographic, or generic."""
        argo_vars = {"PRES", "TEMP", "PSAL"}
        found = sum(1 for v in argo_vars if v in ds.data_vars or v in ds.coords)
        if found >= 2:
            return "argo"
        ocean_keywords = {
            "temperature", "salinity", "pressure", "ocean", "sea_water",
            "LATITUDE", "LONGITUDE", "depth",
        }
        all_names = set(ds.data_vars) | set(ds.coords) | set(ds.attrs.get("title", "").split())
        if ocean_keywords & {k.lower() for k in all_names}:
            return "oceanographic"
        return "generic"

    def process_file(self, filepath: str) -> list[dict]:
        """Open a NetCDF file and extract all profiles."""
        try:
            ds = xr.open_dataset(filepath, decode_times=False, mask_and_scale=True)
        except Exception:
            try:
                ds = xr.open_dataset(filepath, engine="h5netcdf", decode_times=False)
            except Exception:
                logger.exception("Failed to open file: %s", filepath)
                return []

        file_type = self.detect_file_type(ds)
        logger.info("Processing %s as type=%s", Path(filepath).name, file_type)

        try:
            if file_type == "argo":
                profiles = self.extract_argo_profiles(ds, source_file=Path(filepath).name)
            else:
                profiles = self.extract_generic_profiles(ds, source_file=Path(filepath).name)
        except Exception:
            logger.exception("Failed to extract profiles from %s", filepath)
            profiles = []
        finally:
            ds.close()

        logger.info("Extracted %d profiles from %s", len(profiles), Path(filepath).name)
        return profiles

    def extract_argo_profiles(self, ds: xr.Dataset, source_file: str = "") -> list[dict]:
        """Extract profiles from ARGO NetCDF file. Handles N_PROF dimension."""
        profiles = []

        # Determine number of profiles (N_PROF dimension or single profile)
        n_prof = 1
        if "N_PROF" in ds.dims:
            n_prof = ds.dims["N_PROF"]
        elif "n_prof" in ds.dims:
            n_prof = ds.dims["n_prof"]

        for i in range(n_prof):
            try:
                profile = self._extract_single_argo_profile(ds, i, source_file)
                if profile:
                    profiles.append(profile)
            except Exception:
                logger.exception("Failed to extract ARGO profile index %d", i)

        return profiles

    def _extract_single_argo_profile(
        self, ds: xr.Dataset, prof_idx: int, source_file: str
    ) -> dict | None:
        """Extract one profile from a potentially multi-profile ARGO dataset."""

        def get_scalar(var_names):
            for name in var_names:
                if name in ds.data_vars or name in ds.coords:
                    arr = ds[name]
                    if "N_PROF" in arr.dims or "n_prof" in arr.dims:
                        val = arr.values[prof_idx]
                    else:
                        val = arr.values[0] if arr.values.ndim > 0 else arr.values
                    if hasattr(val, "__iter__") and not isinstance(val, (str, bytes)):
                        val = val[0] if len(val) > 0 else None
                    if val is not None and not (isinstance(val, float) and np.isnan(val)):
                        return val
            return None

        def get_profile_array(var_names):
            """Get 1-D array for one profile across depth levels."""
            for name in var_names:
                if name in ds.data_vars or name in ds.coords:
                    arr = ds[name]
                    vals = arr.values
                    if vals.ndim == 2:
                        return vals[prof_idx]
                    elif vals.ndim == 1:
                        return vals
            return None

        # Extract metadata
        lat = get_scalar(VARIABLE_MAPPINGS["latitude"])
        lon = get_scalar(VARIABLE_MAPPINGS["longitude"])
        if lat is None or lon is None:
            logger.debug("Skipping profile %d: missing lat/lon", prof_idx)
            return None

        lat = float(lat)
        lon = float(lon)

        # Time handling
        time_val = get_scalar(VARIABLE_MAPPINGS["time"])
        measurement_date = self._parse_time(time_val, ds)

        # Float ID
        float_id_raw = get_scalar(VARIABLE_MAPPINGS["float_id"])
        if float_id_raw is None:
            float_id = f"UNKNOWN_{prof_idx}"
        elif isinstance(float_id_raw, (bytes, bytearray)):
            float_id = float_id_raw.decode("utf-8", errors="ignore").strip()
        elif hasattr(float_id_raw, "tobytes"):
            # char arrays in ARGO
            float_id = b"".join(float_id_raw).decode("utf-8", errors="ignore").strip()
        else:
            float_id = str(float_id_raw).strip()

        # Cycle number
        cycle_raw = get_scalar(VARIABLE_MAPPINGS["cycle_number"])
        cycle_number = int(cycle_raw) if cycle_raw is not None else None

        # Data mode
        data_mode_raw = get_scalar(VARIABLE_MAPPINGS["data_mode"])
        if isinstance(data_mode_raw, (bytes, bytearray)):
            data_mode = data_mode_raw.decode("utf-8", errors="ignore").strip()
        else:
            data_mode = str(data_mode_raw).strip() if data_mode_raw else "R"

        # Build measurements array
        pressure_arr = get_profile_array(VARIABLE_MAPPINGS["pressure"])
        temp_arr = get_profile_array(VARIABLE_MAPPINGS["temperature"])
        sal_arr = get_profile_array(VARIABLE_MAPPINGS["salinity"])
        depth_arr = get_profile_array(VARIABLE_MAPPINGS["depth"])
        oxy_arr = get_profile_array(VARIABLE_MAPPINGS["oxygen"])
        nit_arr = get_profile_array(VARIABLE_MAPPINGS["nitrate"])
        ph_arr = get_profile_array(VARIABLE_MAPPINGS["ph"])
        chl_arr = get_profile_array(VARIABLE_MAPPINGS["chlorophyll"])

        if pressure_arr is None and depth_arr is None:
            logger.debug("Skipping profile %d: no pressure or depth data", prof_idx)
            return None

        n_levels = (
            len(pressure_arr)
            if pressure_arr is not None
            else len(depth_arr)
        )

        measurements = []
        for j in range(n_levels):
            meas = {}
            if pressure_arr is not None:
                p = self._safe_float(pressure_arr[j])
                if p is not None:
                    meas["pressure"] = p
            if depth_arr is not None:
                d = self._safe_float(depth_arr[j])
                if d is not None:
                    meas["depth"] = d
            elif "pressure" in meas:
                meas["depth"] = meas["pressure"]  # approximate
            if temp_arr is not None:
                t = self._safe_float(temp_arr[j])
                if t is not None:
                    meas["temperature"] = t
            if sal_arr is not None:
                s = self._safe_float(sal_arr[j])
                if s is not None:
                    meas["salinity"] = s
            if oxy_arr is not None:
                o = self._safe_float(oxy_arr[j])
                if o is not None:
                    meas["oxygen"] = o
            if nit_arr is not None:
                n = self._safe_float(nit_arr[j])
                if n is not None:
                    meas["nitrate"] = n
            if ph_arr is not None:
                ph = self._safe_float(ph_arr[j])
                if ph is not None:
                    meas["ph"] = ph
            if chl_arr is not None:
                c = self._safe_float(chl_arr[j])
                if c is not None:
                    meas["chlorophyll"] = c

            if meas:
                measurements.append(meas)

        if not measurements:
            return None

        metadata = {
            "float_id": float_id,
            "latitude": lat,
            "longitude": lon,
            "measurement_date": measurement_date or datetime.now(timezone.utc).replace(tzinfo=None),
            "cycle_number": cycle_number,
            "data_mode": data_mode,
            "source_file": source_file,
        }
        return {"metadata": metadata, "measurements": measurements}

    def extract_generic_profiles(self, ds: xr.Dataset, source_file: str = "") -> list[dict]:
        """More flexible extraction for non-ARGO files."""
        lat = self.map_variable(ds, "latitude")
        lon = self.map_variable(ds, "longitude")
        time_arr = self.map_variable(ds, "time")
        pressure_arr = self.map_variable(ds, "pressure")
        depth_arr = self.map_variable(ds, "depth")
        temp_arr = self.map_variable(ds, "temperature")
        sal_arr = self.map_variable(ds, "salinity")

        if lat is None or lon is None:
            logger.warning("Generic file missing lat/lon, skipping")
            return []

        lat_val = float(lat.flat[0]) if hasattr(lat, "flat") else float(lat)
        lon_val = float(lon.flat[0]) if hasattr(lon, "flat") else float(lon)

        time_val = None
        if time_arr is not None:
            raw = time_arr.flat[0] if hasattr(time_arr, "flat") else time_arr
            time_val = self._parse_time(raw, ds)

        ref_arr = pressure_arr if pressure_arr is not None else depth_arr
        if ref_arr is None:
            return []

        n_levels = len(ref_arr.flat) if hasattr(ref_arr, "flat") else 1
        measurements = []
        for j in range(n_levels):
            meas = {}
            if pressure_arr is not None:
                p = self._safe_float(pressure_arr.flat[j])
                if p is not None:
                    meas["pressure"] = p
            if depth_arr is not None:
                d = self._safe_float(depth_arr.flat[j])
                if d is not None:
                    meas["depth"] = d
            if temp_arr is not None and j < len(temp_arr.flat):
                t = self._safe_float(temp_arr.flat[j])
                if t is not None:
                    meas["temperature"] = t
            if sal_arr is not None and j < len(sal_arr.flat):
                s = self._safe_float(sal_arr.flat[j])
                if s is not None:
                    meas["salinity"] = s
            if meas:
                measurements.append(meas)

        if not measurements:
            return []

        float_id = self.generate_profile_id(
            "GENERIC",
            0,
            (time_val or datetime.now(timezone.utc).replace(tzinfo=None)).strftime("%Y%m%d"),
        )
        metadata = {
            "float_id": float_id,
            "latitude": lat_val,
            "longitude": lon_val,
            "measurement_date": time_val or datetime.now(timezone.utc).replace(tzinfo=None),
            "cycle_number": None,
            "data_mode": "R",
            "source_file": source_file,
        }
        return [{"metadata": metadata, "measurements": measurements}]

    def map_variable(self, ds: xr.Dataset, standard_name: str):
        """Try each variant name for standard_name; return array of first found."""
        for name in VARIABLE_MAPPINGS.get(standard_name, []):
            if name in ds.data_vars:
                return ds[name].values
            if name in ds.coords:
                return ds.coords[name].values
        return None

    @staticmethod
    def generate_profile_id(float_id: str, cycle: int | None, date: str) -> str:
        """Create a short hash-based unique identifier for duplicate detection."""
        key = f"{float_id}_{cycle}_{date}"
        return hashlib.md5(key.encode()).hexdigest()[:12]

    @staticmethod
    def _safe_float(val) -> float | None:
        """Convert a value to float, returning None for missing/NaN."""
        if val is None:
            return None
        try:
            f = float(val)
            if np.isnan(f) or np.isinf(f):
                return None
            return f
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_time(time_val, ds: xr.Dataset) -> datetime | None:
        """Parse ARGO Julian day or numeric time to datetime."""
        if time_val is None:
            return None
        try:
            # Try cftime / xarray decode
            import cftime

            t = float(time_val)
            # ARGO Julian days: reference 1950-01-01
            if 10000 < t < 100000:
                from datetime import timedelta

                ref = datetime(1950, 1, 1)
                return ref + timedelta(days=t)
            # Unix timestamp range
            if 0 < t < 4e9:
                return datetime.utcfromtimestamp(t)
        except Exception:
            pass
        return None
