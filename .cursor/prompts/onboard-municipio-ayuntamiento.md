# Onboarding automático de portales municipales

Eres un agente de Cursor que incorpora **un municipio de la Comunidad de Madrid** al pipeline de portales del ayuntamiento en `poc-bocm` (repo `homes-bocm`).

**En cada ejecución procesas exactamente UN municipio.** No hagas varios en la misma run.

---

## Paso 0 — Reservar municipio

```bash
cd poc-bocm
PYTHONPATH=. python3 -m municipio queue claim
```

Guarda el JSON de salida (`slug`, `nombre`, `bocm_count`). Si la salida es `null` o vacía, termina sin abrir PR y escribe en el resumen: "Cola vacía".

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
   - Limitaciones (sin coords, solo PDFs, SSL, paginación, etc.)

**Referencias obligatorias** (lee antes de implementar):

| Municipio | Adapter | Patrón |
|-----------|---------|--------|
| Pozuelo | `municipio/adapters/pozuelo.py` | Drupal, expedientes IP, crawl semillas |
| Móstoles | `municipio/adapters/mostoles.py` | Tablón sede + GMU documentos |
| Getafe | `municipio/adapters/getafe.py` | Sede STA + gobierno abierto |
| Madrid capital | `sector_geometry/madrid_*.py` | ArcGIS + datos abiertos (NO replicar; es otro pipeline) |

Brief técnico: `data/municipios/SUBAGENT-BRIEF.md`

---

## Paso 2 — Implementar ingesta

### 2a. Manifest

Crea `data/municipios/<slug>/manifest.yaml` siguiendo `data/municipios/_template/manifest.yaml`:

```yaml
slug: <slug>
nombre: "<Nombre oficial>"
provincia: Madrid
comunidad_autonoma: comunidad-madrid

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

- IDs estables: `<slug_prefix>-{lic|proy}-{sha256[:14]}`
- Si no hay licencias publicadas, devuelve páginas informativas de trámites (como Pozuelo) o lista vacía con `min_rows: 0` en validate.
- Usa `urllib` o `requests`; respeta `request_delay_s`; User-Agent identificable.
- No dependas de LLM para el scrape.

### 2c. Ejecutar pipeline local

```bash
pip install -r requirements-municipio.txt
PYTHONPATH=. python3 -m municipio run --municipio <slug> --step all
```

Verifica `output/municipios/<slug>/parity-report.json` → `overall` debe ser `ok` o `partial` (nunca `none` en proyectos).

Opcional: cruce con BOCM existente:

```bash
PYTHONPATH=. python3 -m municipio match --municipio <slug>
```

---

## Paso 3 — Sync a Supabase

El script `db/sync_municipio_to_supabase.py` escribe en `homes.proyecto` y `homes.licencia`.

```bash
# Dry-run (sin credenciales)
python3 db/sync_municipio_to_supabase.py --municipio <slug> --dry-run

# Con credenciales (si SUPABASE_DB_URL está disponible en el entorno)
python3 db/sync_municipio_to_supabase.py --municipio <slug>
```

Si no hay `SUPABASE_DB_URL`, deja el script listo y documenta en la PR que el sync se ejecutará en CI/manual. **No inventes credenciales.**

Tras sync exitoso, opcionalmente exportar datos web:

```bash
python3 db/export_web_data_from_supabase.py
cd web && BUILD_DATA_SCOPE=full npm run build-data
```

---

## Paso 4 — PR a main

**No hay tool de "crear PR" en esta automation.** Usa git + `gh` en la terminal del agente.

1. Crea rama: `automation/municipio-<slug>`
2. Commit solo los archivos del municipio (y `queue.yaml` si aplica):
   - `data/municipios/<slug>/manifest.yaml`
   - `data/municipios/<slug>/RESEARCH.md`
   - `municipio/adapters/<slug_modulo>.py`
   - Actualización de `data/municipios/queue.yaml` (marca el municipio como `done`)
3. **No commitees** `output/municipios/` (está en .gitignore) ni cambios en `web/public/data/`.
4. Push y abre PR con `gh`:

```bash
git checkout -b automation/municipio-<slug>
git add data/municipios/<slug>/ municipio/adapters/<modulo>.py data/municipios/queue.yaml
git commit -m "feat(municipio): portal ayuntamiento <Nombre>"
git push -u origin HEAD
gh pr create --base main --title "feat(municipio): portal ayuntamiento <Nombre>" --body "$(cat <<'EOF'
## Municipio
<Nombre> (`<slug>`)

## Fuentes del portal
- ...

## Datos extraídos
- Proyectos: N filas
- Licencias: N filas
- Parity: ok/partial

## Sync Supabase
- [ ] Ejecutado / Pendiente (falta SUPABASE_DB_URL)

EOF
)"
```

5. Guarda la URL de la PR que devuelve `gh pr create`.

Marca la cola como hecha:

```bash
PYTHONPATH=. python3 -m municipio queue done --municipio <slug> --pr-url "<url de la PR>"
```

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
- [ ] `RESEARCH.md` con fuentes documentadas
- [ ] PR abierta a `main`
- [ ] Cola actualizada (`done` o `fail` con motivo)
