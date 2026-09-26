# Estructura ideal del repositorio

> Documento de referencia para la auditoría y reorganización de `homes-bocm`.
> Define hacia qué estructura queremos migrar y por qué. Las issues abiertas en
> GitHub (etiquetadas con las categorías descritas al final) apuntan a acercar el
> repo a esta estructura.

## 1. La idea en una frase

El proyecto hace **tres cosas**, y la estructura del repo debería reflejarlas de
forma obvia:

1. **Scrapers** — obtienen datos crudos de fuentes externas (BOCM, otros
   boletines autonómicos, portales de ayuntamientos, SIGMA/visor/NTI de Madrid).
2. **Workflows** — ejecutan los scrapers periódicamente y **pueblan la base de
   datos**, tanto en su forma *cruda* (`raw`) como *transformada*.
3. **Web** — muestra el contenido de la base de datos.

Todo lo demás (esquema de BD, utilidades compartidas, configuración, docs) es
soporte de esos tres pilares.

## 2. Problema actual (resumen)

- La **raíz** mezcla POC y producción. El POC (`0_quick_test.py`, `1_collect_bocm.py`, …) está en `junk/`.
- Hay **dos pipelines paralelos que no se conocen entre sí**: `municipio/`
  (un adapter por ayuntamiento) y `sector_geometry/` (Madrid capital: SIGMA,
  visor, NTI). Duplican lógica de geometría (SITCM/ArcGIS), matching BOCM y
  normalización de texto.
- **`db/`** mezcla producción, librerías compartidas y rutas *legacy* de SQLite.
  Conviven **7 ficheros `schema*.sql`**, **21 migraciones** de Supabase y DDL
  embebido en Python: tres fuentes de verdad para el esquema.
- **Duplicación transversal**: `pdf_to_text` copiado en ≥5 scripts, dos jobs
  "nightly" casi gemelos, IP del LLM hardcodeada en 6 sitios, `_write_jsonl`
  copiado en ~50 adapters.
- El **README** describe únicamente el POC original; el flujo real de producción
  vive disperso en docstrings.
- La **web** arrastra ~2.500 líneas de exploradores *legacy* huérfanos y un
  `build-data.mjs` monolítico de ~2.000 líneas.

## 3. Estructura objetivo

```
homes-bocm/
├── README.md                 # Describe los 3 pilares y cómo corren (actualizado)
├── pyproject.toml            # Dependencias Python unificadas (reemplaza requirements-*.txt sueltos)
├── .env.example
│
├── scrapers/                 # ── PILAR 1: obtención de datos crudos ──
│   ├── common/               #   utilidades compartidas (hoy duplicadas por todo el repo)
│   │   ├── pdf.py            #     pdf_to_text único (hoy repetido ≥5 veces)
│   │   ├── llm.py            #     ex boletin_llm_parse.py: config LLM + prompts
│   │   ├── fingerprint.py    #     ex project_fingerprint.py
│   │   ├── http.py           #     cliente HTTP + user-agent + reintentos comunes
│   │   └── geo/              #     SITCM (WFS) + ArcGIS + normalización de texto UNIFICADOS
│   │
│   ├── boletines/            #   BOCM + CCAA + DOGC (fetch histórico + parse LLM)
│   │   ├── fetch.py          #     ex fetch_history.py
│   │   └── parse.py          #     ex parse_history_nightly.py + parse_ccaa_history_nightly.py (unificados)
│   │
│   ├── municipios/           #   scraping de ayuntamientos (ex paquete municipio/)
│   │   ├── cli.py            #     python -m scrapers.municipios
│   │   ├── orchestrator.py
│   │   ├── adapters/
│   │   │   ├── base.py       #     clase base con _write_jsonl, _stable_id, fetch… (hoy copiados ~45 veces)
│   │   │   └── <slug>.py
│   │   └── ...
│   │
│   └── madrid/               #   Madrid capital (ex sector_geometry/ parte madrid_*)
│       ├── sigma/            #     ayto SIGMA + cruce BOCM
│       ├── visor/            #     visor VSURB + árbol NTI
│       ├── nti/              #     extracción de métricas PDF
│       └── sectores/         #     worker de geometría de sectores (ex worker/enqueue/resolvers)
│
├── db/                       # ── PILAR 2 (datos): esquema + carga ──
│   ├── migrations/           #   ÚNICA fuente de verdad del esquema (Supabase). Elimina schema*.sql sueltos
│   ├── sync/                 #   output/ (raw) → Supabase (sync_dominio, sync_municipio)
│   ├── export/               #   Supabase → JSON/GeoJSON estáticos para la web
│   └── lib/                  #   librerías compartidas (clasificación, programas, geo_utils, direccion)
│
├── .github/workflows/        # ── PILAR 2 (orquestación): ejecución periódica ──
│                             #   dispara scrapers + sync + export; el README explica cada uno
│
├── web/                      # ── PILAR 3: frontend Next.js ──
│   ├── app/ components/ lib/ public/
│   └── scripts/              #   build-data modular (hoy monolito de 2k líneas)
│
├── data/                     # Configuración declarativa (manifests de municipios). NO código
│
├── output/                   # Artefactos RAW generados (gitignored). Salida de scrapers
│
├── docs/                     # Documentación (este fichero incluido)
│
├── tests/                    # Tests (hoy inexistentes o sueltos dentro de paquetes)
│
└── tools/                    # Utilidades dev/QA de un solo uso (spotchecks, evals, dashboard.html)
```

