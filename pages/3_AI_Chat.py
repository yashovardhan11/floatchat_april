import logging
import sys
from html import escape
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="AI Chat — FloatChat",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from utils.helpers import GLOBAL_CSS, retrieval_steps_html

# ── CSS first, immediately after set_page_config ──────────────────────────────
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
st.markdown("""<style>
div[data-testid="stButton"] > button {
  min-height: 52px !important;
  padding: 0.8rem 1rem !important;
  font-size: 0.98rem !important;
  font-weight: 600 !important;
  border-radius: 12px !important;
}
div[data-testid="stExpander"] summary {
  font-size: 0.98rem !important;
}
div[data-testid="stDataFrame"] {
  font-size: 0.96rem !important;
}
div[data-testid="stChatInput"] {
  max-width: 880px !important;
  margin: 0 auto !important;
}
div[data-testid="stChatInput"] textarea {
  min-height: 48px !important;
  padding: 0.8rem 1rem !important;
  font-size: 0.96rem !important;
  font-weight: 500 !important;
  line-height: 1.45 !important;
  letter-spacing: 0.01em !important;
  color: #EAF8FF !important;
}
div[data-testid="stChatInput"] button {
  min-height: 40px !important;
}
section[data-testid="stBottom"] {
  background: #020B18 !important;
  border-top: 1px solid #1A3A5C !important;
  padding: 0.72rem 2rem !important;
}
</style>""", unsafe_allow_html=True)

# ─── Service init ──────────────────────────────────────────────────────────────

def _init_services():
    if "db" not in st.session_state or st.session_state.db is None:
        try:
            from config.settings import load_config
            from database.connection import DatabaseManager
            from database.vector_store import ChromaVectorStore
            from rag.groq_rag import OceanRAG
            from rag.hybrid_retriever import HybridOceanRetriever
            from rag.query_processor import QueryProcessor
            config = load_config()
            st.session_state.config = config
            st.session_state.db = DatabaseManager(config)
            st.session_state.vs = ChromaVectorStore(config)
            st.session_state.rag = OceanRAG(config)
            st.session_state.retriever = HybridOceanRetriever(
                st.session_state.db, st.session_state.vs)
            st.session_state.qp = QueryProcessor()
        except Exception as e:
            st.error(f"Init failed: {e}")
            return False
    elif "retriever" not in st.session_state:
        try:
            from rag.hybrid_retriever import HybridOceanRetriever
            from rag.query_processor import QueryProcessor
            st.session_state.retriever = HybridOceanRetriever(
                st.session_state.db, st.session_state.vs)
            st.session_state.qp = QueryProcessor()
        except Exception as e:
            st.error(f"Retriever init failed: {e}")
            return False
    return True

if not _init_services():
    st.stop()

db        = st.session_state.db
rag       = st.session_state.rag
retriever = st.session_state.retriever
qp        = st.session_state.qp

# ─── Session state ─────────────────────────────────────────────────────────────

if "chat_history"          not in st.session_state: st.session_state.chat_history = []
if "retrieved_profiles"    not in st.session_state: st.session_state.retrieved_profiles = []
if "last_retrieval_details" not in st.session_state: st.session_state.last_retrieval_details = {}


def _safe_html_text(text: str) -> str:
    return escape(text or "").replace("\n", "<br>")

# ─── TOP BAR ──────────────────────────────────────────────────────────────────

provider  = "Groq" if (rag and rag.groq_client) else ("OpenAI" if (rag and rag.openai_client) else "None")
model_str = "llama-3.3-70b" if provider == "Groq" else ("gpt-4o-mini" if provider == "OpenAI" else "No key")

top_col1, top_col2 = st.columns([4, 2])
with top_col1:
    st.markdown(
        '<div style="background:#020B18;border-bottom:1px solid #1A3A5C;'
        'padding:0.875rem 2rem;display:flex;align-items:center;gap:1rem;">'
        '<span style="color:#8BAABF;font-size:0.95rem;cursor:pointer;font-weight:500;"'
        ' onclick="window.location=\'/\'">&#8592; Home</span>'
        '<span style="color:#1A3A5C;">|</span>'
        '<span style="font-size:1.1rem;font-weight:700;color:#F0F8FF;">&#129302; AI Chat</span>'
        '</div>',
        unsafe_allow_html=True,
    )
with top_col2:
    st.markdown(
        '<div style="background:#020B18;border-bottom:1px solid #1A3A5C;'
        'padding:0.875rem 2rem;display:flex;align-items:center;'
        'justify-content:flex-end;gap:10px;">'
        '<span style="background:rgba(245,166,35,0.1);border:1px solid rgba(245,166,35,0.3);'
        f'color:#F5A623;font-size:0.8rem;font-weight:700;padding:5px 12px;border-radius:20px;">'
        f'{provider} &middot; {model_str}</span>'
        '</div>',
        unsafe_allow_html=True,
    )

