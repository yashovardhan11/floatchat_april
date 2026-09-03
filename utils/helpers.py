import logging
import math
from datetime import datetime

logger = logging.getLogger(__name__)

PARAM_UNITS = {
    "temperature": "°C",
    "salinity": "PSU",
    "pressure": "dbar",
    "depth": "m",
    "oxygen": "µmol/kg",
    "nitrate": "µmol/kg",
    "ph": "",
    "chlorophyll": "mg/m³",
    "density": "kg/m³",
    "potential_temperature": "°C",
    "mixed_layer_depth": "m",
}

QUALITY_FLAG_LABELS = {
    1: "Good data",
    2: "Probably good data",
    3: "Bad data potentially correctable",
    4: "Bad data",
    8: "Estimated value",
    9: "Missing value",
}


def format_coordinates(lat: float, lon: float) -> str:
    """Format lat/lon as '23.4°N, 68.2°E'."""
    lat_dir = "N" if lat >= 0 else "S"
    lon_dir = "E" if lon >= 0 else "W"
    return f"{abs(lat):.2f}°{lat_dir}, {abs(lon):.2f}°{lon_dir}"


def format_date(dt) -> str:
    """Format datetime as '15 July 2024'."""
    if dt is None:
        return "Unknown"
    if hasattr(dt, "strftime"):
        return dt.strftime("%d %B %Y")
    try:
        return datetime.fromisoformat(str(dt)[:19]).strftime("%d %B %Y")
    except Exception:
        return str(dt)[:10]


def format_parameter_value(value, parameter: str) -> str:
    """Add correct units to a parameter value."""
    if value is None:
        return "—"
    try:
        fval = float(value)
        unit = PARAM_UNITS.get(parameter, "")
        unit_str = f" {unit}" if unit else ""
        return f"{fval:.2f}{unit_str}"
    except (TypeError, ValueError):
        return str(value)


