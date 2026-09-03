# FloatChat

AI-powered conversational interface for ARGO oceanographic float data discovery and visualization.

## Features

- **Data Sync** — Auto-downloads daily ARGO Indian Ocean profiles from Ifremer FTP
- **AI Chat** — 3-stage hybrid retrieval (spatial filter → semantic search → score fusion)
- **Data Explorer** — Filter and browse ocean profiles with interactive depth charts
- **Visualizations** — Depth profiles, T-S diagrams, time series, maps, heatmaps

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit |
| Database | PostgreSQL 15 |
| Vector DB | ChromaDB |
| LLM | Groq (llama-3.3-70b-versatile) + OpenAI fallback |
| Embeddings | sentence-transformers all-MiniLM-L6-v2 |
| Data | xarray, netCDF4, pandas |
| Visualization | Plotly, Folium |
| PDF | fpdf2 |

## Setup

### 1. Database

```bash
brew services start postgresql@15
createdb argo_data
```

### 2. Environment

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
# Edit .env — add GROQ_API_KEY and/or OPENAI_API_KEY
```

### 3. Dependencies

```bash
pip3 install -r requirements.txt
```

### 4. Run

```bash
streamlit run Home.py
```

Open [http://localhost:8501](http://localhost:8501)

## Hybrid Retrieval (Patent Core)

**Final Score = 0.4 × Spatial Score + 0.6 × Semantic Score**

1. **Stage 1 — Spatial Filter**: PostgreSQL query using lat/lon/date/float_id filters
2. **Stage 2 — Semantic Search**: ChromaDB vector search within Stage 1 candidates
3. **Stage 3 — Score Fusion**: Weighted combination of spatial proximity and semantic relevance

## Data Source

ARGO float data from [Ifremer FTP](ftp://ftp.ifremer.fr/ifremer/argo/geo/indian_ocean) — Indian Ocean profiles updated daily.