nb1, nb2, nb3 = st.columns([1, 1, 4])
with nb1:
    if st.button("← Home", key="chat_home"):
        st.switch_page("Home.py")
with nb2:
    if st.button("🗑 Clear", key="clear_chat"):
        st.session_state.chat_history = []
        st.session_state.retrieved_profiles = []
        st.session_state.last_retrieval_details = {}
        st.rerun()

# ─── CHAT BODY ────────────────────────────────────────────────────────────────

body_left, body_col, body_right = st.columns([1, 8, 1])
with body_col:
    # Empty state
    if not st.session_state.chat_history:
        st.markdown(
            '<div style="text-align:center;padding:3rem 1rem;">'
            '<div style="font-size:3.3rem;margin-bottom:1rem;">&#127754;</div>'
            '<h2 style="color:#F0F8FF;font-size:1.72rem;font-weight:700;margin:0;">'
            'Ask anything about ocean data</h2>'
            '<p style="color:#8BAABF;font-size:1rem;margin:0.7rem 0 2rem;line-height:1.7;">'
            'Powered by hybrid geospatial-semantic retrieval</p>'
            '</div>',
            unsafe_allow_html=True,
        )

        CHIPS = [
            "🌡 Temperature near Arabian Sea",
            "🧂 Salinity in Bay of Bengal",
            "💧 Oxygen levels Indian Ocean",
            "📍 Show recent float profiles",
        ]
        chip_cols = st.columns(2)
        for i, chip in enumerate(CHIPS):
            with chip_cols[i % 2]:
                if st.button(chip, key=f"chip_{i}", use_container_width=True):
                    st.session_state._pending_query = chip
                    st.rerun()

    # ─── Render chat history ──────────────────────────────────────────────────

    for i, msg in enumerate(st.session_state.chat_history):
        role    = msg.get("role")
        content = msg.get("content", "")
        is_last = (i == len(st.session_state.chat_history) - 1)
        content_html = _safe_html_text(content)

        if role == "user":
            st.markdown(
                '<div style="display:flex;justify-content:flex-end;margin-bottom:1.5rem;">'
                '<div style="background:linear-gradient(135deg,rgba(0,198,255,0.13),rgba(0,114,255,0.13));'
                'border:1px solid rgba(0,198,255,0.27);border-radius:16px 16px 4px 16px;'
                f'padding:1rem 1.35rem;max-width:72%;color:#F0F8FF;font-size:1rem;'
                f'line-height:1.72;">{content_html}</div>'
                '</div>',
                unsafe_allow_html=True,
            )

        elif role == "assistant":
            st.markdown(
                '<div style="display:flex;gap:0.875rem;margin-bottom:1.5rem;align-items:flex-start;">'
                '<div style="width:36px;height:36px;background:linear-gradient(135deg,#00C6FF,#0072FF);'
                'border-radius:50%;display:flex;align-items:center;justify-content:center;'
                'font-size:1rem;flex-shrink:0;margin-top:2px;">&#127754;</div>'
                '<div style="background:#0A1F3A;border:1px solid #1A3A5C;'
                'border-radius:4px 16px 16px 16px;padding:1.1rem 1.35rem;max-width:86%;'
                f'color:#F0F8FF;font-size:1rem;line-height:1.8;">{content_html}</div>'
                '</div>',
                unsafe_allow_html=True,
            )

            # Show retrieval details only for last AI message
            if is_last and st.session_state.last_retrieval_details:
                details = st.session_state.last_retrieval_details
                results = st.session_state.retrieved_profiles
                n_ret = details.get("final_count", 0)

                det_col1, det_col2, det_col3 = st.columns([0.5, 4, 0.5])
                with det_col2:
                    with st.expander(f"🔍 Retrieval Details ({n_ret} profiles)", expanded=False):
                        st.markdown(
                            retrieval_steps_html(
                                details.get("stage1_count", 0),
                                details.get("stage2_count", 0),
                                details.get("final_count", 0),
                            ),
                            unsafe_allow_html=True,
                        )

                        if results:
                            import pandas as pd

                            rows = []
                            for r in results[:10]:
                                pr   = r.get("profile", {})
                                meta = r.get("metadata", {})
                                fid  = pr.get("float_id") or meta.get("float_id", "?")
                                dval = pr.get("measurement_date", "")
                                dstr = dval.strftime("%d %b %Y") if hasattr(dval, "strftime") else str(dval)[:10]
                                lat  = pr.get("latitude", "?")
                                lon  = pr.get("longitude", "?")
                                score = r.get("final_score", r.get("similarity_score", 0))
                                rows.append({
                                    "Float": fid,
                                    "Date": dstr,
                                    "Location": f"{lat:.2f}°N {lon:.2f}°E" if isinstance(lat, float) else "—",
                                    "Score": f"{score:.3f}",
                                })
                            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                        else:
                            st.info("No profiles were retrieved for this query.")

                        ac1, ac2, _ = st.columns([1, 1, 3])
                        with ac1:
                            if st.button("📄 PDF Report", key=f"pdf_{i}", use_container_width=True):
                                st.session_state._generate_pdf = True
                        with ac2:
                            if st.button("📊 View Charts", key=f"viz_{i}", use_container_width=True):
                                st.switch_page("pages/4_Visualizations.py")

