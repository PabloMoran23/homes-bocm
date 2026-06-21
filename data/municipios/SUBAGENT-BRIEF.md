# Brief subagente — portal del ayuntamiento

## Objetivo (único)

Conseguir **licencias** y **proyectos/expedientes** de un municipio **desde el portal del ayuntamiento** (sede electrónica, visor urbanístico, datos abiertos, API).

**No** es objetivo re-filtrar el BOCM regional (eso ya existe en `web/public/data/projects.json`). El orquestador puede usar `bocm_legacy` solo como atajo de desarrollo; el subagente no debe trabajar en eso.

## Entregables del subagente

1. `data/municipios/<slug>/manifest.yaml` — `portal.base_url` + `portal.adapter`
2. `municipio/adapters/<slug>.py` — clase `AyuntamientoAdapter`
3. `data/municipios/<slug>/RESEARCH.md` — incluye sección **Geometría / visor**

**No ejecutar** el orquestador; solo entregar YAML + código.

## manifest.yaml

```yaml
portal:
  base_url: "https://www...."
  adapter: municipio.adapters.mostoles:MostolesAyuntamientoAdapter
  config:
    request_delay_s: 0.35
    # Opcional si hay visor GIS:
    # geometry:
    #   kind: arcgis_mapserver
    #   base_url: "https://..."
    #   layer_id: 0

licencias:
  enabled: true

proyectos:
  enabled: true
  source: ayuntamiento
```

## AyuntamientoAdapter (4 métodos)

```python
class MostolesAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_licencias(self, out_jsonl: Path) -> dict: ...
    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict: ...
    def backfill_proyectos(self, out_jsonl: Path) -> dict: ...
    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict: ...
```

### licencias.jsonl (paridad mínima Madrid)

`id`, `fecha_concesion`, `tipo`, `distrito`, `lat`, `lon` (+ `source: ayuntamiento`)

Campos opcionales de geometría (misma convención que proyectos).

### proyectos.jsonl

Campos mínimos:

`id`, `municipio`, `titulo`, `fecha`, `tipo`, `url` (+ `source: ayuntamiento`, `lat`, `lon`, `coord_source`)

**Geometría (obligatorio intentar, opcional conseguir):**

Si el portal expone delimitación del ámbito/expediente, el adapter **debe** incluirla:

| Campo | Descripción |
|-------|-------------|
| `geom_geojson` | GeoJSON Geometry (`Polygon`, `MultiPolygon`, …) en WGS84 |
| `geometry_source` | `portal_visor_arcgis`, `portal_wfs`, `portal_geojson`, … |
| `geometry_source_url` | URL de la query o dataset usado |
| `coord_source` | `portal_geometry_centroid` si solo hay polígono sin punto explícito |

Patrones habituales (prioridad):

1. **ArcGIS MapServer / FeatureServer** — `returnGeometry=true`, `outSR=4326`, `f=geojson` (ver `sector_geometry/madrid_ayto_sync.py`)
2. **GeoJSON/WFS** en datos abiertos o geoportal
3. **Enlace al visor** con `objectId` / código de expediente → query puntual

Si **no** hay fuente GIS pública, documentarlo en `RESEARCH.md` (`geometry_status: unavailable`) y deja `geom_geojson` ausente; el orquestador aplicará centroide + jitter.

Helpers compartidos: `municipio/geometry.py` (`record_geometry`, `geometry_bbox`, …).

Tras el scrape, el orquestador ejecuta **geocode** (centroide del polígono o del municipio + jitter) y **sync_supabase**
si hay `SUPABASE_DB_URL`.

## Orquestador (humano / CI)

```bash
cd poc-bocm
PYTHONPATH=. python -m municipio run --municipio mostoles --step all
```

Salida: `output/municipios/<slug>/licencias.jsonl`, `proyectos.jsonl`, `parity-report.json`.

`parity-report.json` incluye `with_geometry` (informativo; no bloquea si es 0).
