import logging
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="FloatChat",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from utils.helpers import GLOBAL_CSS, status_pill

# ── CSS first, immediately after set_page_config ──────────────────────────────
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
st.markdown("""<style>
.content-pad { padding: 0 2.5rem 3rem; }
.home-topbar {
  background: linear-gradient(180deg, rgba(2,11,24,0.96) 0%, rgba(4,17,34,0.92) 100%);
  border-bottom: 1px solid rgba(26, 58, 92, 0.95);
  padding: 0.16rem 2.5rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  position: sticky;
  top: 0;
  z-index: 100;
  backdrop-filter: blur(10px);
}
.home-topbar-brand {
  display: flex;
  align-items: center;
  gap: 8px;
}
.home-topbar-pills {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.home-hero-shell {
  position: relative;
  margin-top: 0.18rem;
  margin-bottom: 1.2rem;
  padding: 0.58rem 0 0.42rem;
}
.home-hero-shell::before {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: 26px;
  background:
    radial-gradient(circle at top left, rgba(0,198,255,0.16), transparent 36%),
    linear-gradient(135deg, rgba(10,31,58,0.84) 0%, rgba(6,20,40,0.66) 100%);
  border: 1px solid rgba(59, 101, 142, 0.45);
  box-shadow:
    0 18px 38px rgba(0, 0, 0, 0.16),
    inset 0 1px 0 rgba(255, 255, 255, 0.03);
  pointer-events: none;
}
.home-hero {
  position: relative;
  z-index: 1;
  padding: 0.6rem 1.35rem 0.92rem;
}
.home-hero-kicker {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  margin-bottom: 0.42rem;
  padding: 0.28rem 0.66rem;
  border-radius: 999px;
  border: 1px solid rgba(0,198,255,0.22);
  background: rgba(0,198,255,0.08);
  color: #7fdfff;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.home-hero h1 {
  margin: 0;
  font-size: 3rem;
  font-weight: 800;
  color: #F0F8FF;
  letter-spacing: -0.04em;
  line-height: 1.05;
}
.home-hero p {
  margin: 0.62rem 0 0.9rem;
  font-size: 0.97rem;
  color: #9fb7c9;
  max-width: 560px;
  line-height: 1.7;
}
.home-hero-stats {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.home-hero-stat {
  background: rgba(8, 24, 45, 0.82);
  border: 1px solid rgba(0,198,255,0.22);
  border-radius: 999px;
  padding: 0.4rem 0.9rem;
  font-size: 0.8rem;
  color: #b5f0ff;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.02);
}
div[data-testid="column"] > div[data-testid="stVerticalBlock"] {
  height: 100% !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] {
  height: 100% !important;
  background: linear-gradient(180deg, #143a57 0%, #0f2e45 58%, #0a1f35 100%) !important;
  border: 1px solid rgba(92, 150, 198, 0.78) !important;
  border-radius: 20px !important;
  box-shadow:
    0 14px 30px rgba(0, 0, 0, 0.24),
    inset 0 0 0 1px rgba(255, 255, 255, 0.04) !important;
  padding: 1.2rem !important;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:hover {
  transform: translateY(-3px) !important;
  border-color: rgba(0, 198, 255, 0.82) !important;
  box-shadow: 0 18px 38px rgba(0, 198, 255, 0.14) !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] > div {
  gap: 0.9rem !important;
}
.home-nav-card {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
  min-height: 160px;
}
.home-nav-accent {
  width: 58px;
  height: 4px;
  border-radius: 999px;
  background: linear-gradient(90deg, #00C6FF 0%, #58E1FF 100%);
}
.home-nav-icon {
  font-size: 1.85rem;
  line-height: 1;
}
.home-nav-title {
  margin: 0;
  font-size: 1.08rem;
  font-weight: 700;
  color: #F0F8FF;
  letter-spacing: -0.02em;
}
.home-nav-desc {
  margin: 0;
  color: #B6CFE1;
  font-size: 0.88rem;
  line-height: 1.6;
  min-height: 4.4rem;
}
.home-nav-badge {
  align-self: flex-start;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  border-radius: 999px;
  padding: 0.35rem 0.7rem;
}
div[data-testid="stButton"] > button {
  min-height: 46px !important;
  background: linear-gradient(135deg, #1ad2ff 0%, #0072ff 100%) !important;
  color: #031422 !important;
  border: 1px solid rgba(88, 225, 255, 0.75) !important;
  border-radius: 12px !important;
  font-size: 0.9rem !important;
  font-weight: 700 !important;
  letter-spacing: 0.01em !important;
  box-shadow: 0 10px 20px rgba(0, 114, 255, 0.22) !important;
}
div[data-testid="stButton"] > button:hover {
  background: linear-gradient(135deg, #46dcff 0%, #2284ff 100%) !important;
  color: #031422 !important;
  transform: translateY(-1px) !important;
}
div[data-testid="stButton"] > button:focus-visible {
  outline: 2px solid rgba(88, 225, 255, 0.95) !important;
  outline-offset: 2px !important;
}
@media (max-width: 1100px) {
  .content-pad { padding: 0 1.25rem 2rem; }
  .home-topbar { padding: 0.3rem 1.25rem; }
  .home-hero-shell { margin-top: 0.28rem; }
  .home-hero { padding: 0.72rem 1.05rem 0.86rem; }
}
@media (max-width: 768px) {
  div[data-testid="stVerticalBlockBorderWrapper"] {
    padding: 1rem !important;
  }
  .home-topbar {
    align-items: flex-start;
    gap: 0.75rem;
    flex-direction: column;
  }
  .home-topbar-pills {
    justify-content: flex-start;
  }
  .home-nav-card {
    min-height: 0;
  }
  .home-nav-desc {
    min-height: 0;
  }
  .home-hero-shell {
    margin-top: 0.2rem;
    padding: 0.45rem 0 0.32rem;
  }
  .home-hero h1 {
    font-size: 2.35rem;
  }
}
</style>""", unsafe_allow_html=True)


