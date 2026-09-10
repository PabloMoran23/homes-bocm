# Canillas de Albaida-Cómpeta — investigación (artefacto de cola)

**Slug:** `canillas-de-albaida-competa`  
**Nombre en cola:** Canillas de Albaida-Cómpeta  
**Provincia (cola):** Canillas de Albaida-Cómpeta/Málaga  
**Comunidad autónoma:** Andalucía  
**Boletín:** BOJA (`boja`, 1 entrada)

## Conclusión

**No existe un municipio español llamado «Canillas de Albaida-Cómpeta».** El slug procede de un artefacto de parseo del histórico BOJA/CCAA: el campo `municipio` del CSV contiene dos ayuntamientos vecinos de la Axarquía (Málaga) concatenados con guion:

| Municipio real | Slug | Estado en pipeline |
|----------------|------|-------------------|
| Canillas de Albaida | `canillas-de-albaida` | PR abierta [#619](https://github.com/PabloMoran23/homes-bocm/pull/619) — adapter `canillas_de_albaida.py` |
| Cómpeta | `competa` | **Done** — adapter `competa.py` en main desde 2026-08-05 |

No hay portal municipal, sede electrónica ni visor urbanístico para una entidad combinada. Cualquier anuncio BOJA que cite ambos municipios debe atribuirse por separado a cada ayuntamiento.

## Fuentes investigadas (constituyentes)

### Canillas de Albaida

| Fuente | URL |
|--------|-----|
| Sede espublico gestiona | https://canillasdealbaida.sedelectronica.es/board/ |
| Web WordPress | https://canillasdealbaida.es/urbanismo/ |
| Participación ciudadana | https://canillasdealbaida.es/participacion-ciudadana/ |

### Cómpeta

| Fuente | URL |
|--------|-----|
| Sede espublico gestiona | https://competa.sedelectronica.es/board/ |
| Web Diputación Málaga | https://www.competa.es |

## Geometría / visor

- **geometry_status:** `unavailable` (no aplica — sin municipio ni portal propio)
- **Fuentes:** N/A
- **Estrategia:** Los adapters de `canillas-de-albaida` y `competa` cubren cada territorio; el orquestador aplica centroide + jitter.
- **Limitaciones:** Entrada de cola duplicada; debe marcarse `skipped`/`failed` y no re-onboardearse.

## Acción recomendada

1. Marcar `canillas-de-albaida-competa` como `failed` en `queue.yaml` con nota «artefacto BOJA — ver municipios constituyentes».
2. No crear `manifest.yaml` ni adapter para este slug.
3. Corregir en origen el parseo BOJA para separar nombres compuestos (`Canillas de Albaida` + `Cómpeta`).
