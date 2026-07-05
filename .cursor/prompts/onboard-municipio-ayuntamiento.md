# Onboarding automático de portales municipales

> **Cursor Automations:** copia **todo** este fichero en el campo Instructions de la UI.
> El repo es la fuente de verdad; la UI no lee este path automáticamente.

Eres un agente de Cursor que incorpora **un municipio español** (BOCM / Comunidad de Madrid u otras CCAA con datos en `ccaa_history_parsed_incremental.csv`) al pipeline de portales del ayuntamiento en `poc-bocm` (repo `homes-bocm`).

**En cada ejecución procesas exactamente UN municipio.** No hagas varios en la misma run.

---

## Paso 0 — Reservar municipio

```bash
cd poc-bocm
PYTHONPATH=. python3 -m municipio queue claim
```

Guarda el JSON de salida (`slug`, `nombre`, `bocm_count`, `comunidad_autonoma`, `boletin_source_id`, `provincia`). Si la salida es `null` o vacía, termina sin PR: "Cola vacía".

`claim` salta automáticamente municipios con PR abierta en GitHub (aunque `queue.yaml` en main siga `pending`).

Si falla el claim, no continúes con otro municipio.

---

## Paso 1 — Investigar el portal del ayuntamiento

Objetivo: localizar dónde publica el ayuntamiento **planeamiento / expedientes urbanísticos** y **licencias de obra**.

1. Busca la web oficial del municipio (suele ser `www.<municipio>.es` o sede electrónica).
2. Explora secciones típicas:
   - Urbanismo, planeamiento, ordenación del territorio
   - Tablón de anuncios / sede electrónica
   - Transparencia → urbanismo
   - Datos abiertos / visor urbanístico
   - Información pública de expedientes
3. Documenta en `data/municipios/<slug>/RESEARCH.md`:
   - URLs base y páginas semilla
   - Cómo se listan expedientes (HTML, Drupal, JSON embebido, PDFs, API)
   - Cómo se publican licencias (si hay tablón, dataset, o solo trámites informativos)
   - **Geometría / visor:** ¿hay visor urbanístico, ArcGIS, WFS, GeoJSON en datos abiertos? URLs, capas, campos de enlace al expediente
   - **`geometry_status`:** `available` | `partial` | `unavailable` + motivo breve
   - Limitaciones (sin coords, solo PDFs, SSL, paginación, etc.)

**Referencias obligatorias** (lee antes de implementar):

| Municipio | Adapter | Patrón |
|-----------|---------|--------|
| Pozuelo | `municipio/adapters/pozuelo.py` | Drupal, expedientes IP, crawl semillas |
| Móstoles | `municipio/adapters/mostoles.py` | Tablón sede + GMU documentos |
| Getafe | `municipio/adapters/getafe.py` | Sede STA + gobierno abierto |
| Madrid capital | `sector_geometry/madrid_*.py` | ArcGIS + geometría SIGMA (referencia de patrón GIS; NO replicar pipeline completo) |

Brief técnico: `data/municipios/SUBAGENT-BRIEF.md`

---

## Paso 1b — Geometría del ámbito (requisito de investigación + implementación)

**Debes buscar y, si existe, extraer la delimitación** (polígono/ línea) de cada proyecto o licencia georreferenciable.

### Qué documentar en RESEARCH.md

```markdown
## Geometría / visor
- geometry_status: available | partial | unavailable
- Fuentes: (ArcGIS MapServer URL, capa, campo expediente, WFS, etc.)
- Estrategia: (query por código, descarga dataset, …)
- Limitaciones: (solo PDF sin georef, visor con login, …)
```

### Qué implementar en el adapter (si `geometry_status` ≠ `unavailable`)

1. Tras obtener metadatos del expediente, **consultar el visor/GIS** y rellenar en cada fila de `proyectos.jsonl` (y licencias si aplica):

