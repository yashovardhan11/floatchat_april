import logging
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Visualizations — FloatChat",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from utils.helpers import (
    GLOBAL_CSS, page_header, stat_card, section_divider, create_profile_display_name,
)

# ── CSS first, immediately after set_page_config ──────────────────────────────
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
st.markdown("""<style>
.content-pad { padding: 0 2.5rem 3rem; }
.stTabs [data-baseweb="tab"] {
  background: #061428 !important;
  border: 1px solid #1A3A5C !important;
  border-bottom: none !important;
  border-radius: 8px 8px 0 0 !important;
  margin-right: 4px !important;
  padding: 0.5rem 1.25rem !important;
  color: #8BAABF !important;
}
.stTabs [aria-selected="true"] {
  background: rgba(0,198,255,0.1) !important;
  border-color: #00C6FF !important;
  color: #00C6FF !important;
  font-weight: 600 !important;
}
.btn-secondary div[data-testid="stButton"] > button {
  background: transparent !important;
  border: 1px solid #1A3A5C !important;
  color: #8BAABF !important;
  font-weight: 500 !important;
}
.btn-secondary div[data-testid="stButton"] > button:hover {
  border-color: #00C6FF !important;
  color: #F0F8FF !important;
}
</style>""", unsafe_allow_html=True)

# ─── Service init ──────────────────────────────────────────────────────────────

def _get_db():
    if "db" not in st.session_state or st.session_state.db is None:
        try:
            from config.settings import load_config
            from database.connection import DatabaseManager
            config = load_config()
            st.session_state.db = DatabaseManager(config)
        except Exception as e:
            st.error(f"Database init failed: {e}")
            return None
    return st.session_state.db

db = _get_db()

# ─── Header ───────────────────────────────────────────────────────────────────

st.markdown(page_header("Visualizations",
    "Interactive oceanographic charts, maps and statistics", "📊"),
    unsafe_allow_html=True)

st.markdown('<div class="content-pad">', unsafe_allow_html=True)

if st.button("← Home", key="back_home"):
    st.switch_page("Home.py")

if db is None:
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ─── Load data ────────────────────────────────────────────────────────────────

import pandas as _pd

@st.cache_data(ttl=120)
def _load_profiles(_db, limit=1000):
    return _db.get_profiles(limit=limit)

@st.cache_data(ttl=120)
def _load_measurements(_db, pids: tuple):
    dfs = []
    for pid in pids[:50]:
        mdf = _db.get_measurements_by_profile(pid)
        if not mdf.empty:
            dfs.append(mdf)
    return _pd.concat(dfs, ignore_index=True) if dfs else _pd.DataFrame()

profiles_df = _load_profiles(db)
measurements_df = _pd.DataFrame()
if not profiles_df.empty:
    pids = tuple(profiles_df["id"].tolist()[:50])
    measurements_df = _load_measurements(db, pids)

# ─── SUMMARY METRICS ROW ─────────────────────────────────────────────────────

n_floats = profiles_df["float_id"].nunique() if not profiles_df.empty else 0
n_meas   = len(measurements_df)
date_range_str = "No data"
if not profiles_df.empty and "measurement_date" in profiles_df.columns:
    dates = profiles_df["measurement_date"].dropna()
    if not dates.empty:
        date_range_str = f"{str(dates.min())[:10]} — {str(dates.max())[:10]}"

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.markdown(stat_card("Profiles Loaded", f"{len(profiles_df):,}", "🌊", "#00C6FF"),
                unsafe_allow_html=True)
with m2:
    st.markdown(stat_card("Unique Floats", f"{n_floats:,}", "📍", "#0072FF"),
                unsafe_allow_html=True)
with m3:
    st.markdown(stat_card("Measurements", f"{n_meas:,}", "📏", "#F5A623"),
                unsafe_allow_html=True)
with m4:
    st.markdown(stat_card("Date Range", date_range_str, "📅", "#00E676",
                           sublabel="Coverage"),
                unsafe_allow_html=True)

st.markdown(section_divider(), unsafe_allow_html=True)

# ─── TABS ─────────────────────────────────────────────────────────────────────

from visualization.plots import OceanographicPlots, PARAM_LABELS
from visualization.maps import OceanographicMaps

plotter  = OceanographicPlots()
maps_obj = OceanographicMaps()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 Profile Analysis",
    "🗺 Geographic Maps",
    "📉 Time Series",
    "🔬 Parameter Comparison",
    "📊 Statistics",
])

