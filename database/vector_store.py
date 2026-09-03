import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ─── Domain knowledge seed documents ─────────────────────────────────────────

DOMAIN_DOCUMENTS = [
    {
        "id": "domain_temp",
        "text": (
            "TEMP sea water temperature: The in-situ temperature of sea water measured "
            "by ARGO float sensors in degrees Celsius. Temperature profiles reveal "
            "thermoclines, mixed layer depths, and water mass characteristics. "
            "Typical ocean surface temperatures range from -2°C in polar regions to "
            "30°C in tropical waters. Deep ocean temperatures approach 0-4°C."
        ),
        "metadata": {"type": "parameter", "parameter": "temperature"},
    },
    {
        "id": "domain_psal",
        "text": (
            "PSAL practical salinity: The practical salinity of sea water measured "
            "by ARGO floats in PSU (Practical Salinity Units). Salinity indicates "
            "water mass origin and mixing. Surface salinity varies from ~32 PSU in "
            "high-rainfall regions to ~37 PSU in evaporation-dominated areas. "
            "Indian Ocean surface salinities typically range 32-37 PSU."
        ),
        "metadata": {"type": "parameter", "parameter": "salinity"},
    },
    {
        "id": "domain_pres",
        "text": (
            "PRES sea water pressure: Pressure measured by ARGO floats in decibars (dbar). "
            "Pressure in the ocean approximately equals depth in meters (1 dbar ≈ 1 meter). "
            "ARGO floats profile from surface to 2000 dbar (2000 meters) by default, "
            "with deep floats reaching 6000 dbar. Used to derive depth and density."
        ),
        "metadata": {"type": "parameter", "parameter": "pressure"},
    },
    {
        "id": "domain_doxy",
        "text": (
            "DOXY dissolved oxygen: Dissolved oxygen concentration measured by BGC-ARGO "
            "floats in µmol/kg. Oxygen is critical for marine life and indicates "
            "biological productivity, water mass ventilation, and oxygen minimum zones. "
            "Surface waters are typically near saturation (~200-250 µmol/kg). "
            "Oxygen minimum zones in Indian Ocean can drop below 5 µmol/kg."
        ),
        "metadata": {"type": "parameter", "parameter": "oxygen"},
    },
    {
        "id": "domain_nitrate",
        "text": (
            "NITRATE nitrate concentration: Nitrate (NO3) measured by BGC-ARGO floats "
            "in µmol/kg. Nitrate is a key nutrient limiting phytoplankton growth. "
            "Surface waters are often depleted (0-2 µmol/kg) while deep waters "
            "contain 20-40 µmol/kg. Upwelling regions show elevated surface nitrate."
        ),
        "metadata": {"type": "parameter", "parameter": "nitrate"},
    },
    {
        "id": "domain_ph",
        "text": (
            "PH_IN_SITU_TOTAL ocean pH: In-situ total scale pH measured by BGC-ARGO "
            "floats. Ocean pH typically ranges 7.8-8.3. Ocean acidification driven by "
            "CO2 absorption is reducing ocean pH. Deep waters have lower pH than "
            "surface waters. pH affects carbonate chemistry and coral reef health."
        ),
        "metadata": {"type": "parameter", "parameter": "ph"},
    },
    {
        "id": "domain_chla",
        "text": (
            "CHLA chlorophyll-a: Chlorophyll-a concentration measured by BGC-ARGO floats "
            "in mg/m³. Chlorophyll indicates phytoplankton biomass and primary productivity. "
            "Deep chlorophyll maximum (DCM) typically occurs at 50-150m depth. "
            "Surface blooms visible during monsoon upwelling in Arabian Sea."
        ),
        "metadata": {"type": "parameter", "parameter": "chlorophyll"},
    },
    {
        "id": "domain_argo_overview",
        "text": (
            "ARGO float program: The international Argo program deploys autonomous "
            "profiling floats worldwide. Each float drifts at depth (typically 1000m), "
            "then descends to 2000m before ascending to the surface collecting CTD "
            "profiles every 10 days. Data is transmitted via satellite (Iridium/Argos). "
            "The global array has over 4000 active floats providing continuous ocean monitoring."
        ),
        "metadata": {"type": "overview", "topic": "argo_program"},
    },
    {
        "id": "domain_bgc_argo",
        "text": (
            "BGC-ARGO biogeochemical floats: Biogeochemical Argo (BGC-Argo) floats carry "
            "additional sensors beyond the standard CTD: oxygen (DOXY), nitrate (NITRATE), "
            "pH, chlorophyll (CHLA), backscattering (BBP), and irradiance (PAR). "
            "BGC-Argo provides unprecedented observations of ocean biogeochemistry, "
            "critical for understanding carbon cycling and ecosystem dynamics."
        ),
        "metadata": {"type": "overview", "topic": "bgc_argo"},
    },
    {
        "id": "domain_arabian_sea",
        "text": (
            "Arabian Sea: Northwestern arm of the Indian Ocean bounded by the Arabian "
            "Peninsula, Pakistan, India, and Somalia. Characterized by strong monsoonal "
            "forcing, seasonal upwelling off Oman and Somalia (SW monsoon Jun-Sep), "
            "high salinity (>36 PSU), and one of the world's most intense oxygen minimum "
            "zones (OMZ) at 150-1000m. Lat: 5°N-25°N, Lon: 50°E-78°E."
        ),
        "metadata": {"type": "region", "region": "arabian_sea"},
    },
    {
        "id": "domain_bay_of_bengal",
        "text": (
            "Bay of Bengal: Northeastern arm of the Indian Ocean bounded by India, "
            "Bangladesh, Myanmar, and the Andaman Islands. Characterized by heavy "
            "freshwater input from major rivers (Ganges, Brahmaputra, Irrawaddy) "
            "creating a shallow low-salinity surface layer (barrier layer). "
            "Warm SST fuels intense tropical cyclones. Lat: 5°N-25°N, Lon: 78°E-100°E."
        ),
        "metadata": {"type": "region", "region": "bay_of_bengal"},
    },
    {
        "id": "domain_indian_ocean",
        "text": (
            "Indian Ocean: Third largest ocean basin, bounded by Africa, Asia, Australia, "
            "and Antarctica. Unique as the only ocean with a seasonally reversing monsoon "
            "circulation. Contains Arabian Sea, Bay of Bengal, and Lakshadweep Sea. "
            "Hosts significant submarine ridges and diverse water masses. "
            "Lat: -60°S-30°N, Lon: 20°E-120°E."
        ),
        "metadata": {"type": "region", "region": "indian_ocean"},
    },
    {
        "id": "domain_thermocline",
        "text": (
            "Thermocline: Layer of rapid temperature change separating warmer surface "
            "waters from cold deep waters. In the Indian Ocean the permanent thermocline "
            "is typically at 100-300m depth. Seasonal thermoclines form in summer. "
            "The thermocline inhibits vertical mixing and nutrient supply to the "
            "euphotic zone. Thermocline depth varies with latitude and season."
        ),
        "metadata": {"type": "concept", "topic": "thermocline"},
    },
    {
        "id": "domain_mld",
        "text": (
            "Mixed layer depth (MLD): Depth of the surface mixed layer where temperature, "
            "salinity, and density are nearly uniform due to wind mixing and convection. "
            "MLD is typically defined as depth where temperature drops 0.2°C below "
            "surface value. Indian Ocean MLD ranges from 20-30m in summer to 80-120m "
            "in winter. Deeper MLD in Arabian Sea during northeast monsoon."
        ),
        "metadata": {"type": "concept", "topic": "mixed_layer_depth"},
    },
    {
        "id": "domain_monsoon",
        "text": (
            "Indian Ocean monsoon: The Indian Ocean monsoon drives seasonal reversal "
            "of winds and currents. Southwest (summer) monsoon Jun-Sep brings "
            "upwelling, cooler SST, and phytoplankton blooms in the Arabian Sea. "
            "Northeast (winter) monsoon Nov-Feb brings calm conditions and deeper "
            "mixed layers. The monsoon is the dominant driver of Indian Ocean variability "
            "affecting temperature, salinity, biology, and air-sea fluxes."
        ),
        "metadata": {"type": "concept", "topic": "monsoon"},
    },
]


