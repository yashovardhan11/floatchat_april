import logging
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Data Sync — FloatChat",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from utils.helpers import (
    GLOBAL_CSS, page_header, stat_card, section_divider, status_pill
)

# ── CSS first, immediately after set_page_config ──────────────────────────────
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
st.markdown("""<style>
.content-pad { padding: 0 2.5rem 3rem; }
div[data-testid="stButton"] > button[kind="secondary"] {
  background: transparent !important;
  border: 1px solid #1A3A5C !important;
  color: #8BAABF !important;
}
div[data-testid="stButton"] > button[kind="secondary"]:hover {
  border-color: #00C6FF !important;
  color: #F0F8FF !important;
}
div[data-testid="stButton"] > button:disabled {
  background: #061428 !important;
  border: 1px solid #1A3A5C !important;
  color: #4A6580 !important;
  cursor: not-allowed !important;
  opacity: 0.6 !important;
}
</style>""", unsafe_allow_html=True)

# ─── Service init ──────────────────────────────────────────────────────────────

def _get_services():
    if "db" not in st.session_state or st.session_state.db is None:
        try:
            from config.settings import load_config
            from database.connection import DatabaseManager
            from database.vector_store import ChromaVectorStore
            from sync.argo_sync import ArgoSyncEngine
            config = load_config()
            st.session_state.config = config
            st.session_state.db = DatabaseManager(config)
            st.session_state.vs = ChromaVectorStore(config)
            st.session_state.sync = ArgoSyncEngine(
                config, st.session_state.db, st.session_state.vs)
        except Exception as e:
            st.error(f"Failed to initialize services: {e}")
            return None, None
    return st.session_state.db, st.session_state.get("sync")

db, sync_engine = _get_services()

# ─── Header ───────────────────────────────────────────────────────────────────

st.markdown(page_header("Data Sync",
    "Download and manage ARGO float data from Ifremer FTP", "🔄"),
    unsafe_allow_html=True)

st.markdown('<div class="content-pad">', unsafe_allow_html=True)

if st.button("← Home", key="back_home"):
    st.switch_page("Home.py")

if db is None or sync_engine is None:
    st.error("Services not available. Please restart the app.")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ─── Sync status ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=30)
def _get_sync_status(_sync):
    try:
        return _sync.get_sync_status()
    except Exception as e:
        return {"error": str(e)}

status = _get_sync_status(sync_engine)
today_downloaded = status.get("today_downloaded", False)
today_date = status.get("today_date", "Unknown")
latest_available = status.get("latest_available_date", "Unknown")

# ─── TODAY'S HERO STATUS CARD ─────────────────────────────────────────────────