# ════════════════════════════════════════
# TAB 1 — PROFILE ANALYSIS
# ════════════════════════════════════════
with tab1:
    if profiles_df.empty:
        st.info("No profiles loaded. Sync data first.")
    else:
        left, right = st.columns([3, 7])

        with left:
            profile_labels = [create_profile_display_name(row)
                              for _, row in profiles_df.head(200).iterrows()]
            sel_label = st.selectbox("Profile", profile_labels, key="t1_profile")
            sel_idx   = profile_labels.index(sel_label) if sel_label in profile_labels else 0
            profile   = profiles_df.iloc[sel_idx]
            pid       = profile.get("id")

            meas_t1 = _pd.DataFrame()
            if pid is not None:
                @st.cache_data(ttl=300)
                def _single_meas(_db, _pid):
                    return _db.get_measurements_by_profile(_pid)
                meas_t1 = _single_meas(db, int(pid))

            avail_params = [p for p in
                ["temperature", "salinity", "oxygen", "nitrate", "chlorophyll", "density"]
                if p in meas_t1.columns and meas_t1[p].notna().any()] if not meas_t1.empty else []

            param = st.selectbox("Parameter", avail_params, key="t1_param",
                                 format_func=lambda x: PARAM_LABELS.get(x, x)) if avail_params else None

            if param and not meas_t1.empty:
                col_data = meas_t1[param].dropna()
                st.markdown(section_divider("Stats"), unsafe_allow_html=True)
                for lbl, val in [
                    ("Min",  f"{col_data.min():.3f}"),
                    ("Max",  f"{col_data.max():.3f}"),
                    ("Mean", f"{col_data.mean():.3f}"),
                    ("Std",  f"{col_data.std():.3f}"),
                ]:
                    st.markdown(
                        f'<div style="display:flex;justify-content:space-between;'
                        f'padding:4px 0;border-bottom:1px solid #1A3A5C;">'
                        f'<span style="color:#4A6580;font-size:0.8rem;">{lbl}</span>'
                        f'<span style="color:#F0F8FF;font-size:0.8rem;font-weight:600;">{val}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                st.markdown(section_divider("Export"), unsafe_allow_html=True)
                st.markdown('<div class="btn-secondary">', unsafe_allow_html=True)
                st.download_button(
                    "⬇  Download Chart Data",
                    data=meas_t1[[param, "depth"]].dropna().to_csv(index=False).encode(),
                    file_name=f"profile_{pid}_{param}.csv",
                    key="t1_dl",
                    use_container_width=True,
                )
                st.markdown('</div>', unsafe_allow_html=True)

        with right:
            if param and not meas_t1.empty:
                fig = plotter.depth_profile(meas_t1, param)
                fig.update_layout(height=500)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Select a profile with available measurements.")

# ════════════════════════════════════════
# TAB 2 — GEOGRAPHIC MAPS
# ════════════════════════════════════════
with tab2:
    import streamlit.components.v1 as _components
    import datetime as _dt

    map_type = st.radio(
        "Map Type",
        ["Profile Locations", "Float Trajectory", "Heatmap"],
        horizontal=True,
        key="t2_maptype",
    )

    filtered_profiles = profiles_df.copy()

    if not profiles_df.empty and "measurement_date" in profiles_df.columns:
        dates = profiles_df["measurement_date"].dropna()
        if not dates.empty:
            min_d = dates.min().date() if hasattr(dates.min(), "date") else _dt.date(2020, 1, 1)
            max_d = dates.max().date() if hasattr(dates.max(), "date") else _dt.date.today()
            dr = st.date_input("Date Range", value=[min_d, max_d], key="t2_dates")
            if isinstance(dr, (list, tuple)) and len(dr) == 2:
                d_from = _dt.datetime.combine(dr[0], _dt.time.min)
                d_to   = _dt.datetime.combine(dr[1], _dt.time.max)
                mask = ((filtered_profiles["measurement_date"] >= d_from) &
                        (filtered_profiles["measurement_date"] <= d_to))
                filtered_profiles = filtered_profiles[mask]

    if filtered_profiles.empty:
        st.info("No profiles for this date range.")
    elif map_type == "Profile Locations":
        m = maps_obj.profile_locations(filtered_profiles)
        _components.html(maps_obj.render_to_html(m), height=550)
        st.caption(f"{len(filtered_profiles):,} profiles shown")
    elif map_type == "Float Trajectory":
        fids = filtered_profiles["float_id"].unique().tolist() if "float_id" in filtered_profiles.columns else []
        if fids:
            sel_float = st.selectbox("Float ID", fids, key="t2_float")
            m = maps_obj.float_trajectory(filtered_profiles, sel_float)
            _components.html(maps_obj.render_to_html(m), height=550)
        else:
            st.info("No floats available.")
    else:
        m = maps_obj.regional_heatmap(filtered_profiles)
        _components.html(maps_obj.render_to_html(m), height=550)
        st.caption(f"Heatmap of {len(filtered_profiles):,} profiles")

# ════════════════════════════════════════
# TAB 3 — TIME SERIES
# ════════════════════════════════════════
with tab3:
    if measurements_df.empty:
        st.info("No measurement data. Sync data first.")
    else:
        ts_params = [p for p in
            ["temperature", "salinity", "oxygen", "nitrate", "chlorophyll"]
            if p in measurements_df.columns and measurements_df[p].notna().any()]

        if not ts_params:
            st.info("No parameters available.")
        else:
            tc1, tc2, tc3 = st.columns([2, 2, 3])
            with tc1:
                ts_param = st.selectbox("Parameter", ts_params, key="t3_param",
                                        format_func=lambda x: PARAM_LABELS.get(x, x))
            with tc2:
                float_opts = profiles_df["float_id"].unique().tolist() if not profiles_df.empty else []
                sel_floats = st.multiselect("Float IDs (optional)", float_opts, key="t3_floats")
            with tc3:
                import datetime as _dt2
                dates2 = profiles_df["measurement_date"].dropna() if not profiles_df.empty else _pd.Series()
                if not dates2.empty:
                    min_d2 = dates2.min().date()
                    max_d2 = dates2.max().date()
                    ts_dr = st.date_input("Date Range", value=[min_d2, max_d2], key="t3_dates")
                else:
                    ts_dr = None

            ts_prof = profiles_df.copy()
            if sel_floats:
                ts_prof = ts_prof[ts_prof["float_id"].isin(sel_floats)]
            if isinstance(ts_dr, (list, tuple)) and len(ts_dr) == 2:
                from datetime import datetime as _DT
                ts_prof = ts_prof[
                    (ts_prof["measurement_date"] >= _DT.combine(ts_dr[0], _dt2.time.min)) &
                    (ts_prof["measurement_date"] <= _DT.combine(ts_dr[1], _dt2.time.max))
                ]

            ts_pids = ts_prof["id"].tolist() if not ts_prof.empty else []
            ts_meas = measurements_df[measurements_df["profile_id"].isin(ts_pids)] if ts_pids else measurements_df

            fig = plotter.time_series(ts_prof, ts_meas, ts_param)
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

            with st.expander("📋 Raw Data", expanded=False):
                if not ts_meas.empty and ts_param in ts_meas.columns:
                    st.dataframe(
                        ts_meas[["profile_id", ts_param, "depth"]].dropna(subset=[ts_param]).head(200),
                        use_container_width=True, hide_index=True,
                    )

# ════════════════════════════════════════
# TAB 4 — PARAMETER COMPARISON
# ════════════════════════════════════════
with tab4:
    if measurements_df.empty:
        st.info("No measurement data available.")
    else:
        all_params = [p for p in
            ["temperature", "salinity", "oxygen", "nitrate", "chlorophyll", "density", "pressure"]
            if p in measurements_df.columns and measurements_df[p].notna().any()]

        if len(all_params) < 2:
            st.info("Need at least 2 parameters.")
        else:
            pc1, pc2, pc3 = st.columns([2, 2, 1])
            with pc1:
                p1 = st.selectbox("X Axis", all_params, index=1, key="t4_p1",
                                  format_func=lambda x: PARAM_LABELS.get(x, x))
            with pc2:
                p2 = st.selectbox("Y Axis", all_params, index=0, key="t4_p2",
                                  format_func=lambda x: PARAM_LABELS.get(x, x))
            with pc3:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("T-S Diagram", key="ts_btn"):
                    st.session_state["t4_p1"] = "salinity"
                    st.session_state["t4_p2"] = "temperature"
                    st.rerun()

            fig = plotter.parameter_comparison(measurements_df, p1, p2)
            fig.update_layout(height=450)
            st.plotly_chart(fig, use_container_width=True)

            df_clean = measurements_df[[p1, p2]].dropna()
            if len(df_clean) > 1:
                corr = df_clean[p1].corr(df_clean[p2])
                st.markdown(
                    f'<div style="text-align:center;">'
                    f'<span style="background:#0A1F3A;border:1px solid #1A3A5C;'
                    f'border-radius:20px;padding:4px 16px;font-size:0.8rem;color:#8BAABF;">'
                    f'Pearson r = <b style="color:#00C6FF;">{corr:.4f}</b></span></div>',
                    unsafe_allow_html=True,
                )

# ════════════════════════════════════════
# TAB 5 — STATISTICS
# ════════════════════════════════════════
with tab5:
    stats = db.get_statistics()
    anom_count = int(measurements_df["anomaly_flag"].sum()) if "anomaly_flag" in measurements_df.columns else 0

    ss1, ss2, ss3, ss4 = st.columns(4)
    with ss1:
        st.markdown(stat_card("Total Profiles", f"{stats.get('total_profiles',0):,}", "🌊", "#00C6FF"),
                    unsafe_allow_html=True)
    with ss2:
        st.markdown(stat_card("Total Floats", f"{stats.get('total_floats',0):,}", "📍", "#0072FF"),
                    unsafe_allow_html=True)
    with ss3:
        st.markdown(stat_card("Measurements", f"{stats.get('total_measurements',0):,}", "📏", "#F5A623"),
                    unsafe_allow_html=True)
    with ss4:
        st.markdown(stat_card("Anomalies", f"{anom_count:,}", "⚠️", "#FF5252"),
                    unsafe_allow_html=True)

    if not measurements_df.empty:
        st.markdown(section_divider("Distributions"), unsafe_allow_html=True)
        hist_params = [p for p in
            ["temperature", "salinity", "oxygen", "depth", "nitrate", "chlorophyll"]
            if p in measurements_df.columns and measurements_df[p].notna().any()]

        if hist_params:
            cols_per_row = 2
            for i in range(0, min(len(hist_params), 6), cols_per_row):
                row_cols = st.columns(cols_per_row)
                for j, col in enumerate(row_cols):
                    pi = i + j
                    if pi < len(hist_params):
                        with col:
                            fig = plotter.statistics_histogram(measurements_df, hist_params[pi])
                            fig.update_layout(height=250, margin=dict(l=40, r=10, t=40, b=30))
                            st.plotly_chart(fig, use_container_width=True)

    if not measurements_df.empty and "quality_flag" in measurements_df.columns:
        st.markdown(section_divider("Data Quality"), unsafe_allow_html=True)
        q1, q2 = st.columns(2)

        with q1:
            import plotly.graph_objects as go
            qf = measurements_df["quality_flag"].value_counts()
            fig_q = go.Figure(go.Bar(
                x=[f"Flag {k}" for k in qf.index],
                y=qf.values,
                marker_color=["#00E676", "#00C6FF", "#FFB300", "#FF5252", "#8BAABF"][:len(qf)],
            ))
            fig_q.update_layout(
                title=dict(text="Quality Flag Distribution", font=dict(color="#F0F8FF")),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#8BAABF"), height=280,
                xaxis=dict(gridcolor="#1A3A5C"), yaxis=dict(gridcolor="#1A3A5C"),
                margin=dict(l=40, r=10, t=50, b=30),
            )
            st.plotly_chart(fig_q, use_container_width=True)

        with q2:
            if "anomaly_flag" in measurements_df.columns:
                anom_params = [p for p in
                    ["temperature", "salinity", "oxygen", "nitrate", "chlorophyll"]
                    if p in measurements_df.columns]
                if anom_params:
                    anom_counts = {
                        p: int(measurements_df[measurements_df["anomaly_flag"] == True][p].notna().sum())
                        for p in anom_params
                    }
                    fig_a = go.Figure(go.Bar(
                        x=list(anom_counts.keys()),
                        y=list(anom_counts.values()),
                        marker_color="#FF5252",
                    ))
                    fig_a.update_layout(
                        title=dict(text="Anomaly Count by Parameter", font=dict(color="#F0F8FF")),
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(color="#8BAABF"), height=280,
                        xaxis=dict(gridcolor="#1A3A5C"), yaxis=dict(gridcolor="#1A3A5C"),
                        margin=dict(l=40, r=10, t=50, b=30),
                    )
                    st.plotly_chart(fig_a, use_container_width=True)

st.markdown('</div>', unsafe_allow_html=True)
