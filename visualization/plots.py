import logging

import pandas as pd
import plotly.graph_objects as go

logger = logging.getLogger(__name__)

# ─── Shared dark theme ─────────────────────────────────────────────────────────

DARK_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#8BAABF", family="Inter, sans-serif", size=12),
    title=dict(font=dict(color="#F0F8FF", size=16)),
    xaxis=dict(
        gridcolor="#1A3A5C",
        linecolor="#1A3A5C",
        tickcolor="#8BAABF",
        showgrid=True,
    ),
    yaxis=dict(
        gridcolor="#1A3A5C",
        linecolor="#1A3A5C",
        tickcolor="#8BAABF",
        showgrid=True,
    ),
    legend=dict(
        bgcolor="rgba(10,31,58,0.8)",
        bordercolor="#1A3A5C",
        borderwidth=1,
        font=dict(color="#8BAABF"),
    ),
    margin=dict(l=60, r=20, t=60, b=50),
    hovermode="closest",
)

COLORS = {
    "primary": "#00C6FF",
    "secondary": "#F5A623",
    "success": "#00E676",
    "error": "#FF5252",
    "purple": "#B388FF",
    "muted": "#8BAABF",
}

PARAM_LABELS = {
    "temperature": "Temperature (°C)",
    "salinity": "Salinity (PSU)",
    "pressure": "Pressure (dbar)",
    "depth": "Depth (m)",
    "oxygen": "Dissolved Oxygen (µmol/kg)",
    "nitrate": "Nitrate (µmol/kg)",
    "ph": "pH",
    "chlorophyll": "Chlorophyll-a (mg/m³)",
    "density": "Density (kg/m³)",
    "potential_temperature": "Potential Temperature (°C)",
    "mixed_layer_depth": "Mixed Layer Depth (m)",
}


