# Municipios — portal del ayuntamiento

## Objetivo

Por cada municipio: **licencias** + **proyectos** extraídos del **portal del ayuntamiento**.

El BOCM regional ya alimenta la web global; este pipeline no duplica ese trabajo salvo `proyectos.source: bocm_legacy` (solo debug).

## Roles

| Rol | Responsabilidad |
|-----|-----------------|
| **Subagente** | `manifest.yaml` + `AyuntamientoAdapter` en `municipio/adapters/<slug>.py` |
| **Orquestador** | Lee YAML → `licencias_*`, `proyectos_*`, `validate` |

## Piloto

`mostoles`, `getafe`, `pozuelo-de-alarcon` — adapters pendientes.

## Comandos

```bash
cd poc-bocm
pip install -r requirements-municipio.txt
PYTHONPATH=. python -m municipio run --municipio mostoles --step all
```

Ver `SUBAGENT-BRIEF.md`.
