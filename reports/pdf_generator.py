import logging
import math
import unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# ─── Color constants ──────────────────────────────────────────────────────────
NAVY = (2, 11, 24)          # #020B18
DARK_NAVY = (6, 20, 40)     # #061428
CARD = (10, 31, 58)         # #0A1F3A
CYAN = (0, 198, 255)        # #00C6FF
GOLD = (245, 166, 35)       # #F5A623
WHITE = (240, 248, 255)     # #F0F8FF
LIGHT_GREY = (230, 238, 245)
MID_GREY = (139, 170, 191)  # #8BAABF
SUCCESS = (0, 230, 118)     # #00E676
WARNING = (255, 179, 0)     # #FFB300
ERROR = (255, 82, 82)       # #FF5252


class OceanReportGenerator:
    """Generates premium-styled PDF reports for ARGO ocean data analysis."""

    _UNICODE_REPLACEMENTS = str.maketrans(
        {
            "\u2013": "-",
            "\u2014": "-",
            "\u2018": "'",
            "\u2019": "'",
            "\u201c": '"',
            "\u201d": '"',
            "\u2022": "-",
            "\u2026": "...",
            "\u2212": "-",
            "\u00a0": " ",
        }
    )

    def __init__(self) -> None:
        pass

    @staticmethod
    def _get_ist_time() -> datetime:
        """Get current time in IST (Indian Standard Time, UTC+5:30)."""
        ist = timezone(timedelta(hours=5, minutes=30))
        return datetime.now(ist)

    def generate(
        self,
        query: str,
        profiles_df: pd.DataFrame,
        measurements_df: pd.DataFrame,
        ai_summary: str,
        output_path: str,
    ) -> str:
        """Build and save the complete PDF report. Returns filepath."""
        from fpdf import FPDF

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)

        # ── Section 1: Cover Page ──
        self._add_cover_page(pdf, query, profiles_df)

        # ── Section 2: Executive Summary ──
        self._add_executive_summary(pdf, ai_summary, profiles_df)

        # ── Section 3: Statistical Summary ──
        self._add_statistics_table(pdf, measurements_df)

        # ── Section 4: Profile Details ──
        self._add_profile_details(pdf, profiles_df, measurements_df)

        # ── Section 5: Data Quality ──
        self._add_data_quality(pdf, measurements_df)

        # Write footers on all pages
        total_pages = pdf.page

        pdf.output(output_path)
        logger.info("PDF report saved to %s (%d pages)", output_path, total_pages)
        return output_path

    # ─── Section builders ─────────────────────────────────────────────────────

    def _add_cover_page(self, pdf, query: str, profiles_df: pd.DataFrame) -> None:
        from fpdf import FPDF

        self._ensure_new_page(pdf, check_content=False)  # Cover page always needs fresh page
        # Navy background
        pdf.set_fill_color(*NAVY)
        pdf.rect(0, 0, 210, 297, "F")

        # Title
        pdf.set_y(60)
        pdf.set_font("Helvetica", "B", 42)
        pdf.set_text_color(*CYAN)
        pdf.cell(0, 20, "FloatChat", align="C", ln=True)

        pdf.set_font("Helvetica", "", 16)
        pdf.set_text_color(*WHITE)
        pdf.cell(0, 10, "ARGO Oceanographic Data Report", align="C", ln=True)

        # Cyan divider line
        pdf.set_draw_color(*CYAN)
        pdf.set_line_width(0.8)
        pdf.line(30, pdf.get_y() + 6, 180, pdf.get_y() + 6)
        pdf.ln(16)

        # Query (clean up leading/trailing special chars)
        clean_query = query.strip('?! ') if query else "Ocean data analysis"
        pdf.set_font("Helvetica", "I", 11)
        pdf.set_text_color(*MID_GREY)
        pdf.multi_cell(0, 8, self._safe_text(f'Query: "{clean_query}"'), align="C")
        pdf.ln(10)

        # Metadata box
        now = self._get_ist_time()
        n_profiles = len(profiles_df) if not profiles_df.empty else 0
        float_ids = []
        if not profiles_df.empty and "float_id" in profiles_df.columns:
            float_ids = profiles_df["float_id"].unique().tolist()[:10]

        meta_lines = [
            f"Generated: {now.strftime('%d %B %Y at %H:%M IST')}",
            f"Profiles Analyzed: {n_profiles}",
            f"Float IDs: {', '.join(str(f) for f in float_ids) if float_ids else 'N/A'}",
        ]
        for line in meta_lines:
            pdf.set_font("Helvetica", "", 11)
            pdf.set_text_color(*WHITE)
            pdf.cell(0, 9, self._safe_text(line), align="C", ln=True)

        self._add_footer(pdf, pdf.page, 0)

    def _add_executive_summary(
        self, pdf, ai_summary: str, profiles_df: pd.DataFrame
    ) -> None:
        self._ensure_new_page(pdf, check_content=True)
        self._add_section_heading(pdf, "Executive Summary")

        # AI summary text with markdown support
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(30, 30, 30)
        self._add_markdown_text(pdf, ai_summary or "No AI summary available.", font_size=10)
        pdf.ln(8)

        # Key metrics
        if not profiles_df.empty:
            n_profiles = len(profiles_df)
            date_min = date_max = "N/A"
            if "measurement_date" in profiles_df.columns:
                dates = profiles_df["measurement_date"].dropna()
                if not dates.empty:
                    date_min = str(dates.min())[:10]
                    date_max = str(dates.max())[:10]

            lat_range = lon_range = "N/A"
            if "latitude" in profiles_df.columns:
                lat_range = f"{profiles_df['latitude'].min():.1f}° to {profiles_df['latitude'].max():.1f}°"
            if "longitude" in profiles_df.columns:
                lon_range = f"{profiles_df['longitude'].min():.1f}° to {profiles_df['longitude'].max():.1f}°"

            metrics = [
                ("Total Profiles", str(n_profiles)),
                ("Date Range", f"{date_min} to {date_max}"),
                ("Latitude Coverage", lat_range),
                ("Longitude Coverage", lon_range),
            ]
            self._add_metrics_row(pdf, metrics)

        self._add_footer(pdf, pdf.page, 0)

    def _add_statistics_table(
        self, pdf, measurements_df: pd.DataFrame
    ) -> None:
        self._ensure_new_page(pdf, check_content=True)
        self._add_section_heading(pdf, "Statistical Summary")

        params = [
            ("temperature", "°C"),
            ("salinity", "PSU"),
            ("pressure", "dbar"),
            ("depth", "m"),
            ("oxygen", "µmol/kg"),
            ("nitrate", "µmol/kg"),
            ("ph", ""),
            ("chlorophyll", "mg/m³"),
        ]

        headers = ["Parameter", "Min", "Max", "Mean", "Std Dev", "Unit"]
        rows = []

        if not measurements_df.empty:
            for param, unit in params:
                if param in measurements_df.columns:
                    col = measurements_df[param].dropna()
                    if not col.empty:
                        rows.append([
                            param.replace("_", " ").title(),
                            f"{col.min():.3f}",
                            f"{col.max():.3f}",
                            f"{col.mean():.3f}",
                            f"{col.std():.3f}",
                            unit,
                        ])

        if rows:
            self.add_table(pdf, headers, rows)
        else:
            pdf.set_font("Helvetica", "I", 10)
            pdf.set_text_color(120, 120, 120)
            pdf.cell(0, 8, "No measurement data available.", ln=True)

        self._add_footer(pdf, pdf.page, 0)

    def _add_profile_details(
        self,
        pdf,
        profiles_df: pd.DataFrame,
        measurements_df: pd.DataFrame,
    ) -> None:
        self._ensure_new_page(pdf, check_content=True)
        self._add_section_heading(pdf, "Profile Details")

        if profiles_df.empty:
            pdf.set_font("Helvetica", "I", 10)
            pdf.cell(0, 8, "No profiles to display.", ln=True)
            self._add_footer(pdf, pdf.page, 0)
            return

        target_depths = [0, 10, 100, 500, 1000]
        display_profiles = profiles_df.head(10)

        for _, profile in display_profiles.iterrows():
            pdf.ln(4)
            float_id = profile.get("float_id", "Unknown")
            date_val = profile.get("measurement_date", "")
            if hasattr(date_val, "strftime"):
                date_str = date_val.strftime("%d %b %Y")
            else:
                date_str = str(date_val)[:10]
            lat = profile.get("latitude", 0)
            lon = profile.get("longitude", 0)
            lat_dir = "N" if lat >= 0 else "S"
            lon_dir = "E" if lon >= 0 else "W"

            # Sub-heading
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*CARD)
            pdf.cell(
                0,
                7,
                self._safe_text(
                    f"Float {float_id}  |  {date_str}  |  {abs(lat):.2f}°{lat_dir}, {abs(lon):.2f}°{lon_dir}"
                ),
                ln=True,
            )

            # Measurement snapshot at target depths
            if not measurements_df.empty and "profile_id" in measurements_df.columns:
                pid = profile.get("id")
                p_meas = measurements_df[measurements_df["profile_id"] == pid]
                if not p_meas.empty and "depth" in p_meas.columns:
                    headers = ["Depth (m)", "Temp (°C)", "Salinity (PSU)", "O2 (µmol/kg)"]
                    rows = []
                    for td in target_depths:
                        closest = p_meas.iloc[(p_meas["depth"] - td).abs().argsort()[:1]]
                        if not closest.empty:
                            r = closest.iloc[0]
                            rows.append([
                                f"{r.get('depth', td):.0f}",
                                self._format_numeric(r.get("temperature"), decimals=2),
                                self._format_numeric(r.get("salinity"), decimals=2),
                                self._format_numeric(r.get("oxygen"), decimals=1),
                            ])
                    if rows:
                        self.add_table(pdf, headers, rows, font_size=9)

            # Quality indicator
            qflag = profile.get("quality_flag", 1)
            qcolor = SUCCESS if qflag == 1 else (WARNING if qflag == 2 else ERROR)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*qcolor)
            pdf.cell(0, 5, f"Quality flag: {qflag}", ln=True)
            pdf.set_draw_color(*MID_GREY)
            pdf.set_line_width(0.3)
            pdf.line(10, pdf.get_y() + 1, 200, pdf.get_y() + 1)
            pdf.ln(4)

        self._add_footer(pdf, pdf.page, 0)

    def _add_data_quality(
        self, pdf, measurements_df: pd.DataFrame
    ) -> None:
        self._ensure_new_page(pdf, check_content=True)
        self._add_section_heading(pdf, "Data Quality")

        if measurements_df.empty:
            pdf.set_font("Helvetica", "I", 10)
            pdf.cell(0, 8, "No measurement data available.", ln=True)
            self._add_footer(pdf, pdf.page, 0)
            return

        # Quality flag distribution
        if "quality_flag" in measurements_df.columns:
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(*CARD)
            pdf.cell(0, 8, "Quality Flag Distribution", ln=True)
            pdf.ln(2)

            flag_counts = measurements_df["quality_flag"].value_counts().sort_index()
            total = len(measurements_df)
            headers = ["Quality Flag", "Count", "Percentage"]
            rows = [
                [str(flag), str(count), f"{count / total * 100:.1f}%"]
                for flag, count in flag_counts.items()
            ]
            self.add_table(pdf, headers, rows)

        pdf.ln(6)

        # Anomaly counts by parameter
        if "anomaly_flag" in measurements_df.columns:
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(*CARD)
            pdf.cell(0, 8, "Anomaly Summary", ln=True)
            pdf.ln(2)

            total = len(measurements_df)
            anomaly_total = int(measurements_df["anomaly_flag"].sum())
            pdf.set_font("Helvetica", "", 10)
            pct = anomaly_total / total * 100 if total > 0 else 0
            pdf.cell(0, 7, f"Total anomalies flagged: {anomaly_total} ({pct:.1f}%)", ln=True)

        self._add_footer(pdf, pdf.page, 0)

    # ─── Reusable components ──────────────────────────────────────────────────

    def _add_section_heading(self, pdf, text: str) -> None:
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(*NAVY)
        pdf.cell(0, 12, self._safe_text(text), ln=True)
        pdf.set_draw_color(*CYAN)
        pdf.set_line_width(0.6)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(6)

    def add_section_heading(self, text: str) -> None:
        pass  # Interface method — internal use only via _add_section_heading

    def add_table(
        self,
        pdf,
        headers: list,
        rows: list,
        font_size: int = 10,
    ) -> None:
        """Add a styled table with alternating row colors."""
        n_cols = len(headers)
        col_width = 185 / n_cols

        # Header row
        pdf.set_fill_color(*NAVY)
        pdf.set_text_color(*WHITE)
        pdf.set_font("Helvetica", "B", font_size)
        for header in headers:
            pdf.cell(
                col_width,
                7,
                self._safe_text(str(header))[:20],
                border=0,
                fill=True,
                align="C",
            )
        pdf.ln()

        # Data rows
        for i, row in enumerate(rows):
            if i % 2 == 0:
                pdf.set_fill_color(*LIGHT_GREY)
            else:
                pdf.set_fill_color(255, 255, 255)
            pdf.set_text_color(30, 30, 30)
            pdf.set_font("Helvetica", "", font_size)
            for cell in row:
                pdf.cell(
                    col_width,
                    6,
                    self._safe_text(str(cell))[:25],
                    border=0,
                    fill=True,
                    align="C",
                )
            pdf.ln()
        pdf.ln(4)

    def _add_metrics_row(self, pdf, metrics: list[tuple]) -> None:
        """Add a row of metric boxes (label, value)."""
        box_w = 44
        pdf.set_font("Helvetica", "B", 9)
        for label, value in metrics:
            pdf.set_fill_color(*CARD)
            pdf.set_text_color(*CYAN)
            pdf.cell(box_w, 6, self._safe_text(label), border=0, fill=True, align="C")
        pdf.ln()
        pdf.set_font("Helvetica", "B", 11)
        for label, value in metrics:
            pdf.set_fill_color(*CARD)
            pdf.set_text_color(*WHITE)
            pdf.cell(
                box_w,
                8,
                self._safe_text(str(value))[:18],
                border=0,
                fill=True,
                align="C",
            )
        pdf.ln(12)

    def _add_footer(self, pdf, page_num: int, total_pages: int) -> None:
        """Draw footer on current page."""
        y = 282
        pdf.set_y(y)
        pdf.set_draw_color(*CYAN)
        pdf.set_line_width(0.4)
        pdf.line(10, y, 200, y)
        pdf.ln(2)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*MID_GREY)
        pdf.cell(60, 5, "Generated by FloatChat", align="L")
        pdf.cell(70, 5, f"Page {page_num}", align="C")
        pdf.cell(60, 5, self._get_ist_time().strftime("%Y-%m-%d %H:%M IST"), align="R")

    def _safe_text(self, value: object) -> str:
        """Normalize text to glyphs supported by fpdf core fonts."""
        text = "" if value is None else str(value)
        text = text.translate(self._UNICODE_REPLACEMENTS)
        text = unicodedata.normalize("NFKD", text)
        return text.encode("latin-1", "replace").decode("latin-1")

    def _format_numeric(self, value: object, decimals: int) -> str:
        """Format numeric table values while preserving valid zeroes."""
        if value is None or pd.isna(value):
            return "-"
        if isinstance(value, (int, float)) and not math.isfinite(float(value)):
            return "-"
        return f"{float(value):.{decimals}f}"

    def _add_markdown_text(self, pdf, text: str, font_size: int = 10) -> None:
        """Parse and clean markdown formatting, render as plain text in PDF."""
        import re

        pdf.set_font("Helvetica", "", font_size)
        pdf.set_text_color(30, 30, 30)

        # Strip markdown markers (**bold** → bold, *italic* → italic)
        clean_text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # Remove ** markers
        clean_text = re.sub(r'\*([^*]+)\*', r'\1', clean_text)  # Remove * markers
        clean_text = self._safe_text(clean_text)

        # Render as single multi_cell to avoid positioning issues
        pdf.multi_cell(0, 6, clean_text, align="L")

    def _ensure_new_page(self, pdf, check_content: bool = False) -> None:
        """Add a new page only if the current page has content or if forced."""
        if check_content:
            # Only add new page if we're not already on an empty page
            if pdf.get_y() > 30:  # More than just margins
                pdf.add_page()
        else:
            pdf.add_page()