class OceanographicPlots:
    """Collection of Plotly dark-theme oceanographic visualizations."""

    def _apply_layout(self, fig: go.Figure, **extra) -> go.Figure:
        layout = {**DARK_LAYOUT, **extra}
        fig.update_layout(**layout)
        return fig

    def depth_profile(
        self,
        measurements_df: pd.DataFrame,
        parameter: str,
        title: str | None = None,
    ) -> go.Figure:
        """Parameter vs depth (inverted Y axis — deep at bottom)."""
        fig = go.Figure()
        if measurements_df.empty or parameter not in measurements_df.columns:
            return self._empty_fig(f"No data for {parameter}")

        depth_col = "depth" if "depth" in measurements_df.columns else "pressure"
        df = measurements_df.dropna(subset=[parameter, depth_col]).sort_values(depth_col)

        fig.add_trace(
            go.Scatter(
                x=df[parameter],
                y=df[depth_col],
                mode="lines+markers",
                line=dict(color=COLORS["primary"], width=2),
                marker=dict(color=COLORS["primary"], size=4),
                name=parameter,
                hovertemplate=f"{PARAM_LABELS.get(parameter, parameter)}: %{{x:.3f}}<br>Depth: %{{y:.1f}}m<extra></extra>",
            )
        )

        self._apply_layout(
            fig,
            title=title or f"Depth Profile — {PARAM_LABELS.get(parameter, parameter)}",
            xaxis_title=PARAM_LABELS.get(parameter, parameter),
            yaxis=dict(
                autorange="reversed",
                title="Depth (m)",
                gridcolor="#1A3A5C",
                linecolor="#1A3A5C",
                tickcolor="#8BAABF",
            ),
        )
        return fig

    def temperature_salinity(self, measurements_df: pd.DataFrame) -> go.Figure:
        """Classic T-S diagram colored by depth."""
        fig = go.Figure()
        if measurements_df.empty:
            return self._empty_fig("No data")

        required = {"temperature", "salinity"}
        if not required.issubset(measurements_df.columns):
            return self._empty_fig("Missing temperature or salinity")

        depth_col = "depth" if "depth" in measurements_df.columns else "pressure"
        df = measurements_df.dropna(subset=["temperature", "salinity"])

        scatter = go.Scatter(
            x=df["salinity"],
            y=df["temperature"],
            mode="markers",
            marker=dict(
                color=df[depth_col] if depth_col in df.columns else COLORS["primary"],
                colorscale="Viridis_r",
                colorbar=dict(
                    title=dict(text="Depth (m)", font=dict(color="#8BAABF")),
                    tickfont=dict(color="#8BAABF"),
                ),
                size=5,
                opacity=0.8,
            ),
            name="T-S",
            hovertemplate="Salinity: %{x:.3f} PSU<br>Temperature: %{y:.2f}°C<extra></extra>",
        )
        fig.add_trace(scatter)
        self._apply_layout(
            fig,
            title="Temperature-Salinity Diagram",
            xaxis_title="Salinity (PSU)",
            yaxis_title="Temperature (°C)",
        )
        return fig

    def time_series(
        self,
        profiles_df: pd.DataFrame,
        measurements_df: pd.DataFrame,
        parameter: str,
    ) -> go.Figure:
        """Time series of parameter means per profile, one line per float."""
        fig = go.Figure()
        if profiles_df.empty or measurements_df.empty:
            return self._empty_fig("No data")
        if parameter not in measurements_df.columns:
            return self._empty_fig(f"No data for {parameter}")

        palette = [
            COLORS["primary"], COLORS["secondary"], COLORS["success"],
            COLORS["purple"], COLORS["error"], "#FF9800", "#E040FB", "#00BCD4",
        ]

        float_ids = profiles_df["float_id"].unique() if "float_id" in profiles_df.columns else []
        for i, fid in enumerate(float_ids):
            float_profiles = profiles_df[profiles_df["float_id"] == fid]
            pids = float_profiles["id"].tolist()
            meas = measurements_df[measurements_df["profile_id"].isin(pids)]
            if meas.empty:
                continue
            grouped = meas.groupby("profile_id")[parameter].mean().reset_index()
            merged = grouped.merge(
                float_profiles[["id", "measurement_date"]], left_on="profile_id", right_on="id"
            ).sort_values("measurement_date")

            fig.add_trace(
                go.Scatter(
                    x=merged["measurement_date"],
                    y=merged[parameter],
                    mode="lines+markers",
                    name=f"Float {fid}",
                    line=dict(color=palette[i % len(palette)], width=2),
                    marker=dict(size=6),
                    hovertemplate=f"Float {fid}<br>Date: %{{x}}<br>{PARAM_LABELS.get(parameter, parameter)}: %{{y:.3f}}<extra></extra>",
                )
            )

        self._apply_layout(
            fig,
            title=f"Time Series — {PARAM_LABELS.get(parameter, parameter)}",
            xaxis_title="Date",
            yaxis_title=PARAM_LABELS.get(parameter, parameter),
        )
        return fig

    def parameter_comparison(
        self,
        measurements_df: pd.DataFrame,
        param1: str,
        param2: str,
    ) -> go.Figure:
        """Scatter plot of param1 vs param2 colored by depth."""
        fig = go.Figure()
        if measurements_df.empty:
            return self._empty_fig("No data")
        required = {param1, param2}
        if not required.issubset(measurements_df.columns):
            return self._empty_fig(f"Missing {param1} or {param2}")

        depth_col = "depth" if "depth" in measurements_df.columns else "pressure"
        df = measurements_df.dropna(subset=[param1, param2])

        fig.add_trace(
            go.Scatter(
                x=df[param1],
                y=df[param2],
                mode="markers",
                marker=dict(
                    color=df[depth_col] if depth_col in df.columns else COLORS["primary"],
                    colorscale="Blues",
                    colorbar=dict(
                        title=dict(text="Depth (m)", font=dict(color="#8BAABF")),
                        tickfont=dict(color="#8BAABF"),
                    ),
                    size=5,
                    opacity=0.7,
                ),
                hovertemplate=(
                    f"{PARAM_LABELS.get(param1, param1)}: %{{x:.3f}}<br>"
                    f"{PARAM_LABELS.get(param2, param2)}: %{{y:.3f}}<extra></extra>"
                ),
            )
        )
        self._apply_layout(
            fig,
            title=f"{PARAM_LABELS.get(param1, param1)} vs {PARAM_LABELS.get(param2, param2)}",
            xaxis_title=PARAM_LABELS.get(param1, param1),
            yaxis_title=PARAM_LABELS.get(param2, param2),
        )
        return fig

    def statistics_histogram(
        self, measurements_df: pd.DataFrame, parameter: str
    ) -> go.Figure:
        """Distribution histogram with mean line."""
        fig = go.Figure()
        if measurements_df.empty or parameter not in measurements_df.columns:
            return self._empty_fig(f"No data for {parameter}")

        col = measurements_df[parameter].dropna()
        if col.empty:
            return self._empty_fig(f"No data for {parameter}")

        fig.add_trace(
            go.Histogram(
                x=col,
                nbinsx=40,
                marker_color=COLORS["primary"],
                opacity=0.8,
                name=parameter,
            )
        )
        # Mean line
        mean_val = col.mean()
        fig.add_vline(
            x=mean_val,
            line_color=COLORS["secondary"],
            line_width=2,
            annotation_text=f"Mean: {mean_val:.2f}",
            annotation_font_color=COLORS["secondary"],
        )
        self._apply_layout(
            fig,
            title=f"Distribution — {PARAM_LABELS.get(parameter, parameter)}",
            xaxis_title=PARAM_LABELS.get(parameter, parameter),
            yaxis_title="Count",
        )
        return fig

    def anomaly_plot(
        self, measurements_df: pd.DataFrame, parameter: str
    ) -> go.Figure:
        """Depth profile with anomaly points highlighted in red."""
        fig = go.Figure()
        if measurements_df.empty or parameter not in measurements_df.columns:
            return self._empty_fig(f"No data for {parameter}")

        depth_col = "depth" if "depth" in measurements_df.columns else "pressure"
        df = measurements_df.dropna(subset=[parameter, depth_col]).sort_values(depth_col)

        normal = df[~df.get("anomaly_flag", pd.Series(False, index=df.index))]
        anomalies = df[df.get("anomaly_flag", pd.Series(False, index=df.index))] if "anomaly_flag" in df.columns else pd.DataFrame()

        fig.add_trace(
            go.Scatter(
                x=normal[parameter],
                y=normal[depth_col],
                mode="markers",
                marker=dict(color=COLORS["primary"], size=5),
                name="Normal",
            )
        )
        if not anomalies.empty:
            fig.add_trace(
                go.Scatter(
                    x=anomalies[parameter],
                    y=anomalies[depth_col],
                    mode="markers",
                    marker=dict(color=COLORS["error"], size=10, symbol="x"),
                    name="Anomaly",
                )
            )
        self._apply_layout(
            fig,
            title=f"Anomaly Detection — {PARAM_LABELS.get(parameter, parameter)}",
            xaxis_title=PARAM_LABELS.get(parameter, parameter),
            yaxis=dict(
                autorange="reversed",
                title="Depth (m)",
                gridcolor="#1A3A5C",
                linecolor="#1A3A5C",
            ),
        )
        return fig

    def multi_profile_depth(self, profiles_list: list[dict]) -> go.Figure:
        """Multiple depth profiles on one chart, one color per float."""
        fig = go.Figure()
        if not profiles_list:
            return self._empty_fig("No profiles")

        palette = [
            COLORS["primary"], COLORS["secondary"], COLORS["success"],
            COLORS["purple"], COLORS["error"], "#FF9800", "#00BCD4", "#E040FB",
        ]

        for i, p in enumerate(profiles_list):
            df = p.get("measurements")
            label = p.get("label", f"Profile {i+1}")
            if df is None or df.empty:
                continue
            param = p.get("parameter", "temperature")
            depth_col = "depth" if "depth" in df.columns else "pressure"
            df_clean = df.dropna(subset=[param, depth_col]).sort_values(depth_col)
            if df_clean.empty:
                continue

            fig.add_trace(
                go.Scatter(
                    x=df_clean[param],
                    y=df_clean[depth_col],
                    mode="lines",
                    name=label,
                    line=dict(color=palette[i % len(palette)], width=2),
                )
            )

        self._apply_layout(
            fig,
            title="Multi-Profile Comparison",
            xaxis_title=PARAM_LABELS.get(profiles_list[0].get("parameter", "temperature"), "Value"),
            yaxis=dict(
                autorange="reversed",
                title="Depth (m)",
                gridcolor="#1A3A5C",
                linecolor="#1A3A5C",
            ),
        )
        return fig

    @staticmethod
    def _empty_fig(message: str = "No data available") -> go.Figure:
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(color="#8BAABF", size=14),
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
        )
        return fig
