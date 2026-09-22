# Madrid, Alcobendas, San Sebastián de los Reyes y Paracuellos de Jarama — investigación

**Slug cola:** `madrid-alcobendas-san-sebastian-de-los-reyes-y-paracuellos-de-jarama`  
**Fecha:** 2026-09-22  
**BOCM:** 1 aviso parseado (`bocm_count: 1`)

## Hallazgo principal

**No es un municipio INE.** El slug procede de un **artefacto del parseo BOCM**: el campo
`municipio` del CSV contiene la lista completa de términos afectados por un **plan especial
intermunicipal de la Comunidad de Madrid**, no el nombre de una entidad local.

### Proyecto BOCM subyacente

El único aviso corresponde a actuaciones de planeamiento regional que afectan simultáneamente a:

| Municipio INE | Slug pipeline | Estado cola |
|---------------|---------------|-------------|
| Madrid (capital) | `madrid` (SIGMA) | `skipped` — pipeline propio |
| Alcobendas | `alcobendas` | `done` — PR #4 |
| San Sebastián de los Reyes | `san-sebastian-de-los-reyes` | `done` — PR #23 |
| Paracuellos de Jarama | `paracuellos-de-jarama` | `done` — PR #38 |

Ejemplos documentados en BOCM:

- **Plan Especial del Sistema General Aeroportuario Madrid-Barajas** (AENA), aprobación / EIA
  (BOCM 2019-01-04, resolución 14-nov-2018).
- **Plan Especial / Proyecto Arteria Norte** (Canal de Isabel II), conducción 6,2 km entre
  Alcobendas, San Sebastián de los Reyes y Paracuellos (BOCM 2024-01-04).

Estos expedientes se publican en el **BOCM a nivel autonómico** (Consejería de Medio Ambiente y
Ordenación del Territorio), no en un portal único de ayuntamiento.

## Fuentes del portal

| Entidad | Portal urbanismo | Adapter |
|---------|------------------|---------|
| Alcobendas | https://www.alcobendas.org | `municipio.adapters.alcobendas` |
| San Sebastián de los Reyes | https://www.ssreyes.org | `municipio.adapters.san_sebastian_de_los_reyes` |
| Paracuellos de Jarama | https://www.paracuellos.org | `municipio.adapters.paracuellos_de_jarama` |
| Madrid capital | SIGMA / servpub.madrid.es | `sector_geometry/madrid_*` |

**No existe** web municipal ni sede electrónica para «Madrid, Alcobendas, San Sebastián de los
Reyes y Paracuellos de Jarama».

## Geometría / visor

- **geometry_status:** `unavailable`
- **Motivo:** Entrada de cola sin municipio real; la geometría del ámbito aeroportuario / Arteria
  Norte está en visores autonómicos (SITCM, geoportal CM) y en los adapters municipales
  individuales, no en un portal agregado.
- **Fuentes GIS relevantes (referencia):**
  - SITCM WFS `sitcm:VPLA_V_AMBITO` (por municipio)
  - Visor urbanístico Madrid SIGMA (capital)
- **Estrategia:** No aplicable — usar adapters existentes por municipio INE.
- **Limitaciones:** Proyecto CCAA multi-municipio; el parser BOCM no debe generar slug de cola
  para listas separadas por comas.

## Decisión

- **Sin `manifest.yaml` ni adapter:** no hay portal scrapeable.
- **Cola:** marcar como `skipped` (análogo a `madrid` capital).
- **Recomendación parser/cola:** en `aggregate_municipios_from_csv`, ignorar o dividir valores de
  `municipio` con comas / « y » cuando correspondan a listas multi-municipio de actuaciones
  autonómicas; reasignar el aviso BOCM a los slugs INE correspondientes vía `match_bocm`.

## Datos extraídos

- Proyectos: **N/A** (sin adapter)
- Licencias: **N/A**
- Parity: **N/A**
- geometry_status: **unavailable**