# ─── System init (once per session) ──────────────────────────────────────────

def _init_system() -> None:
    with st.spinner("Initializing FloatChat..."):
        try:
            from config.settings import load_config
            config = load_config()
            st.session_state.config = config
        except Exception as e:
            st.session_state.init_error = str(e)
            return

        try:
            from database.connection import DatabaseManager
            st.session_state.db = DatabaseManager(config)
        except Exception as e:
            st.session_state.init_error = f"Database: {e}"
            return

        try:
            from database.vector_store import ChromaVectorStore
            st.session_state.vs = ChromaVectorStore(config)
        except Exception as e:
            logger.exception("ChromaVectorStore init")
            st.session_state.vs = None

        try:
            from sync.argo_sync import ArgoSyncEngine
            st.session_state.sync = ArgoSyncEngine(
                config, st.session_state.db, st.session_state.vs)
        except Exception as e:
            st.session_state.sync = None

        try:
            from rag.groq_rag import OceanRAG
            st.session_state.rag = OceanRAG(config)
        except Exception as e:
            st.session_state.rag = None

        if st.session_state.get("sync"):
            try:
                st.session_state.sync.run_auto_sync()
            except Exception:
                pass

        st.session_state.initialized = True


if "initialized" not in st.session_state:
    _init_system()

# ─── Helper checks ────────────────────────────────────────────────────────────

def _db_ok():
    return st.session_state.get("db") is not None

def _ai_ok():
    rag = st.session_state.get("rag")
    return rag is not None and (rag.groq_client is not None or rag.openai_client is not None)

def _vs_ok():
    return st.session_state.get("vs") is not None

def _ai_label():
    rag = st.session_state.get("rag")
    if rag and rag.groq_client:
        return "Groq Ready"
    if rag and rag.openai_client:
        return "OpenAI Ready"
    return "No Key"

# ─── Live data ────────────────────────────────────────────────────────────────

db = st.session_state.get("db")
total_profiles = db.get_profile_count() if db else 0
total_floats = db.get_float_count() if db else 0
last_sync = db.get_latest_sync_date() if db else None
last_sync_str = last_sync.strftime("%d %b %H:%M") if last_sync else "Never"
today_ready = False
if st.session_state.get("sync"):
    try:
        today_ready = st.session_state.sync.is_today_downloaded()
    except Exception:
        pass

vs_stats = {}
if st.session_state.get("vs"):
    try:
        vs_stats = st.session_state.vs.get_statistics()
    except Exception:
        pass

date_range_str = "No data"
if db:
    try:
        dr = db.get_date_range()
        if dr[0]:
            date_range_str = f"{str(dr[0])[:10]} — {str(dr[1])[:10]}"
    except Exception:
        pass

rag = st.session_state.get("rag")
llm_badge = "Groq" if (rag and rag.groq_client) else ("OpenAI" if (rag and rag.openai_client) else "No Key")

# ─── TOP NAV BAR ──────────────────────────────────────────────────────────────
# Build ALL pills into one string, then render the whole navbar in ONE st.markdown call.

pills_html = (
    status_pill("Database", "Connected" if _db_ok() else "Offline", _db_ok())
    + status_pill("AI", _ai_label(), _ai_ok())
    + status_pill("Vectors", "Ready" if _vs_ok() else "Not Ready", _vs_ok())
    + status_pill("Sync", last_sync_str, last_sync is not None)
)

