# Homes / BOCM

Scrapers periódicos (ayuntamientos, boletines, Madrid) → `db/ingest.py` → Supabase (`homes.*`).

```
fetch_history.py / parse_history_nightly.py   → boletines → homes.publicacion
python -m municipio run --municipio <slug> --step all  → homes.proyecto / licencia
python -m municipio run --municipio madrid --step update  → SIGMA/visor/licencias
python -m municipio schedule run --interval-days 15 --limit 16  → lote due (cron GHA diario)
```

El POC original (scripts `0_`, `1_`, `2_`, dashboard) está en [`junk/`](./junk/).

## Web (portal)

En la carpeta [`web/`](./web/) hay una aplicación Next.js.

```bash
cd web && npm install && npm run build-data && npm run dev
```

**Producción:** [`docs/production-web.md`](docs/production-web.md).