### Principios

- **Un pilar = una carpeta de primer nivel.** La raíz solo contiene los tres
  pilares (`scrapers/`, `db/` + `.github/workflows/`, `web/`) más soporte
  (`data/`, `docs/`, `tests/`, `tools/`, `output/`). **Cero scripts `.py` sueltos
  en la raíz.**
- **DRY entre pilares.** Todo lo compartido por varios scrapers vive en
  `scrapers/common/`. Geometría (SITCM/ArcGIS), `pdf_to_text`, config del LLM y
  fingerprint tienen **una sola implementación**.
- **Una sola fuente de verdad para el esquema**: `db/migrations/`. Los
  `schema*.sql` y el DDL embebido en Python se eliminan o se generan desde ahí.
- **`raw` vs `transformado` explícito.** Los scrapers escriben `raw` en
  `output/`; los jobs de `db/sync/` lo cargan a Supabase (transformado); los de
  `db/export/` generan el estático que consume la web.
- **POC, experimentos y QA fuera del camino de producción**: van a `tools/` o se
  eliminan. El flujo de producción debe ser trivial de seguir.
- **Nombres importables.** Nada de módulos que empiezan por dígito
  (`3_llm_parse.py`) que obligan a cargar con `importlib`.
- **Tests en `tests/`**, no dentro de los paquetes de producción.

## 4. Mapeo actual → objetivo (resumen)

| Hoy | Objetivo |
|---|---|
| `fetch_history.py` | `scrapers/boletines/fetch.py` |
| `parse_history_nightly.py` + `parse_ccaa_history_nightly.py` | `scrapers/boletines/parse.py` (unificado) |
| `3_llm_parse.py`, `boletin_llm_parse.py` | `scrapers/common/llm.py` |
| `project_fingerprint.py` | `scrapers/common/fingerprint.py` |
| `pdf_to_text` (≥5 copias) | `scrapers/common/pdf.py` |
| `municipio/` | `scrapers/municipios/` |
| `sector_geometry/madrid_*` | `scrapers/madrid/{sigma,visor,nti}/` |
| `sector_geometry/` (worker sectores) | `scrapers/madrid/sectores/` |
| `municipio/gis/` + `sector_geometry/resolvers_madrid*` | `scrapers/common/geo/` |
| `db/schema*.sql` (7 ficheros) | `db/migrations/` (única fuente) |
| `db/sync_*` | `db/sync/` |
| `db/export_*` | `db/export/` |
| `db/sigma_*`, `geo_utils.py`, `direccion.py`, `visor_resumen.py` | `db/lib/` |
| `0_quick_test.py`, `1_collect_bocm.py`, `2_extract_text.py`, `municipio_discover.py`, `try_ccaa_sample_parse.py`, `poc_small_examples.py`, `dashboard.html` | `tools/` o eliminar |
| `requirements-*.txt` (3 ficheros) | `pyproject.toml` |

## 5. Etiquetas de las issues de auditoría

Las issues creadas para migrar hacia esta estructura se etiquetan así:

- **`Fallo de estructura`** — código que no está donde debería.
- **`Código inútil`** — ya no hace nada / no está referenciado.
- **`Código innecesariamente complejo`** — se puede simplificar.
- **`Malas prácticas`** — secretos/IPs hardcodeadas, SSL desactivado, `print` en
  lugar de logging, errores silenciados, etc.
- **`Inconsistencias`** — naming y patrones divergentes para lo mismo
  (`lon`/`lng`, múltiples esquemas, dos estrategias de matching, etc.).
