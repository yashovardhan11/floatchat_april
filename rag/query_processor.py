import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

# ─── Domain constants ─────────────────────────────────────────────────────────

OCEAN_REGIONS = {
    "arabian_sea": {
        "lat_min": 5.0, "lat_max": 25.0, "lon_min": 50.0, "lon_max": 78.0,
        "keywords": ["arabian sea", "arabian", "oman", "gulf of oman", "persian gulf",
                     "lakshadweep", "laccadive"],
    },
    "bay_of_bengal": {
        "lat_min": 5.0, "lat_max": 25.0, "lon_min": 78.0, "lon_max": 100.0,
        "keywords": ["bay of bengal", "bengal", "andaman", "myanmar", "bangladesh"],
    },
    "indian_ocean": {
        "lat_min": -60.0, "lat_max": 30.0, "lon_min": 20.0, "lon_max": 120.0,
        "keywords": ["indian ocean", "india", "indian", "south asia"],
    },
    "lakshadweep_sea": {
        "lat_min": 8.0, "lat_max": 15.0, "lon_min": 72.0, "lon_max": 77.0,
        "keywords": ["lakshadweep", "laccadive sea", "kerala coast"],
    },
    "andaman_sea": {
        "lat_min": 10.0, "lat_max": 20.0, "lon_min": 92.0, "lon_max": 100.0,
        "keywords": ["andaman sea", "andaman islands", "nicobar"],
    },
    "southern_ocean": {
        "lat_min": -70.0, "lat_max": -40.0, "lon_min": 0.0, "lon_max": 360.0,
        "keywords": ["southern ocean", "antarctic", "antarctica"],
    },
    "pacific_ocean": {
        "lat_min": -60.0, "lat_max": 60.0, "lon_min": 120.0, "lon_max": 280.0,
        "keywords": ["pacific ocean", "pacific"],
    },
    "atlantic_ocean": {
        "lat_min": -60.0, "lat_max": 60.0, "lon_min": -80.0, "lon_max": 20.0,
        "keywords": ["atlantic ocean", "atlantic"],
    },
}

SEASON_MONTHS = {
    "monsoon": (6, 9),
    "summer_monsoon": (6, 9),
    "southwest_monsoon": (6, 9),
    "winter_monsoon": (11, 2),
    "northeast_monsoon": (11, 2),
    "pre_monsoon": (3, 5),
    "post_monsoon": (10, 11),
    "spring": (3, 5),
    "summer": (6, 8),
    "autumn": (9, 11),
    "fall": (9, 11),
    "winter": (12, 2),
}

PARAMETERS = [
    "temperature",
    "salinity",
    "pressure",
    "oxygen",
    "nitrate",
    "ph",
    "chlorophyll",
    "density",
    "mixed_layer_depth",
    "potential_temperature",
]

PARAMETER_ALIASES = {
    "temp": "temperature",
    "sst": "temperature",
    "sea surface temperature": "temperature",
    "sal": "salinity",
    "psal": "salinity",
    "pres": "pressure",
    "doxy": "oxygen",
    "dissolved oxygen": "oxygen",
    "o2": "oxygen",
    "no3": "nitrate",
    "chla": "chlorophyll",
    "chl": "chlorophyll",
    "mld": "mixed_layer_depth",
    "mixed layer": "mixed_layer_depth",
    "density": "density",
    "sigma": "density",
    "theta": "potential_temperature",
}

MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9,
    "oct": 10, "nov": 11, "dec": 12,
}


class QueryProcessor:
    """Parses natural language queries into structured filter dicts."""

    def process(self, query: str) -> dict:
        text = query.lower().strip()
        result = {
            "parameters": self.extract_parameters(text),
            "location": self.extract_location(text),
            "float_id": self.extract_float_id(text),
            "season": self.extract_season(text),
            "raw_query": query,
        }
        time_info = self.extract_time(text)
        result["date_from"] = time_info.get("date_from")
        result["date_to"] = time_info.get("date_to")
        logger.debug("Parsed query: %s", result)
        return result

    def extract_parameters(self, text: str) -> list[str]:
        found = set()
        for param in PARAMETERS:
            if param in text or param.replace("_", " ") in text:
                found.add(param)
        for alias, canonical in PARAMETER_ALIASES.items():
            if alias in text:
                found.add(canonical)
        return list(found)

    def extract_location(self, text: str) -> dict | None:
        for region_name, region_data in OCEAN_REGIONS.items():
            for keyword in region_data.get("keywords", []):
                if keyword in text:
                    return {
                        "region_name": region_name,
                        "lat_min": region_data["lat_min"],
                        "lat_max": region_data["lat_max"],
                        "lon_min": region_data["lon_min"],
                        "lon_max": region_data["lon_max"],
                    }

        # Coordinate extraction: e.g. "near 15N 70E" or "at 12.5°N 68°E"
        coord_pattern = r"(\d+\.?\d*)\s*°?\s*([ns])\s*[,\s]+(\d+\.?\d*)\s*°?\s*([ew])"
        match = re.search(coord_pattern, text, re.IGNORECASE)
        if match:
            lat = float(match.group(1))
            if match.group(2).lower() == "s":
                lat = -lat
            lon = float(match.group(3))
            if match.group(4).lower() == "w":
                lon = -lon
            pad = 5.0
            return {
                "region_name": "custom",
                "lat_min": lat - pad,
                "lat_max": lat + pad,
                "lon_min": lon - pad,
                "lon_max": lon + pad,
            }
        return None

    def extract_time(self, text: str) -> dict:
        result: dict = {}
        now = datetime.utcnow()

        # "last N days/weeks/months"
        m = re.search(r"last\s+(\d+)\s+(day|week|month|year)s?", text)
        if m:
            n = int(m.group(1))
            unit = m.group(2)
            from datetime import timedelta

            if unit == "day":
                delta = timedelta(days=n)
            elif unit == "week":
                delta = timedelta(weeks=n)
            elif unit == "month":
                delta = timedelta(days=n * 30)
            else:
                delta = timedelta(days=n * 365)
            result["date_from"] = now - delta
            result["date_to"] = now
            return result

        # "in YYYY" or just a 4-digit year
        year_match = re.search(r"\b(20\d{2}|19\d{2})\b", text)
        if year_match:
            year = int(year_match.group(1))
            result["date_from"] = datetime(year, 1, 1)
            result["date_to"] = datetime(year, 12, 31)

        # Month name
        for month_name, month_num in MONTH_NAMES.items():
            if month_name in text:
                year = now.year
                if "date_from" in result:
                    year = result["date_from"].year
                # Find last day of month
                import calendar
                last_day = calendar.monthrange(year, month_num)[1]
                result["date_from"] = datetime(year, month_num, 1)
                result["date_to"] = datetime(year, month_num, last_day)
                break

        # "recent" or "latest" → last 30 days
        if any(w in text for w in ("recent", "latest", "current", "today")):
            from datetime import timedelta
            result["date_from"] = now - timedelta(days=30)
            result["date_to"] = now

        return result

    def extract_float_id(self, text: str) -> str | None:
        # "float 1234567" or "WMO 1234567"
        m = re.search(r"(?:float|wmo|platform)\s+(\w{4,10})", text, re.IGNORECASE)
        if m:
            return m.group(1).upper()
        # Standalone 7-digit number (ARGO WMO IDs are typically 7 digits)
        m = re.search(r"\b(\d{7})\b", text)
        if m:
            return m.group(1)
        return None

    def extract_season(self, text: str) -> str | None:
        for season_name in SEASON_MONTHS:
            if season_name.replace("_", " ") in text or season_name in text:
                return season_name
        return None