def quality_flag_label(flag: int) -> str:
    """Return human-readable quality flag description."""
    return QUALITY_FLAG_LABELS.get(flag, f"Flag {flag}")


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Simple Euclidean distance in degree-space (for scoring, not navigation)."""
    return math.sqrt((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2)


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate string with ellipsis if over max_length."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def create_profile_display_name(profile) -> str:
    """Create a human-readable label like 'Float 1234 · Cycle 45 · 15 Jul 2024'."""
    if hasattr(profile, "get"):
        float_id = profile.get("float_id", "Unknown")
        cycle = profile.get("cycle_number", "?")
        date_val = profile.get("measurement_date")
    else:
        float_id = getattr(profile, "float_id", "Unknown")
        cycle = getattr(profile, "cycle_number", "?")
        date_val = getattr(profile, "measurement_date", None)

    date_str = "Unknown"
    if date_val is not None:
        if hasattr(date_val, "strftime"):
            date_str = date_val.strftime("%d %b %Y")
        else:
            try:
                date_str = datetime.fromisoformat(str(date_val)[:19]).strftime("%d %b %Y")
            except Exception:
                date_str = str(date_val)[:10]

    return f"Float {float_id} · Cycle {cycle} · {date_str}"


# ─── HTML UI Component Functions ──────────────────────────────────────────────
# IMPORTANT: Every function below returns a plain str that starts with '<'.
# No leading whitespace — Markdown's 4-space indent rule would turn it into
# a code block and render it as raw text instead of HTML.

GLOBAL_CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

* { font-family: 'Inter', sans-serif !important; box-sizing: border-box; }

html, body, [class*="css"], .stApp, .main {
  background-color: #020B18 !important;
  color: #F0F8FF !important;
}

[data-testid="collapsedControl"] { display: none !important; }
[data-testid="stSidebar"] { display: none !important; }

.main .block-container {
  padding: 0 !important;
  max-width: 100% !important;
}

header[data-testid="stHeader"] { display: none !important; }
footer { display: none !important; }

div[data-testid="stButton"] > button {
  font-family: 'Inter', sans-serif !important;
  font-weight: 600 !important;
  border-radius: 8px !important;
  transition: all 0.2s ease !important;
  border: none !important;
}

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #020B18; }
::-webkit-scrollbar-thumb { background: #1A3A5C; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #00C6FF; }

div[data-testid="metric-container"] {
  background: #0A1F3A !important;
  border: 1px solid #1A3A5C !important;
  border-radius: 12px !important;
  padding: 1.25rem 1.5rem !important;
}
div[data-testid="metric-container"] label {
  color: #8BAABF !important;
  font-size: 0.75rem !important;
  font-weight: 500 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.08em !important;
}
div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
  color: #F0F8FF !important;
  font-size: 1.8rem !important;
  font-weight: 700 !important;
}

div[data-testid="stDataFrame"] {
  border: 1px solid #1A3A5C !important;
  border-radius: 12px !important;
  overflow: hidden !important;
}

div[data-testid="stSelectbox"] > div {
  background: #061428 !important;
  border: 1px solid #1A3A5C !important;
  border-radius: 8px !important;
  color: #F0F8FF !important;
}

div[data-testid="stTextInput"] > div > div {
  background: #061428 !important;
  border: 1px solid #1A3A5C !important;
  border-radius: 8px !important;
  color: #F0F8FF !important;
}

.stTabs [data-baseweb="tab-list"] {
  background: transparent !important;
  border-bottom: 1px solid #1A3A5C !important;
  gap: 0 !important;
  padding: 0 !important;
}
.stTabs [data-baseweb="tab"] {
  background: transparent !important;
  border: none !important;
  border-bottom: 2px solid transparent !important;
  border-radius: 0 !important;
  color: #8BAABF !important;
  font-size: 0.875rem !important;
  font-weight: 500 !important;
  padding: 0.75rem 1.5rem !important;
  transition: all 0.15s !important;
}
.stTabs [data-baseweb="tab"]:hover {
  color: #F0F8FF !important;
  background: rgba(0,198,255,0.05) !important;
}
.stTabs [aria-selected="true"] {
  color: #00C6FF !important;
  border-bottom: 2px solid #00C6FF !important;
  font-weight: 600 !important;
}

div[data-testid="stExpander"] {
  background: #0A1F3A !important;
  border: 1px solid #1A3A5C !important;
  border-radius: 10px !important;
  margin: 1.5rem 0 !important;
}
div[data-testid="stExpander"] summary {
  color: #8BAABF !important;
  font-size: 0.875rem !important;
  padding: 0.75rem 1rem !important;
}

div[data-testid="stProgressBar"] > div {
  background: linear-gradient(90deg, #00C6FF, #0072FF) !important;
  border-radius: 4px !important;
}

div[data-testid="stSuccess"] {
  background: rgba(0,230,118,0.1) !important;
  border: 1px solid rgba(0,230,118,0.3) !important;
  border-radius: 8px !important;
  color: #00E676 !important;
}
div[data-testid="stError"] {
  background: rgba(255,82,82,0.1) !important;
  border: 1px solid rgba(255,82,82,0.3) !important;
  border-radius: 8px !important;
  color: #FF5252 !important;
}
div[data-testid="stWarning"] {
  background: rgba(255,179,0,0.1) !important;
  border: 1px solid rgba(255,179,0,0.3) !important;
  border-radius: 8px !important;
  color: #FFB300 !important;
}
div[data-testid="stInfo"] {
  background: rgba(0,198,255,0.08) !important;
  border: 1px solid rgba(0,198,255,0.2) !important;
  border-radius: 8px !important;
  color: #00C6FF !important;
}

div[data-testid="stDateInput"] input {
  background: #061428 !important;
  border: 1px solid #1A3A5C !important;
  border-radius: 8px !important;
  color: #F0F8FF !important;
}

div[data-testid="stMultiSelect"] > div {
  background: #061428 !important;
  border: 1px solid #1A3A5C !important;
  border-radius: 8px !important;
}

div[data-testid="stDownloadButton"] > button {
  background: transparent !important;
  border: 1px solid #00C6FF !important;
  color: #00C6FF !important;
  border-radius: 8px !important;
  font-weight: 500 !important;
}
div[data-testid="stDownloadButton"] > button:hover {
  background: rgba(0,198,255,0.1) !important;
}

div[data-testid="stChatInput"] textarea {
  background: #061428 !important;
  border: 1px solid #1A3A5C !important;
  border-radius: 12px !important;
  color: #F0F8FF !important;
}
div[data-testid="stChatInput"]:focus-within {
  border-color: #00C6FF !important;
  box-shadow: 0 0 0 2px rgba(0,198,255,0.15) !important;
}

@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(255,179,0,0.4); }
  70% { box-shadow: 0 0 0 10px rgba(255,179,0,0); }
  100% { box-shadow: 0 0 0 0 rgba(255,179,0,0); }
}
@keyframes pulse-green {
  0% { box-shadow: 0 0 0 0 rgba(0,230,118,0.4); }
  70% { box-shadow: 0 0 0 10px rgba(0,230,118,0); }
  100% { box-shadow: 0 0 0 0 rgba(0,230,118,0); }
}
</style>"""


def page_header(title: str, subtitle: str, icon: str) -> str:
    """Render a page header bar with icon, title and subtitle."""
    return (
        '<div style="background:linear-gradient(135deg,#061428 0%,#0A1F3A 100%);'
        'border-bottom:1px solid #1A3A5C;padding:1.5rem 2.5rem;'
        'margin-bottom:2rem;display:flex;align-items:center;gap:1rem;">'
        f'<span style="font-size:2rem">{icon}</span>'
        '<div>'
        f'<h1 style="margin:0;font-size:1.6rem;font-weight:700;color:#F0F8FF;'
        f'letter-spacing:-0.03em;">{title}</h1>'
        f'<p style="margin:0;font-size:0.875rem;color:#8BAABF;margin-top:2px;">{subtitle}</p>'
        '</div>'
        '</div>'
    )