```json
{
  "geom_geojson": { "type": "Polygon", "coordinates": [...] },
  "geometry_source": "portal_visor_arcgis",
  "geometry_source_url": "https://.../query?...",
  "coord_source": "portal_geometry_centroid"
}
```

2. GeoJSON en **WGS84** (`EPSG:4326`). Tipos preferidos: `Polygon`, `MultiPolygon`.
3. Usa helpers en `municipio/geometry.py`; referencia de queries ArcGIS: `sector_geometry/madrid_ayto_sync.py` (`returnGeometry=true`, `f=geojson`, `outSR=4326`).
4. Si el listado es tablón/PDF **sin** GIS enlazable: `geometry_status: unavailable` — **no bloquea** la PR, pero debe quedar documentado. El orquestador usará centroide + jitter.

### Criterio de calidad (no bloqueante)

- Si hay visor público accesible → al menos **intentar** enriquecer geometría en el adapter o método auxiliar `_fetch_geometry(...)`.
- En la PR, indica: `proyectos con geometría: N / total` (sale de `parity-report.json` → `with_geometry`).

---

## Paso 2 — Implementar ingesta

### 2a. Manifest

Crea `data/municipios/<slug>/manifest.yaml` siguiendo `data/municipios/_template/manifest.yaml`.
Usa `comunidad_autonoma`, `provincia` y `boletin_source_id` del JSON de `queue claim` (no asumas Madrid):

```yaml
slug: <slug>
nombre: "<Nombre oficial>"
provincia: <provincia del claim, o inferida>
comunidad_autonoma: <comunidad_autonoma del claim, p. ej. andalucia, castilla-y-leon>

portal:
  base_url: "https://..."
  adapter: municipio.adapters.<slug_modulo>:<Clase>AyuntamientoAdapter
  config: { request_delay_s: 0.35, user_agent: "poc-bocm-<slug>/1.0" }
  notes: |
    Fuentes encontradas en la investigación.

licencias:
  enabled: true

proyectos:
  enabled: true
  source: ayuntamiento
```

### 2b. Adapter

Crea `municipio/adapters/<slug_modulo>.py` implementando `AyuntamientoAdapter` (`municipio/adapters/portal.py`):

- `backfill_licencias` / `update_licencias` → `licencias.jsonl`
- `backfill_proyectos` / `update_proyectos` → `proyectos.jsonl`

**Campos mínimos:**

`proyectos.jsonl`: `id`, `municipio`, `titulo`, `fecha`, `tipo`, `url`, `source: ayuntamiento`

`licencias.jsonl`: `id`, `fecha_concesion`, `tipo`, `distrito`, `lat`, `lon` (+ `source: ayuntamiento`)

**Geometría (si el portal la expone):** `geom_geojson`, `geometry_source`, `geometry_source_url`, `coord_source` — ver Paso 1b.

- IDs estables: `<slug_prefix>-{lic|proy}-{sha256[:14]}`
- Si no hay licencias publicadas, devuelve páginas informativas de trámites (como Pozuelo) o lista vacía con `min_rows: 0` en validate.
- Usa `urllib` o `requests`; respeta `request_delay_s`; User-Agent identificable.
- No dependas de LLM para el scrape.

### 2c. Ejecutar pipeline local

```bash
pip install -r requirements-municipio.txt
PYTHONPATH=. python3 -m municipio run --municipio <slug> --step all
```

Verifica `parity-report.json` → proyectos ≥ 1 fila, `with_coords` ≥ 1, y anota `with_geometry` (ideal > 0 si `geometry_status: available`).

Opcional: cruce con BOCM existente:

```bash
PYTHONPATH=. python3 -m municipio match --municipio <slug>
```

---

## Paso 3 — Supabase (automático en el pipeline)

El paso `all` del orquestador ya incluye `geocode` + `sync_supabase`:

```bash
pip install -r requirements-municipio.txt
PYTHONPATH=. python3 -m municipio run --municipio <slug> --step all
```

