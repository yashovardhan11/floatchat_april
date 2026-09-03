import logging

import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_TILES = "CartoDB dark_matter"
DEFAULT_CENTER = [20, 75]
DEFAULT_ZOOM = 4


class OceanographicMaps:
    """Folium-based dark ocean maps for ARGO profile visualization."""

    def profile_locations(self, profiles_df: pd.DataFrame):
        """Map with one CircleMarker per profile."""
        import folium

        m = folium.Map(location=DEFAULT_CENTER, zoom_start=DEFAULT_ZOOM, tiles=DEFAULT_TILES)

        if profiles_df.empty:
            return m

        required = {"latitude", "longitude"}
        if not required.issubset(profiles_df.columns):
            return m

        for _, row in profiles_df.iterrows():
            lat = row.get("latitude")
            lon = row.get("longitude")
            if lat is None or lon is None:
                continue
            float_id = row.get("float_id", "Unknown")
            date_val = row.get("measurement_date", "")
            if hasattr(date_val, "strftime"):
                date_str = date_val.strftime("%d %b %Y")
            else:
                date_str = str(date_val)[:10]

            popup_html = f"""
            <div style="font-family: Inter, sans-serif; min-width: 160px;">
                <b style="color:#00C6FF;">Float {float_id}</b><br>
                📅 {date_str}<br>
                📍 {lat:.3f}°N, {lon:.3f}°E<br>
                Cycle: {row.get('cycle_number', 'N/A')}
            </div>
            """
            folium.CircleMarker(
                location=[lat, lon],
                radius=6,
                color="#00C6FF",
                fill=True,
                fill_color="#00C6FF",
                fill_opacity=0.7,
                popup=folium.Popup(popup_html, max_width=200),
                tooltip=f"Float {float_id}",
            ).add_to(m)

        return m

    def float_trajectory(self, profiles_df: pd.DataFrame, float_id: str):
        """Map showing one float's trajectory over time with gradient coloring."""
        import folium

        m = folium.Map(location=DEFAULT_CENTER, zoom_start=DEFAULT_ZOOM, tiles=DEFAULT_TILES)

        if profiles_df.empty:
            return m

        df = profiles_df[profiles_df["float_id"] == float_id].copy()
        if df.empty:
            return m

        if "measurement_date" in df.columns:
            df = df.sort_values("measurement_date")

        lats = df["latitude"].tolist()
        lons = df["longitude"].tolist()
        if len(lats) < 1:
            return m

        # Trajectory line
        coords = list(zip(lats, lons))
        if len(coords) > 1:
            folium.PolyLine(
                coords,
                color="#00C6FF",
                weight=2.5,
                opacity=0.8,
                tooltip=f"Float {float_id} trajectory",
            ).add_to(m)

        # Markers: gradient from dark (old) to bright (new)
        n = len(df)
        for i, (_, row) in enumerate(df.iterrows()):
            lat = row.get("latitude")
            lon = row.get("longitude")
            if lat is None or lon is None:
                continue

            # Color gradient: dark teal → bright cyan
            frac = i / max(n - 1, 1)
            r = int(0 * (1 - frac) + 0 * frac)
            g = int(100 * (1 - frac) + 198 * frac)
            b = int(150 * (1 - frac) + 255 * frac)
            color = f"#{r:02x}{g:02x}{b:02x}"

            date_val = row.get("measurement_date", "")
            date_str = date_val.strftime("%d %b %Y") if hasattr(date_val, "strftime") else str(date_val)[:10]

            # Start = green, End = gold, others = gradient
            if i == 0:
                marker_color = "#00E676"
                icon_str = "play"
            elif i == n - 1:
                marker_color = "#F5A623"
                icon_str = "star"
            else:
                marker_color = color
                icon_str = None

            popup_html = f"""
            <div style="font-family: Inter, sans-serif; min-width: 140px;">
                <b style="color:#00C6FF;">Float {float_id}</b><br>
                📅 {date_str}<br>
                📍 {lat:.3f}°N, {lon:.3f}°E<br>
                Cycle: {row.get('cycle_number', i+1)}
            </div>
            """
            if icon_str:
                folium.Marker(
                    location=[lat, lon],
                    popup=folium.Popup(popup_html, max_width=180),
                    tooltip=date_str,
                    icon=folium.Icon(color="green" if i == 0 else "orange", icon=icon_str, prefix="fa"),
                ).add_to(m)
            else:
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=5,
                    color=marker_color,
                    fill=True,
                    fill_color=marker_color,
                    fill_opacity=0.75,
                    popup=folium.Popup(popup_html, max_width=180),
                    tooltip=date_str,
                ).add_to(m)

        # Center map on trajectory
        if lats:
            m.location = [sum(lats) / len(lats), sum(lons) / len(lons)]

        return m

    def regional_heatmap(self, profiles_df: pd.DataFrame):
        """Density heatmap of profile locations."""
        import folium
        from folium.plugins import HeatMap

        m = folium.Map(location=DEFAULT_CENTER, zoom_start=DEFAULT_ZOOM, tiles=DEFAULT_TILES)

        if profiles_df.empty:
            return m

        required = {"latitude", "longitude"}
        if not required.issubset(profiles_df.columns):
            return m

        heat_data = [
            [row["latitude"], row["longitude"], 1.0]
            for _, row in profiles_df.iterrows()
            if row.get("latitude") is not None and row.get("longitude") is not None
        ]

        if heat_data:
            HeatMap(
                heat_data,
                min_opacity=0.3,
                radius=15,
                blur=10,
                gradient={0.2: "#0072FF", 0.5: "#00C6FF", 0.8: "#F5A623", 1.0: "#FF5252"},
            ).add_to(m)

        return m

    @staticmethod
    def render_to_html(map_obj) -> str:
        """Return HTML string for embedding in Streamlit."""
        return map_obj._repr_html_()