class ChromaVectorStore:
    """Persistent vector store using ChromaDB with sentence-transformer embeddings."""

    COLLECTION_NAME = "argo_profiles"

    def __init__(self, config: dict) -> None:
        import chromadb
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

        chroma_path = str(Path(config["chroma_db_path"]))
        self.client = chromadb.PersistentClient(path=chroma_path)
        self.embedding_fn = SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "l2"},
        )
        logger.info(
            "ChromaVectorStore initialized, collection=%s count=%d",
            self.COLLECTION_NAME,
            self.collection.count(),
        )

        # Seed domain knowledge if collection is empty
        if self.collection.count() == 0:
            self.seed_domain_knowledge()

    def seed_domain_knowledge(self) -> None:
        """Add oceanographic domain knowledge documents to ChromaDB."""
        try:
            ids = [doc["id"] for doc in DOMAIN_DOCUMENTS]
            documents = [doc["text"] for doc in DOMAIN_DOCUMENTS]
            metadatas = [doc["metadata"] for doc in DOMAIN_DOCUMENTS]
            self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
            logger.info("Seeded %d domain knowledge documents", len(DOMAIN_DOCUMENTS))
        except Exception:
            logger.exception("Failed to seed domain knowledge")

    def add_profile(self, profile_summary: dict, profile_id: int) -> None:
        """Embed and upsert a profile summary into ChromaDB."""
        try:
            doc_id = f"profile_{profile_id}"
            text = profile_summary.get("summary_text", "")
            if not text:
                logger.warning("Empty summary_text for profile_id=%d", profile_id)
                return

            metadata = {
                "profile_id": profile_id,
                "float_id": str(profile_summary.get("float_id", "")),
                "latitude": float(profile_summary.get("latitude", 0.0)),
                "longitude": float(profile_summary.get("longitude", 0.0)),
                "measurement_date": str(profile_summary.get("measurement_date", "")),
                "type": "profile",
            }
            self.collection.upsert(
                ids=[doc_id],
                documents=[text],
                metadatas=[metadata],
            )
            logger.debug("Upserted profile to ChromaDB: %s", doc_id)
        except Exception:
            logger.exception("Failed to add_profile to ChromaDB id=%d", profile_id)

    def search(self, query: str, k: int = 10) -> list[dict]:
        """Semantic search; returns results with similarity scores."""
        try:
            count = self.collection.count()
            if count == 0:
                return []
            effective_k = min(k, count)
            results = self.collection.query(
                query_texts=[query],
                n_results=effective_k,
                where={"type": "profile"},
            )
            return self._parse_results(results)
        except Exception:
            logger.exception("ChromaDB search failed for query='%s'", query)
            return []

    def search_with_filter(
        self, query: str, profile_ids: list[int], k: int = 10
    ) -> list[dict]:
        """Semantic search filtered to specific profile IDs — critical for hybrid retrieval."""
        if not profile_ids:
            return []
        try:
            # ChromaDB where clause for profile_id in list
            if len(profile_ids) == 1:
                where_clause = {
                    "$and": [
                        {"type": "profile"},
                        {"profile_id": profile_ids[0]},
                    ]
                }
            else:
                where_clause = {
                    "$and": [
                        {"type": "profile"},
                        {"profile_id": {"$in": profile_ids}},
                    ]
                }

            count = self.collection.count()
            effective_k = min(k, count, len(profile_ids))
            if effective_k == 0:
                return []

            results = self.collection.query(
                query_texts=[query],
                n_results=effective_k,
                where=where_clause,
            )
            return self._parse_results(results)
        except Exception:
            logger.exception(
                "ChromaDB search_with_filter failed, falling back to unfiltered search"
            )
            return self.search(query, k)

    def get_statistics(self) -> dict:
        try:
            count = self.collection.count()
            profile_count = 0
            domain_count = 0
            try:
                profile_results = self.collection.get(where={"type": "profile"})
                profile_count = len(profile_results.get("ids", []))
                domain_count = count - profile_count
            except Exception:
                pass
            return {
                "total_documents": count,
                "profile_documents": profile_count,
                "domain_documents": domain_count,
                "collection_name": self.COLLECTION_NAME,
            }
        except Exception:
            logger.exception("Failed to get ChromaDB statistics")
            return {"total_documents": 0, "profile_documents": 0, "domain_documents": 0}

    def clear_profiles(self) -> None:
        """Remove all profile documents, keeping domain knowledge."""
        try:
            results = self.collection.get(where={"type": "profile"})
            ids_to_delete = results.get("ids", [])
            if ids_to_delete:
                self.collection.delete(ids=ids_to_delete)
                logger.info("Cleared %d profile documents from ChromaDB", len(ids_to_delete))
        except Exception:
            logger.exception("Failed to clear_profiles from ChromaDB")

    def remove_profile(self, profile_id: int) -> None:
        try:
            self.collection.delete(ids=[f"profile_{profile_id}"])
            logger.debug("Removed profile_%d from ChromaDB", profile_id)
        except Exception:
            logger.exception("Failed to remove_profile id=%d", profile_id)

    # ─── Private helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _parse_results(results: dict) -> list[dict]:
        """Parse ChromaDB query results into a list of dicts with similarity scores."""
        parsed = []
        ids_list = results.get("ids", [[]])[0]
        distances = results.get("distances", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        documents = results.get("documents", [[]])[0]

        for doc_id, distance, meta, doc in zip(ids_list, distances, metadatas, documents):
            similarity = max(0.0, 1.0 - distance)
            profile_id = meta.get("profile_id")
            parsed.append(
                {
                    "doc_id": doc_id,
                    "profile_id": int(profile_id) if profile_id is not None else None,
                    "similarity_score": similarity,
                    "distance": distance,
                    "search_text": doc,
                    "metadata": meta,
                }
            )
        return parsed