if today_downloaded:
    st.markdown(
        '<div style="background:linear-gradient(135deg,#0A1F3A,#0F2847);'
        'border:1px solid #00E676;border-radius:16px;padding:2rem 2.5rem;'
        'display:flex;justify-content:space-between;align-items:center;'
        'margin-bottom:2rem;flex-wrap:wrap;gap:1rem;">'
        '<div style="display:flex;align-items:center;gap:1.25rem;">'
        '<div style="width:48px;height:48px;background:rgba(0,230,118,0.15);'
        'border:1px solid rgba(0,230,118,0.4);border-radius:50%;'
        'display:flex;align-items:center;justify-content:center;font-size:1.5rem;">&#10003;</div>'
        '<div>'
        '<p style="margin:0;font-size:1.3rem;font-weight:700;color:#00E676;">Today\'s Data Ready</p>'
        f'<p style="margin:0.25rem 0 0;font-size:0.85rem;color:#8BAABF;">'
        f'{today_date} &nbsp;&middot;&nbsp; {str(today_date).replace("-","")}_prof.nc</p>'
        '</div>'
        '</div>'
        '<div style="text-align:right;">'
        '<p style="margin:0;font-size:0.75rem;color:#4A6580;text-transform:uppercase;'
        'letter-spacing:0.08em;">Last synced</p>'
        f'<p style="margin:0.2rem 0 0;font-size:0.9rem;color:#F0F8FF;">'
        f'{status.get("last_sync_date","—")}</p>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.button("✓ Already Up To Date", disabled=True, key="sync_disabled")
else:
    st.markdown(
        '<div style="background:linear-gradient(135deg,#0A1F3A,#0F2847);'
        'border:1px solid #FFB300;border-radius:16px;padding:2rem 2.5rem;'
        'display:flex;justify-content:space-between;align-items:center;'
        'margin-bottom:2rem;flex-wrap:wrap;gap:1rem;">'
        '<div style="display:flex;align-items:center;gap:1.25rem;">'
        '<div style="width:48px;height:48px;background:rgba(255,179,0,0.15);'
        'border:1px solid rgba(255,179,0,0.4);border-radius:50%;'
        'display:flex;align-items:center;justify-content:center;">'
        '<span style="width:12px;height:12px;border-radius:50%;background:#FFB300;'
        'display:block;animation:pulse 2s infinite;"></span>'
        '</div>'
        '<div>'
        '<p style="margin:0;font-size:1.3rem;font-weight:700;color:#FFB300;">Today\'s Data Pending</p>'
        f'<p style="margin:0.25rem 0 0;font-size:0.85rem;color:#8BAABF;">'
        f'{today_date} &nbsp;&middot;&nbsp; Latest available: {latest_available}</p>'
        '</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    if st.button("⬇  Download Today's ARGO Data", key="sync_btn", type="primary"):
        progress_bar = st.progress(0)
        status_text = st.empty()

        status_text.info("🌐 Connecting to ftp.ifremer.fr...")
        progress_bar.progress(10)
        try:
            import datetime as _dt
            today = _dt.datetime.utcnow().date()
            date_str = today.strftime("%Y%m%d")
            status_text.info(f"📥 Downloading {date_str}_prof.nc...")
            progress_bar.progress(30)
            filepath = sync_engine.download_file(today)
            progress_bar.progress(55)
            status_text.info("⚙️  Processing profiles...")
            ingest_result = sync_engine.ingest_file(filepath)
            progress_bar.progress(85)
            status_text.info("🧠 Updating vector search index...")
            sync_status = "success" if not ingest_result["errors"] else "partial"
            db.log_sync("manual", 1, ingest_result["profiles_ingested"], sync_status)
            progress_bar.progress(100)
            n = ingest_result["profiles_ingested"]
            status_text.success(f"✅  Complete! {n} profiles ingested.")
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            logger.exception("Manual sync failed")
            status_text.error(f"❌  Sync failed: {e}")
            progress_bar.progress(0)

# ─── STATS ROW ────────────────────────────────────────────────────────────────

total_profiles = status.get("total_profiles", 0)
last_sync_date = status.get("last_sync_date")
last_sync_str = last_sync_date.strftime("%d %b %Y %H:%M") if last_sync_date else "Never"

try:
    float_count = db.get_float_count()
    date_range = db.get_date_range()
    date_range_str = (
        f"{str(date_range[0])[:10]} — {str(date_range[1])[:10]}"
        if date_range[0] else "No data"
    )
except Exception:
    float_count = 0
    date_range_str = "No data"

s1, s2, s3, s4 = st.columns(4)
with s1:
    st.markdown(stat_card("Total Profiles", f"{total_profiles:,}", "🌊", "#00C6FF"),
                unsafe_allow_html=True)
with s2:
    st.markdown(stat_card("Total Floats", f"{float_count:,}", "📍", "#0072FF"),
                unsafe_allow_html=True)
with s3:
    st.markdown(stat_card("Date Range", date_range_str, "📅", "#F5A623",
                           sublabel="Coverage"),
                unsafe_allow_html=True)
with s4:
    st.markdown(stat_card("Last Sync", last_sync_str, "🕐", "#00E676"),
                unsafe_allow_html=True)

# ─── SYNC HISTORY ─────────────────────────────────────────────────────────────

st.markdown(section_divider("Sync History"), unsafe_allow_html=True)

try:
    history_df = db.get_sync_history(limit=10)
    if history_df.empty:
        st.info("No sync history yet. Perform your first sync above.")
    else:
        def _color_status(val):
            if val == "success":
                return "color: #00E676"
            elif val == "failed":
                return "color: #FF5252"
            elif val == "partial":
                return "color: #FFB300"
            return ""

        styled = history_df.style.map(_color_status, subset=["status"])
        st.dataframe(
            styled,
            use_container_width=True,
            hide_index=True,
            column_config={
                "sync_date": st.column_config.DatetimeColumn("Date", format="D MMM YYYY, HH:mm"),
                "sync_type": st.column_config.TextColumn("Type", width="small"),
                "files_downloaded": st.column_config.NumberColumn("Files", width="small"),
                "profiles_ingested": st.column_config.NumberColumn("Profiles"),
                "status": st.column_config.TextColumn("Status", width="small"),
                "error_message": st.column_config.TextColumn("Error"),
                "id": None,
            },
        )
except Exception as e:
    st.error(f"Failed to load sync history: {e}")

# ─── COVERAGE MAP ─────────────────────────────────────────────────────────────

st.markdown(section_divider("Data Coverage"), unsafe_allow_html=True)

try:
    profiles_df = db.get_profiles(limit=500)
    if profiles_df.empty:
        st.info("No profiles yet. Sync data to see geographic coverage.")
    else:
        from visualization.maps import OceanographicMaps
        import streamlit.components.v1 as components
        maps_obj = OceanographicMaps()
        m = maps_obj.profile_locations(profiles_df)
        components.html(maps_obj.render_to_html(m), height=400)
        st.caption(f"Showing {len(profiles_df)} profiles · {date_range_str}")
except Exception as e:
    st.warning(f"Map unavailable: {e}")

st.markdown('</div>', unsafe_allow_html=True)
