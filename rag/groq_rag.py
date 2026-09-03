import logging

import pandas as pd

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are FloatChat, an expert marine scientist and oceanographic data analyst. You have access to real ARGO float sensor data from the Indian Ocean region. Answer questions accurately and concisely using ONLY the provided data context. Always cite specific float IDs, dates, coordinates, and measurement values. If data is insufficient, say so clearly rather than speculating. Use units: °C for temperature, PSU for salinity, dbar for pressure, µmol/kg for oxygen. Provide scientific insights where relevant."""


class OceanRAG:
    """LLM-powered Q&A over ARGO ocean data using Groq (primary) and OpenAI (fallback)."""

    def __init__(self, config: dict) -> None:
        self.config = config
        self.provider = config.get("llm_provider", "groq")
        self.groq_client = None
        self.openai_client = None

        # Initialize Groq
        groq_key = config.get("groq_api_key", "")
        if groq_key and groq_key != "your_groq_api_key_here":
            try:
                import groq as groq_lib
                self.groq_client = groq_lib.Groq(api_key=groq_key)
                logger.info("Groq client initialized")
            except Exception:
                logger.exception("Failed to initialize Groq client")

        # Initialize OpenAI
        openai_key = config.get("openai_api_key", "")
        if openai_key and openai_key != "your_openai_api_key_here":
            try:
                import openai as openai_lib
                self.openai_client = openai_lib.OpenAI(api_key=openai_key)
                logger.info("OpenAI client initialized")
            except Exception:
                logger.exception("Failed to initialize OpenAI client")

    def format_profiles_as_context(self, profiles: list) -> str:
        """Convert retrieved profiles to a compact readable context string (<2000 tokens)."""
        if not profiles:
            return "No oceanographic data profiles are available for this query."

        lines = ["=== RETRIEVED ARGO PROFILES ===\n"]
        char_budget = 6000  # ~2000 tokens at ~3 chars/token

        for i, result in enumerate(profiles[:10], 1):
            profile = result.get("profile", {})
            meta = result.get("metadata", {})

            float_id = profile.get("float_id") or meta.get("float_id", "Unknown")
            date = profile.get("measurement_date") or meta.get("measurement_date", "Unknown")
            if hasattr(date, "strftime"):
                date = date.strftime("%d %b %Y")
            lat = profile.get("latitude")
            if lat is None:
                lat = meta.get("latitude")
            lon = profile.get("longitude")
            if lon is None:
                lon = meta.get("longitude")
            score = result.get("final_score", result.get("similarity_score", 0))
            location = self._format_location(lat, lon)

            block = (
                f"[Profile {i}] Float {float_id} | Date: {date} | "
                f"Location: {location} | Score: {score:.3f}\n"
            )
            # Add summary text if available
            summary = result.get("search_text", "")
            if summary:
                block += f"  Summary: {summary[:300]}\n"
            block += "\n"

            if sum(len(part) for part in lines) + len(block) > char_budget:
                lines.append(f"[...{len(profiles) - i + 1} more profiles truncated]\n")
                break
            lines.append(block)

        return "".join(lines)

    def answer(
        self,
        query: str,
        retrieved_profiles: list,
        chat_history: list | None = None,
    ) -> str:
        """Generate an AI answer using the retrieved profiles as context."""
        if chat_history is None:
            chat_history = []

        if not retrieved_profiles:
            return self.no_data_response(query)

        context = self.format_profiles_as_context(retrieved_profiles)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Last 6 messages of history
        for msg in chat_history[-6:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

        messages.append(
            {
                "role": "user",
                "content": f"Here is the relevant oceanographic data:\n\n{context}\n\nQuestion: {query}",
            }
        )

        # Try primary provider
        if self.provider == "groq" and self.groq_client:
            try:
                return self.answer_with_groq(messages)
            except Exception:
                logger.exception("Groq failed, trying fallback providers")

        # Try OpenAI as fallback
        if self.openai_client:
            try:
                return self.answer_with_openai(messages)
            except Exception:
                logger.exception("OpenAI fallback also failed")

        # Try Groq as fallback if primary is OpenAI or if both have failed
        if self.groq_client:
            try:
                return self.answer_with_groq(messages)
            except Exception:
                logger.exception("Groq fallback failed")

        return (
            "I'm unable to connect to AI services right now. "
            "Please check your API keys in the .env file.\n\n"
            f"Based on retrieved data:\n{context}"
        )

    @staticmethod
    def no_data_response(query: str) -> str:
        """Return a grounded response when retrieval yields no profiles."""
        return (
            "I couldn't retrieve any ARGO profiles that match this query, so I can't "
            "quote a temperature or profile value reliably. "
            f"Please try rephrasing the location or widening the filters for: '{query}'."
        )

    @staticmethod
    def _format_coordinate(value, positive_suffix: str, negative_suffix: str) -> str:
        """Render one latitude/longitude value with hemisphere."""
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return "?"

        suffix = positive_suffix if numeric >= 0 else negative_suffix
        return f"{abs(numeric):.2f}°{suffix}"

    @classmethod
    def _format_location(cls, lat, lon) -> str:
        """Format a lat/lon pair defensively for prompt context."""
        lat_str = cls._format_coordinate(lat, "N", "S")
        lon_str = cls._format_coordinate(lon, "E", "W")
        return f"{lat_str}, {lon_str}"

    def answer_with_groq(self, messages: list) -> str:
        """Call Groq API with llama-3.3-70b-versatile."""
        response = self.groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=1000,
            temperature=0.3,
        )
        return response.choices[0].message.content

    def answer_with_openai(self, messages: list) -> str:
        """Call OpenAI API with gpt-4o-mini."""
        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=1000,
            temperature=0.3,
        )
        return response.choices[0].message.content

    def generate_report_summary(
        self,
        query: str,
        profiles_df: pd.DataFrame,
        stats: dict,
    ) -> str:
        """Generate a longer narrative summary for PDF report generation."""
        if profiles_df.empty:
            return "No data available for the requested query."

        n_profiles = len(profiles_df)
        float_ids = profiles_df["float_id"].unique().tolist() if "float_id" in profiles_df.columns else []
        dates = profiles_df["measurement_date"] if "measurement_date" in profiles_df.columns else None
        date_range = ""
        if dates is not None and not dates.empty:
            date_range = f"from {dates.min()} to {dates.max()}"

        context_parts = [
            f"This report analyzes {n_profiles} ARGO float profiles {date_range}.",
            f"Float IDs included: {', '.join(str(f) for f in float_ids[:10])}.",
        ]

        if stats.get("param_ranges"):
            for param, rng in list(stats["param_ranges"].items())[:4]:
                context_parts.append(
                    f"{param.capitalize()}: {rng['min']:.2f} to {rng['max']:.2f}"
                )

        context = " ".join(context_parts)
        prompt = (
            f"Generate a comprehensive scientific summary (max 500 words) for an oceanographic "
            f"data report. Query: '{query}'. Data context: {context}\n\n"
            "Include: key oceanographic findings, parameter ranges, geographic coverage, "
            "scientific significance, and any notable patterns or anomalies."
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        if self.groq_client:
            try:
                response = self.groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=messages,
                    max_tokens=800,
                    temperature=0.4,
                )
                return response.choices[0].message.content
            except Exception:
                logger.exception("Failed to generate report summary with Groq")

        if self.openai_client:
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    max_tokens=800,
                    temperature=0.4,
                )
                return response.choices[0].message.content
            except Exception:
                logger.exception("Failed to generate report summary with OpenAI")

        return context