def stat_card(label: str, value: str, icon: str,
              color: str = "#00C6FF", sublabel: str = None) -> str:
    """Render a stat card with colored left border."""
    sublabel_html = (
        f'<p style="margin:0.25rem 0 0;font-size:0.75rem;color:#4A6580;">{sublabel}</p>'
        if sublabel else ""
    )
    return (
        f'<div style="background:#0A1F3A;border:1px solid #1A3A5C;'
        f'border-left:3px solid {color};border-radius:12px;'
        f'padding:1.25rem 1.5rem;height:100%;">'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;">'
        f'<div>'
        f'<p style="margin:0;font-size:0.7rem;color:#8BAABF;text-transform:uppercase;'
        f'letter-spacing:0.1em;font-weight:500;">{label}</p>'
        f'<p style="margin:0.3rem 0 0;font-size:1.8rem;font-weight:700;color:#F0F8FF;'
        f'letter-spacing:-0.03em;line-height:1;">{value}</p>'
        f'{sublabel_html}'
        f'</div>'
        f'<span style="font-size:1.5rem;opacity:0.6;">{icon}</span>'
        f'</div>'
        f'</div>'
    )


def status_pill(label: str, status: str, active: bool = True) -> str:
    """Render an inline status pill with colored dot."""
    color = "#00E676" if active else "#FFB300"
    glow = f"box-shadow:0 0 6px {color};" if active else ""
    return (
        '<span style="display:inline-flex;align-items:center;gap:6px;'
        'background:rgba(10,31,58,0.8);border:1px solid #1A3A5C;'
        'border-radius:20px;padding:4px 12px;font-size:0.75rem;color:#8BAABF;">'
        f'<span style="width:7px;height:7px;border-radius:50%;'
        f'background:{color};{glow}flex-shrink:0;"></span>'
        f'{label}:&nbsp;<span style="color:#F0F8FF;font-weight:500;">{status}</span>'
        '</span>'
    )


def section_divider(title: str = None) -> str:
    """Render a horizontal divider with optional section title."""
    if title:
        return (
            '<div style="display:flex;align-items:center;gap:1rem;margin:1.5rem 0 1rem;">'
            f'<span style="font-size:0.7rem;font-weight:600;color:#4A6580;'
            f'text-transform:uppercase;letter-spacing:0.12em;white-space:nowrap;">{title}</span>'
            '<div style="flex:1;height:1px;background:#1A3A5C;"></div>'
            '</div>'
        )
    return '<div style="height:1px;background:#1A3A5C;margin:1.5rem 0;"></div>'


def nav_card(icon: str, title: str, description: str,
             badge: str = None, badge_color: str = "#00C6FF") -> str:
    """Render a navigation card. Must be wrapped in st.markdown(..., unsafe_allow_html=True)."""
    badge_html = ""
    if badge:
        badge_html = (
            f'<span style="background:rgba(0,198,255,0.1);border:1px solid rgba(0,198,255,0.2);'
            f'color:{badge_color};font-size:0.65rem;font-weight:600;padding:2px 8px;'
            f'border-radius:20px;text-transform:uppercase;letter-spacing:0.08em;">{badge}</span>'
        )
    return (
        '<div style="background:#0A1F3A;border:1px solid #1A3A5C;border-radius:16px;'
        'padding:1.5rem;cursor:pointer;transition:all 0.2s ease;height:140px;'
        'display:flex;flex-direction:column;justify-content:space-between;">'
        f'<div style="font-size:1.8rem">{icon}</div>'
        '<div>'
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">'
        f'<span style="font-size:0.95rem;font-weight:600;color:#F0F8FF;">{title}</span>'
        f'{badge_html}'
        f'</div>'
        f'<p style="margin:0;font-size:0.78rem;color:#8BAABF;line-height:1.4;">{description}</p>'
        '</div>'
        '</div>'
    )


def retrieval_steps_html(stage1: int, stage2: int, final: int) -> str:
    """Render the 3-stage hybrid retrieval step indicator."""
    badge_style = (
        "background:rgba(0,198,255,0.1);border:1px solid rgba(0,198,255,0.2);"
        "border-radius:6px;padding:3px 10px;font-size:0.7rem;color:#00C6FF;white-space:nowrap;"
    )
    arrow = '<span style="color:#4A6580;font-size:0.75rem;">&#8594;</span>'
    return (
        '<div style="display:flex;align-items:center;gap:0.4rem;'
        'margin:0.5rem 0 0.75rem 2.75rem;flex-wrap:wrap;">'
        f'<span style="{badge_style}">&#128205; Stage 1: {stage1} profiles (spatial)</span>'
        f'{arrow}'
        f'<span style="{badge_style}">&#128269; Stage 2: {stage2} profiles (semantic)</span>'
        f'{arrow}'
        f'<span style="{badge_style}">&#9889; Stage 3: top {final} (40/60 fusion)</span>'
        '</div>'
    )
