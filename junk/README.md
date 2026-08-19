# junk

Ingesta que **no** forma parte de scrapers → Supabase (`db/ingest.py`).
Revisar y borrar o reintegrar.

## Qué hay aquí (POC BOCM)

| Fichero | Qué era |
|---------|---------|
| `0_quick_test.py` | Descarga 7 PDFs hardcodeados |
| `1_collect_bocm.py` | Collector RSS/POC (sustituido por `fetch_history.py`) |
| `2_extract_text.py` | pdftotext masivo del POC |
| `poc_small_examples.py` | Eval LLM de muestra |
| `try_ccaa_sample_parse.py` | Prueba CCAA de un PDF |
| `municipio_discover.py` | Descubrimiento por sitemap (sustituido por adapters) |
| `dashboard.html` | Dashboard local del POC |

## Qué NO se ha movido (a propósito)

- **Madrid legado** (`sector_geometry/madrid_*`, `db/sync_dominio_to_supabase.py`, SQLite SIGMA): el scrape SIGMA/visor sigue ahí, pero el movimiento vivo es `python -m municipio run --municipio madrid` → JSONL → `db/ingest.py`.
- **Pipeline vivo:** `municipio/`, `parse_history_nightly.py`, `parse_ccaa_history_nightly.py`, `fetch_history.py`, `3_llm_parse.py`, `boletin_llm_parse.py`, `db/ingest.py`.
