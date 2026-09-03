import logging
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Data Explorer — FloatChat",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from utils.helpers import (
    GLOBAL_CSS, page_header, section_divider,
    format_coordinates, format_date, quality_flag_label,
)

# ── CSS first, immediately after set_page_config ──────────────────────────────
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
st.markdown("""<style>
.content-pad { padding: 0 2.5rem 3rem; }
.filter-bar {
  background: #061428;
  border: 1px solid #1A3A5C;
  border-radius: 12px;
  padding: 1rem 1.5rem;
  margin-bottom: 1.5rem;
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

st.markdown(page_header("Data Explorer",
    "Browse and filter oceanographic profiles by region and date", "🔍"),
    unsafe_allow_html=True)

st.markdown('<div class="content-pad">', unsafe_allow_html=True)

if st.button("← Home", key="back_home"):
    st.switch_page("Home.py")

if db is None:
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ─── FILTER BAR ───────────────────────────────────────────────────────────────

from rag.query_processor import OCEAN_REGIONS

st.markdown('<div class="filter-bar">', unsafe_allow_html=True)
fc1, fc2, fc3, fc4, fc5, fc6 = st.columns([2, 2, 2, 2, 1, 1])

with fc1:
    date_from = st.date_input("From", value=None, key="exp_from", label_visibility="visible")
with fc2:
    date_to = st.date_input("To", value=None, key="exp_to", label_visibility="visible")
with fc3:
    region_labels = ["All Regions"] + [r.replace("_", " ").title() for r in OCEAN_REGIONS]
    region_names  = [None] + list(OCEAN_REGIONS.keys())
    sel_region_label = st.selectbox("Region", region_labels, key="exp_region")
    sel_region = region_names[region_labels.index(sel_region_label)]
with fc4:
    float_id_input = st.text_input("Float ID", placeholder="Search by float ID...", key="exp_float")
with fc5:
    st.markdown("<br>", unsafe_allow_html=True)
    do_search = st.button("Search", type="primary", use_container_width=True, key="exp_search")
with fc6:
    st.markdown("<br>", unsafe_allow_html=True)
    do_reset = st.button("Reset", use_container_width=True, key="exp_reset")

st.markdown('</div>', unsafe_allow_html=True)

if do_reset:
    for k in ("exp_from", "exp_to", "exp_region", "exp_float"):
        st.session_state.pop(k, None)
    st.rerun()

# ─── Build filter kwargs ──────────────────────────────────────────────────────

import datetime as _dt

filter_kwargs: dict = {"limit": 500}

if float_id_input and float_id_input.strip():
    filter_kwargs["float_id"] = float_id_input.strip()
if date_from:
    filter_kwargs["date_from"] = _dt.datetime.combine(date_from, _dt.time.min)
if date_to:
    filter_kwargs["date_to"] = _dt.datetime.combine(date_to, _dt.time.max)
if sel_region and sel_region in OCEAN_REGIONS:
    r = OCEAN_REGIONS[sel_region]
    filter_kwargs.update({
        "lat_min": r["lat_min"], "lat_max": r["lat_max"],
        "lon_min": r["lon_min"], "lon_max": r["lon_max"],
    })

# ─── Load profiles ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def _load_profiles(_db, **kwargs):
    return _db.get_profiles(**kwargs)

profiles_df = _load_profiles(db, **filter_kwargs)

# ─── RESULTS HEADER ──────────────────────────────────────────────────────────

n_profiles = len(profiles_df)
n_floats = profiles_df["float_id"].nunique() if not profiles_df.empty else 0

rh1, rh2 = st.columns([4, 1])
with rh1:
    st.markdown(
        f"<p style='color:#8BAABF;margin:0.5rem 0;'>"
        f"Showing <b style='color:#00C6FF;'>{n_profiles:,}</b> profiles "
        f"from <b style='color:#00C6FF;'>{n_floats:,}</b> floats</p>",
        unsafe_allow_html=True,
    )
with rh2:
    if not profiles_df.empty:
        st.download_button(
            "⬇  Export CSV",
            data=profiles_df.to_csv(index=False).encode("utf-8"),
            file_name="floatchat_profiles.csv",
            mime="text/csv",
            key="dl_profiles",
            use_container_width=True,
        )

# ─── PROFILES TABLE ───────────────────────────────────────────────────────────

if profiles_df.empty:
    st.info("No profiles match your filters. Try adjusting the date range or region.")
else:
    display_cols = [c for c in
        ["float_id", "measurement_date", "latitude", "longitude",
         "cycle_number", "data_mode", "quality_flag"]
        if c in profiles_df.columns]

    sel = st.dataframe(
        profiles_df[display_cols],
        use_container_width=True,
        height=400,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "float_id": st.column_config.TextColumn("Float ID", width="small"),
            "measurement_date": st.column_config.DateColumn("Date", format="DD MMM YYYY"),
            "latitude":  st.column_config.NumberColumn("Lat",  format="%.2f°"),
            "longitude": st.column_config.NumberColumn("Lon",  format="%.2f°"),
            "cycle_number": st.column_config.NumberColumn("Cycle", width="small"),
            "data_mode":    st.column_config.TextColumn("Mode",    width="small"),
            "quality_flag": st.column_config.NumberColumn("Quality", width="small"),
        },
        key="profiles_table",
    )

    # ─── SELECTED PROFILE DETAIL ──────────────────────────────────────────────

    row_indices = (sel.get("selection", {}) or {}).get("rows", []) if isinstance(sel, dict) else []

    if row_indices:
        profile = profiles_df.iloc[row_indices[0]]
        pid = profile.get("id")

        st.markdown(section_divider("Profile Detail"), unsafe_allow_html=True)

        dc1, dc2 = st.columns([4, 6])

        with dc1:
            lat   = float(profile.get("latitude", 0))
            lon   = float(profile.get("longitude", 0))
            qflag = int(profile.get("quality_flag", 1))
            qtext = quality_flag_label(qflag)
            qcolor = "#00E676" if qflag == 1 else ("#FFB300" if qflag == 2 else "#FF5252")
            mode = profile.get("data_mode", "R")
            mode_color = "#00E676" if mode == "D" else "#FFB300"

            rows_html = "".join(
                f'<tr>'
                f'<td style="color:#4A6580;font-size:0.78rem;padding:4px 0;">{lbl}</td>'
                f'<td style="color:#F0F8FF;font-size:0.82rem;padding:4px 0;">{val}</td>'
                f'</tr>'
                for lbl, val in [
                    ("📅 Date", format_date(profile.get("measurement_date"))),
                    ("📍 Location", format_coordinates(lat, lon)),
                    ("🔄 Cycle", profile.get("cycle_number", "N/A")),
                    ("📁 Source", str(profile.get("source_file", "N/A"))[:28]),
                    ("🕐 Synced", str(profile.get("sync_date", "N/A"))[:19]),
                ]
            )
            st.markdown(
                '<div style="background:#0A1F3A;border:1px solid #1A3A5C;'
                'border-radius:12px;padding:1.5rem;">'
                f'<p style="margin:0;font-size:1.4rem;font-weight:700;color:#00C6FF;">'
                f'Float {profile.get("float_id","?")}</p>'
                '<div style="display:flex;gap:6px;margin:0.5rem 0 1rem;flex-wrap:wrap;">'
                f'<span style="background:rgba(0,198,255,0.1);border:1px solid rgba(0,198,255,0.2);'
                f'color:{mode_color};padding:2px 9px;border-radius:20px;font-size:0.7rem;'
                f'font-weight:600;">Mode: {mode}</span>'
                f'<span style="background:rgba(0,230,118,0.1);border:1px solid rgba(0,230,118,0.2);'
                f'color:{qcolor};padding:2px 9px;border-radius:20px;font-size:0.7rem;'
                f'font-weight:600;">QC: {qtext}</span>'
                '</div>'
                f'<table style="width:100%;border-collapse:collapse;">{rows_html}</table>'
                '</div>',
                unsafe_allow_html=True,
            )

        with dc2:
            if pid is not None:
                @st.cache_data(ttl=300)
                def _load_meas(_db, _pid):
                    return _db.get_measurements_by_profile(_pid)
                meas_df = _load_meas(db, int(pid))

                if not meas_df.empty:
                    from visualization.plots import OceanographicPlots, PARAM_LABELS
                    plotter = OceanographicPlots()

                    param_opts = [p for p in
                        ["temperature", "salinity", "oxygen", "nitrate", "chlorophyll"]
                        if p in meas_df.columns and meas_df[p].notna().any()]

                    if param_opts:
                        param = st.selectbox(
                            "Parameter",
                            param_opts,
                            key="detail_param",
                            format_func=lambda x: PARAM_LABELS.get(x, x),
                        )
                        fig = plotter.depth_profile(meas_df, param)
                        fig.update_layout(height=300)
                        st.plotly_chart(fig, use_container_width=True)

                    st.download_button(
                        "⬇  Download Measurements CSV",
                        data=meas_df.to_csv(index=False).encode("utf-8"),
                        file_name=f"measurements_{pid}.csv",
                        mime="text/csv",
                        key="dl_meas",
                    )
                else:
                    st.info("No measurements for this profile.")

st.markdown('</div>', unsafe_allow_html=True)
