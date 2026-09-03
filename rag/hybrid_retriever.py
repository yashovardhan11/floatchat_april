import logging
import math
import re

logger = logging.getLogger(__name__)


class HybridOceanRetriever:
    """
    3-Stage Hybrid Retrieval System — Core Patent Contribution.

    Stage 1: Spatial filter via PostgreSQL (structured DB query)
    Stage 2: Semantic search in ChromaDB filtered to Stage 1 results
    Stage 3: Score fusion using Final Score = 0.4×Spatial + 0.6×Semantic
    """

    SPATIAL_WEIGHT = 0.4
    SEMANTIC_WEIGHT = 0.6

    def __init__(self, db_manager, vector_store) -> None:
        self.db = db_manager
        self.vs = vector_store

    # ─── Stage 1: Spatial Filter ──────────────────────────────────────────────

    def spatial_filter(self, filters: dict) -> list[int]:
        """Query PostgreSQL with spatial/temporal/float filters → list of profile IDs."""
        location = filters.get("location")
        date_from = filters.get("date_from")
        date_to = filters.get("date_to")
        float_id = filters.get("float_id")

        lat_min = lat_max = lon_min = lon_max = None
        if location:
            lat_min = location.get("lat_min")
            lat_max = location.get("lat_max")
            lon_min = location.get("lon_min")
            lon_max = location.get("lon_max")

        has_filter = any(
            x is not None for x in (
                lat_min, lat_max, lon_min, lon_max,
                date_from, date_to, float_id,
            )
        )

        limit = 500 if not has_filter else 1000
        profiles_df = self.db.get_profiles(
            limit=limit,
            float_id=float_id,
            date_from=date_from,
            date_to=date_to,
            lat_min=lat_min,
            lat_max=lat_max,
            lon_min=lon_min,
            lon_max=lon_max,
        )

        if profiles_df.empty:
            profile_ids = []
        else:
            profile_ids = profiles_df["id"].tolist()

        logger.info("Stage 1 spatial filter: %d profiles found", len(profile_ids))
        return profile_ids

    # ─── Stage 2: Semantic Search ─────────────────────────────────────────────

    def semantic_search(
        self, query: str, profile_ids: list[int], k: int = 20
    ) -> list[dict]:
        """Semantic search in ChromaDB filtered to spatial candidates."""
        if not profile_ids:
            logger.info("Stage 2 semantic search: 0 results (empty candidate list)")
            return []

        effective_k = min(k, len(profile_ids))
        results = self.vs.search_with_filter(
            query=query, profile_ids=profile_ids, k=effective_k
        )
        logger.info("Stage 2 semantic search: %d results", len(results))
        return results

    def fallback_search(
        self,
        query: str,
        filters: dict,
        profile_ids: list[int],
        k: int = 20,
    ) -> list[dict]:
        """
        Graceful fallback when vector search returns nothing.

        We first try a lightweight lexical match over the spatial candidates'
        summary text. If that still finds nothing but the user provided
        structured filters (location/date/float), we surface the most recent
        spatial candidates with a low neutral similarity so the RAG layer still
        receives grounded context instead of an empty set.
        """
        if not profile_ids:
            return []

        profiles_df = self.db.get_profiles_by_ids(profile_ids)
        if profiles_df.empty:
            logger.info("Stage 2 fallback search: 0 results (empty profile frame)")
            return []

        profiles_df = profiles_df.sort_values(
            "measurement_date", ascending=False, na_position="last"
        )
        query_terms = self._extract_query_terms(query, filters)

        scored: list[dict] = []
        for _, row in profiles_df.iterrows():
            summary_text = row.get("summary_text") or ""
            similarity_score = self._lexical_similarity(summary_text, query_terms)
            if similarity_score <= 0:
                continue
            scored.append(
                self._profile_row_to_search_result(row, similarity_score=similarity_score)
            )

        if scored:
            scored.sort(key=lambda item: item["similarity_score"], reverse=True)
            top_k = scored[: min(k, len(scored))]
            logger.info("Stage 2 fallback search: %d lexical results", len(top_k))
            return top_k

        if self._has_structured_constraints(filters):
            baseline = []
            for _, row in profiles_df.head(min(k, len(profiles_df))).iterrows():
                baseline.append(
                    self._profile_row_to_search_result(row, similarity_score=0.2)
                )
            logger.info(
                "Stage 2 fallback search: %d structured-filter baseline results",
                len(baseline),
            )
            return baseline

        logger.info("Stage 2 fallback search: 0 results")
        return []

    # ─── Stage 3: Score Fusion ────────────────────────────────────────────────

    def fuse_scores(
        self,
        spatial_profiles: list[int],
        semantic_results: list[dict],
        query_location: dict | None = None,
        k: int = 10,
    ) -> list[dict]:
        """
        Compute final score using the patent formula:
            Final Score = (0.4 × spatial_score) + (0.6 × semantic_score)
        """
        if not semantic_results:
            logger.info("Stage 3 score fusion: 0 results")
            return []

        # Get profile metadata for spatial scoring
        all_pids = [r["profile_id"] for r in semantic_results if r.get("profile_id")]
        profiles_df = self.db.get_profiles_by_ids(all_pids) if all_pids else None

        profile_map = {}
        if profiles_df is not None and not profiles_df.empty:
            for _, row in profiles_df.iterrows():
                profile_map[row["id"]] = row

        fused = []
        for result in semantic_results:
            semantic_score = result.get("similarity_score", 0.0)
            pid = result.get("profile_id")
            profile = profile_map.get(pid) if pid else None
            spatial_score = self._compute_spatial_score(profile, query_location)
            final_score = (
                self.SPATIAL_WEIGHT * spatial_score
                + self.SEMANTIC_WEIGHT * semantic_score
            )
            fused.append(
                {
                    **result,
                    "spatial_score": spatial_score,
                    "semantic_score": semantic_score,
                    "final_score": final_score,
                    "profile": profile.to_dict() if profile is not None else {},
                }
            )

        fused.sort(key=lambda x: x["final_score"], reverse=True)
        top_k = fused[:k]
        logger.info("Stage 3 score fusion: top %d returned", len(top_k))
        return top_k

    def _compute_spatial_score(
        self, profile, query_location: dict | None
    ) -> float:
        """Score 0-1 for how close a profile is to the query region centroid."""
        if query_location is None or profile is None:
            return 0.5  # neutral when no spatial preference

        try:
            lat = float(profile["latitude"]) if hasattr(profile, "__getitem__") else float(getattr(profile, "latitude", 0))
            lon = float(profile["longitude"]) if hasattr(profile, "__getitem__") else float(getattr(profile, "longitude", 0))
        except (TypeError, KeyError, ValueError):
            return 0.5

        # Region centroid
        centroid_lat = (query_location["lat_min"] + query_location["lat_max"]) / 2.0
        centroid_lon = (query_location["lon_min"] + query_location["lon_max"]) / 2.0

        # Euclidean distance in degree-space
        dist = math.sqrt((lat - centroid_lat) ** 2 + (lon - centroid_lon) ** 2)

        # Normalize: region half-diagonal as reference distance
        half_diag = math.sqrt(
            ((query_location["lat_max"] - query_location["lat_min"]) / 2) ** 2
            + ((query_location["lon_max"] - query_location["lon_min"]) / 2) ** 2
        ) or 10.0

        # Score: 1.0 at centroid, decays with distance
        score = max(0.0, 1.0 - (dist / (half_diag * 2.0)))
        return score

    # ─── Main retrieve method ─────────────────────────────────────────────────

    def retrieve(self, query: str, filters: dict, k: int = 10) -> dict:
        """
        Full 3-stage hybrid retrieval.

        Returns top-k profiles with scores and retrieval metadata.
        """
        # Stage 1
        profile_ids = self.spatial_filter(filters)

        # Stage 2
        semantic_query = self._build_semantic_query(query, filters)
        semantic_results = self.semantic_search(
            semantic_query, profile_ids, k=k * 2
        )
        semantic_fallback_used = False
        if not semantic_results and profile_ids:
            semantic_results = self.fallback_search(
                query, filters, profile_ids, k=k * 2
            )
            semantic_fallback_used = len(semantic_results) > 0

        # Stage 3
        location = filters.get("location")
        final_results = self.fuse_scores(
            profile_ids, semantic_results, query_location=location, k=k
        )

        return {
            "results": final_results,
            "stage1_count": len(profile_ids),
            "stage2_count": len(semantic_results),
            "final_count": len(final_results),
            "retrieval_details": {
                "spatial_filter_applied": location is not None
                or filters.get("float_id") is not None
                or filters.get("date_from") is not None
                or filters.get("date_to") is not None,
                "semantic_search_applied": len(semantic_results) > 0,
                "semantic_fallback_used": semantic_fallback_used,
                "semantic_query": semantic_query,
                "fusion_weights": {
                    "spatial": self.SPATIAL_WEIGHT,
                    "semantic": self.SEMANTIC_WEIGHT,
                },
            },
        }

    @staticmethod
    def _has_structured_constraints(filters: dict) -> bool:
        """Detect queries that contain explicit spatial/temporal/float filters."""
        return any(
            (
                filters.get("location") is not None,
                filters.get("float_id") is not None,
                filters.get("date_from") is not None,
                filters.get("date_to") is not None,
            )
        )

    @staticmethod
    def _build_semantic_query(query: str, filters: dict) -> str:
        """
        Enrich the raw user query with structured hints extracted upstream.

        This helps broad or slightly misspelled prompts like "indian oean" still
        search with canonical region and parameter terms.
        """
        parts: list[str] = [query.strip()]

        parameters = filters.get("parameters") or []
        if parameters:
            parts.append(" ".join(parameters))

        location = filters.get("location") or {}
        region_name = location.get("region_name")
        if region_name:
            parts.append(region_name.replace("_", " "))

        float_id = filters.get("float_id")
        if float_id:
            parts.append(f"float {float_id}")

        parts.append("argo oceanographic profile")

        deduped: list[str] = []
        seen: set[str] = set()
        for part in parts:
            cleaned = part.strip()
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(cleaned)
        return " ".join(deduped)

    @staticmethod
    def _extract_query_terms(query: str, filters: dict) -> list[str]:
        """Build a compact keyword list for lexical fallback ranking."""
        stopwords = {
            "about",
            "after",
            "argo",
            "around",
            "data",
            "find",
            "float",
            "from",
            "give",
            "here",
            "into",
            "latest",
            "near",
            "ocean",
            "profile",
            "show",
            "tell",
            "that",
            "the",
            "their",
            "there",
            "these",
            "this",
            "what",
            "when",
            "where",
            "which",
            "with",
        }

        terms = re.findall(r"[a-z0-9]+", query.lower())

        for param in filters.get("parameters") or []:
            terms.extend(re.findall(r"[a-z0-9]+", param.lower().replace("_", " ")))

        location = filters.get("location") or {}
        region_name = location.get("region_name")
        if region_name:
            terms.extend(re.findall(r"[a-z0-9]+", region_name.lower().replace("_", " ")))

        deduped: list[str] = []
        seen: set[str] = set()
        for term in terms:
            if len(term) < 3 or term in stopwords or term in seen:
                continue
            seen.add(term)
            deduped.append(term)
        return deduped

    @staticmethod
    def _lexical_similarity(summary_text: str, query_terms: list[str]) -> float:
        """Simple overlap score for summary-text fallback ranking."""
        if not summary_text or not query_terms:
            return 0.0

        haystack = summary_text.lower()
        hits = sum(1 for term in query_terms if term in haystack)
        if hits == 0:
            return 0.0

        overlap = hits / len(query_terms)
        return min(0.95, 0.35 + 0.6 * overlap)

    @staticmethod
    def _profile_row_to_search_result(row, similarity_score: float) -> dict:
        """Convert a profile DB row into the same shape as vector search results."""
        profile = row.to_dict()
        profile_id = int(profile["id"])
        measurement_date = profile.get("measurement_date")
        measurement_date_str = (
            measurement_date.isoformat(sep=" ")
            if hasattr(measurement_date, "isoformat")
            else str(measurement_date or "")
        )
        metadata = {
            "profile_id": profile_id,
            "float_id": str(profile.get("float_id", "")),
            "latitude": float(profile.get("latitude", 0.0) or 0.0),
            "longitude": float(profile.get("longitude", 0.0) or 0.0),
            "measurement_date": measurement_date_str,
            "type": "profile",
        }

        return {
            "doc_id": f"profile_{profile_id}",
            "profile_id": profile_id,
            "similarity_score": similarity_score,
            "distance": max(0.0, 1.0 - similarity_score),
            "search_text": profile.get("summary_text", "") or "",
            "metadata": metadata,
        }