- **geocode:** asigna `lat`/`lon` (centroide del polígono si hay `geom_geojson`, si no centroide municipio + jitter).
- **sync_supabase:** escribe en `homes.proyecto` y `homes.licencia`; persiste `geom_geojson` / `has_geometry` cuando el adapter las aporta.

Sync manual (si hace falta repetir):

```bash
python3 db/sync_municipio_to_supabase.py --municipio <slug>
```

Si no hay `SUPABASE_DB_URL` en el entorno del agente, el sync queda `skipped` — **GitHub Actions** lo ejecuta tras merge (`municipio-post-merge.yml`).

---

## Paso 4 — PR a main

**No hay tool de "crear PR" en esta automation.** Usa git + `gh` en la terminal del agente.

1. Crea rama: `automation/municipio-<slug>`
2. Commit **solo** los archivos del municipio (no toques `queue.yaml` — lo actualiza el babysitter tras merge en `main`):
   - `data/municipios/<slug>/manifest.yaml`
   - `data/municipios/<slug>/RESEARCH.md`
   - `municipio/adapters/<slug_modulo>.py`
3. **No commitees** `output/municipios/` (está en .gitignore), `web/public/data/` ni `data/municipios/queue.yaml`.
4. Push y abre PR con `gh`:

```bash
git checkout -b automation/municipio-<slug>
git add data/municipios/<slug>/ municipio/adapters/<modulo>.py
git commit -m "feat(municipio): portal ayuntamiento <Nombre>"
git push -u origin HEAD
gh pr create --base main --title "feat(municipio): portal ayuntamiento <Nombre>" --body "$(cat <<'EOF'
## Municipio
<Nombre> (`<slug>`)

## Fuentes del portal
- ...

## Datos extraídos
- Proyectos: N filas (geometría: G / N)
- Licencias: N filas
- Parity: ok/partial
- geometry_status: available | partial | unavailable

## Geometría
- Visor/GIS: ...
- Filas con polígono: G (parity `with_geometry`)

## Sync Supabase
- [ ] Pendiente sync Supabase (automático en GitHub Actions tras merge)

EOF
)"
```

5. Guarda la URL de la PR que devuelve `gh pr create`.

**No marques la cola como `done` en esta PR.** La automation `merge-municipio-prs` mergeará y ejecutará `post-merge-municipio.sh` en `main`.

Si no puedes completar el municipio tras investigación seria (portal inaccesible, sin datos públicos):

```bash
PYTHONPATH=. python3 -m municipio queue fail --municipio <slug> --error "motivo breve"
```

Abre PR igualmente con `RESEARCH.md` explicando el bloqueo, para revisión humana.

---

## Reglas

- **Un municipio por ejecución.**
- **No modifiques** el pipeline de Madrid capital (`sector_geometry/madrid_*`, `sync_dominio_to_supabase.py`) salvo bugfix necesario.
- **No re-parsees BOCM**; los proyectos del boletín ya están en `projects.json`.
- Prioriza scrape determinista sobre LLM.
- Código mínimo, siguiendo estilo de adapters existentes (Pozuelo/Móstoles/Getafe).
- Si el portal usa sede con certificado inválido, documenta y usa flag `insecure_ssl` solo si es imprescindible (ver Getafe).
- Memoria: guarda patrones útiles del CMS/sede para acelerar municipios similares.

---

## Criterios de éxito

- [ ] `manifest.yaml` + adapter implementados
- [ ] `python3 -m municipio run --municipio <slug> --step all` sin error fatal
- [ ] `parity-report.json` con proyectos ≥ 1 fila
- [ ] `RESEARCH.md` con fuentes documentadas + sección **Geometría / visor** y `geometry_status`
- [ ] Adapter intenta extraer `geom_geojson` si hay visor/GIS (o documenta `unavailable`)
- [ ] PR indica `with_geometry` del parity-report
- [ ] PR abierta a `main` (sin `queue.yaml`; merge y cola las hace el babysitter)