st.markdown(
    '<div class="home-topbar">'
    '<div class="home-topbar-brand">'
    '<span style="font-size:1.4rem;">&#127754;</span>'
    '<span style="font-size:1.1rem;font-weight:700;color:#00C6FF;letter-spacing:-0.02em;">FloatChat</span>'
    '<span style="font-size:0.65rem;color:#4A6580;border:1px solid #1A3A5C;'
    'padding:2px 8px;border-radius:4px;">ARGO Intelligence</span>'
    '</div>'
    f'<div class="home-topbar-pills">{pills_html}</div>'
    '</div>',
    unsafe_allow_html=True,
)

# ─── HERO SECTION ─────────────────────────────────────────────────────────────

st.markdown('<div class="content-pad">', unsafe_allow_html=True)

st.markdown(
    '<div class="home-hero-shell">'
    '<div class="home-hero">'
    '<span class="home-hero-kicker">&#9889; Live ARGO intelligence layer</span>'
    '<h1>Ocean Intelligence,<br>'
    '<span style="color:#00C6FF;">Powered by AI</span></h1>'
    '<p>Query, explore and analyze ARGO float data using natural language. '
    'Powered by hybrid geospatial-semantic retrieval.</p>'
    '<div class="home-hero-stats">'
    '<span class="home-hero-stat">'
    f'&#127754; {total_profiles:,} Profiles</span>'
    '<span class="home-hero-stat">'
    f'&#128205; {total_floats:,} Active Floats</span>'
    '</div>'
    '</div>'
    '</div>',
    unsafe_allow_html=True,
)

# ─── NAV CARDS ────────────────────────────────────────────────────────────────

sync_badge = "Live" if today_ready else "Pending"

cards = [
    ("pages/1_Data_Sync.py", "open_sync", "🔄", "Data Sync",
     "Download latest ARGO float data from official repositories.",
     sync_badge, "#00E676"),
    ("pages/2_Data_Explorer.py", "open_explorer", "🔍", "Explorer",
     "Browse and filter oceanographic profiles by region and date.",
     f"{total_profiles:,} profiles", "#00C6FF"),
    ("pages/3_AI_Chat.py", "open_chat", "🤖", "AI Chat",
     "Ask questions in natural language using hybrid retrieval AI.",
     llm_badge, "#F5A623"),
    ("pages/4_Visualizations.py", "open_viz", "📊", "Charts",
     "Interactive depth profiles, maps, time series and statistics.",
     "5 views", "#7EC8FF"),
]

col1, col2, col3, col4 = st.columns(4)
for col, (page, key, icon, title, desc, badge, badge_color) in zip(
    [col1, col2, col3, col4], cards
):
    with col:
        with st.container(border=True):
            st.markdown(
                f"""
                <div class="home-nav-card">
                  <div class="home-nav-accent"></div>
                  <div class="home-nav-icon">{icon}</div>
                  <p class="home-nav-title">{title}</p>
                  <p class="home-nav-desc">{desc}</p>
                  <span class="home-nav-badge"
                        style="color:{badge_color};border:1px solid {badge_color}33;background:{badge_color}14;">
                    {badge}
                  </span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(f"Open {title}", key=key, use_container_width=True):
                st.switch_page(page)

# ─── LIVE DATA STRIP ──────────────────────────────────────────────────────────

today_status = "&#10003; Ready" if today_ready else "&#8987; Pending"
vec_docs = vs_stats.get("total_documents", 0)

def _strip_stat(label: str, value: str, color: str = "#00C6FF") -> str:
    return (
        f'<div style="border-left:3px solid {color};padding:0 1.25rem;text-align:center;">'
        f'<p style="margin:0;font-size:0.65rem;color:#4A6580;'
        f'text-transform:uppercase;letter-spacing:0.1em;">{label}</p>'
        f'<p style="margin:0.2rem 0 0;font-size:1.1rem;font-weight:700;color:#F0F8FF;">{value}</p>'
        f'</div>'
    )

strip_items = (
    _strip_stat("Total Profiles", f"{total_profiles:,}", "#00C6FF")
    + _strip_stat("Total Floats", f"{total_floats:,}", "#0072FF")
    + _strip_stat("Date Range", date_range_str, "#F5A623")
    + _strip_stat("Today's Data", today_status, "#00E676" if today_ready else "#FFB300")
    + _strip_stat("Last Sync", last_sync_str, "#00E676")
    + _strip_stat("Vector Docs", f"{vec_docs:,}", "#B388FF")
)

st.markdown(
    '<div style="background:#061428;border:1px solid #1A3A5C;border-radius:12px;'
    'padding:1.25rem 2rem;display:flex;justify-content:space-around;'
    f'align-items:center;margin-top:2rem;flex-wrap:wrap;gap:1rem;">{strip_items}</div>',
    unsafe_allow_html=True,
)

if "init_error" in st.session_state:
    st.error(f"Initialization error: {st.session_state.init_error}")

st.markdown('</div>', unsafe_allow_html=True)
