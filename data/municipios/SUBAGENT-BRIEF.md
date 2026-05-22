# Brief subagente — portal del ayuntamiento

## Objetivo (único)

Conseguir **licencias** y **proyectos/expedientes** de un municipio **desde el portal del ayuntamiento** (sede electrónica, visor urbanístico, datos abiertos, API).

**No** es objetivo re-filtrar el BOCM regional (eso ya existe en `web/public/data/projects.json`). El orquestador puede usar `bocm_legacy` solo como atajo de desarrollo; el subagente no debe trabajar en eso.

## Entregables del subagente

1. `data/municipios/<slug>/manifest.yaml` — `portal.base_url` + `portal.adapter`
2. `municipio/adapters/<slug>.py` — clase `AyuntamientoAdapter`

**No ejecutar** el orquestador; solo entregar YAML + código.

## manifest.yaml

```yaml
portal:
  base_url: "https://www...."
  adapter: municipio.adapters.mostoles:MostolesAyuntamientoAdapter
  config: { ... }

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

### proyectos.jsonl

`id`, `municipio`, `titulo`, `fecha`, `tipo`, `url` (+ `source: ayuntamiento`)

## Orquestador (humano / CI)

```bash
cd poc-bocm
PYTHONPATH=. python -m municipio run --municipio mostoles --step all
```

Salida: `output/municipios/<slug>/licencias.jsonl`, `proyectos.jsonl`, `parity-report.json`.