# ─── PDF generation ───────────────────────────────────────────────────────────

if st.session_state.get("_generate_pdf"):
    st.session_state._generate_pdf = False
    try:
        import tempfile
        import pandas as pd
        from reports.pdf_generator import OceanReportGenerator

        results = st.session_state.retrieved_profiles
        pids = [r.get("profile", {}).get("id") for r in results
                if r.get("profile", {}).get("id")]
        pids = [p for p in pids if p is not None]

        profiles_df = db.get_profiles_by_ids(pids) if pids else pd.DataFrame()
        meas_dfs = []
        for pid in pids[:5]:
            mdf = db.get_measurements_by_profile(pid)
            if not mdf.empty:
                meas_dfs.append(mdf)
        measurements_df = pd.concat(meas_dfs, ignore_index=True) if meas_dfs else pd.DataFrame()

        last_query = next(
            (m["content"] for m in reversed(st.session_state.chat_history)
             if m["role"] == "user"),
            "Ocean data analysis",
        )
        stats = db.get_statistics()
        ai_summary = rag.generate_report_summary(last_query, profiles_df, stats)

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            out_path = tmp.name
        OceanReportGenerator().generate(
            last_query, profiles_df, measurements_df, ai_summary, out_path)

        with open(out_path, "rb") as f:
            pdf_bytes = f.read()

        st.download_button("⬇  Download PDF Report", data=pdf_bytes,
                           file_name="floatchat_report.pdf",
                           mime="application/pdf", key="pdf_dl")
        st.success("✅ PDF report generated!")
    except Exception as e:
        logger.exception("PDF failed")
        st.error(f"PDF generation failed: {e}")

# ─── Pending chip query ───────────────────────────────────────────────────────

if "_pending_query" in st.session_state:
    pending = st.session_state.pop("_pending_query")
    st.session_state.chat_history.append({"role": "user", "content": pending})
    st.session_state._process_query = pending
    st.rerun()

# ─── Chat input (fixed bottom) ────────────────────────────────────────────────

user_input = st.chat_input("")

if user_input:
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    st.session_state._process_query = user_input
    st.rerun()

# ─── Process query ────────────────────────────────────────────────────────────

if "_process_query" in st.session_state:
    query = st.session_state.pop("_process_query")

    # Thinking indicator
    st.markdown(
        '<div style="display:flex;gap:0.875rem;align-items:center;'
        'margin:0 auto 1rem;max-width:880px;padding:0 2rem;">'
        '<div style="width:36px;height:36px;background:linear-gradient(135deg,#00C6FF,#0072FF);'
        'border-radius:50%;display:flex;align-items:center;justify-content:center;'
        'font-size:1rem;flex-shrink:0;">&#127754;</div>'
        '<div style="background:#0A1F3A;border:1px solid #1A3A5C;'
        'border-radius:4px 16px 16px 16px;padding:1rem 1.35rem;'
        'color:#8BAABF;font-size:0.95rem;font-style:italic;">Analyzing your query...</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    with st.spinner(""):
        try:
            filters = qp.process(query)
            retrieval_result = retriever.retrieve(query, filters, k=10)
            results = retrieval_result.get("results", [])
            st.session_state.retrieved_profiles = results
            st.session_state.last_retrieval_details = retrieval_result

            history_for_rag = [
                m for m in st.session_state.chat_history[:-1]
                if m["role"] in ("user", "assistant")
            ][-6:]
            answer = rag.answer(query, results, chat_history=history_for_rag)
            st.session_state.chat_history.append({"role": "assistant", "content": answer})
        except Exception as e:
            logger.exception("Query failed")
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": f"I encountered an error: {e}",
            })
    st.rerun()
