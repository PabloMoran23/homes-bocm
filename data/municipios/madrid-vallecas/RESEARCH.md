# Madrid-Vallecas — investigación

**Slug cola:** `madrid-vallecas`  
**Fecha:** 2026-09-22  
**BOCM:** 1 aviso parseado (`bocm_count: 1`)

## Hallazgo principal

**No es un municipio INE.** El slug procede de un **artefacto del parseo BOCM**: el campo
`municipio` del CSV contiene la cadena `Madrid-Vallecas`, que no corresponde a ninguna entidad
local del catastro/INE sino a una **referencia geográfica al área de Vallecas** (distritos
municipales de Madrid capital: Villa de Vallecas y Puente de Vallecas).

### Proyecto BOCM subyacente

El único aviso en cola se corresponde con actuaciones de planeamiento en el ámbito
**UZPp 02.04 «Desarrollo del Este-Los Berrocales»** (Villa de Vallecas, Madrid):

| Campo | Valor |
|-------|-------|
| Sector | UZP 02.04 «Los Berrocales» |
| Expediente SIGMA | `711/2020/18164` (reparcelación, aprob. 29-dic-2022) |
| BOCM reparcelación | BOCM nº 16 de 19-ene-2023 (`bocm-2023-01-19-56-ed31f0ca6d346d9d`) |
| Municipio INE real | **Madrid** (capital) |
| Distrito | Villa de Vallecas |

Otros expedientes SIGMA del mismo ámbito (ya en pipeline `madrid`):

- `714/2003/02458` — Plan Parcial UZP 2.04 Desarrollo del Este-Los Berrocales
- `714/2003/03039` — UZP 2.04 Desarrollo del Este-Los Berrocales

El aviso aparece en `sector-geometries.geojson` con `municipio: Madrid-Vallecas` y
`provincia_linea: Madrid-Vallecas` por error de extracción del parser (debería ser `Madrid`).

## Fuentes del portal

Vallecas no tiene ayuntamiento propio. Las fuentes urbanísticas son las de **Madrid capital**:

| Fuente | URL | Adapter / pipeline |
|--------|-----|-------------------|
| Visor planeamiento SIGMA | https://geoportal.madrid.es/IDEAM_WBGEOPORTAL/visor_planeamiento.iam | `municipio.adapters.madrid` |
| Visor expedientes | https://servpub.madrid.es/VSURB_WBVISOR/ | `sector_geometry/madrid_viso_fetch.py` |
| Transparencia — Los Berrocales | https://transparencia.madrid.es/.../02-04-Desarrollo-del-Este-Los-Berrocales-/ | Documentación PDF |
| Datos abiertos licencias | https://datos.madrid.es | `sector_geometry/madrid_licencias_download.py` |
| Junta compensación | https://losberrocales.es | Sitio promotor (no portal municipal) |

**No existe** portal ayuntamiento ni sede electrónica para «Madrid-Vallecas».

## Geometría / visor

- **geometry_status:** `unavailable` (a nivel de este slug de cola)
- **Motivo:** Entrada sin municipio INE; la geometría del ámbito UZP 02.04 está en el visor
  SIGMA de Madrid capital (`has_geometry: true` en expedientes `714/2003/*`, `711/2020/18164`).
- **Fuentes GIS relevantes (ya cubiertas por adapter `madrid`):**
  - ArcGIS SIGMA: capas `tramitados_ad`, `urbanizacion`, `gestion` (geoportal.madrid.es)
  - Visor web: `servpub.madrid.es/VSURB_WBVISOR/seguimiento/expPlaneamiento.iam?exp=711/2020/18164`
- **Estrategia:** No aplicable — usar adapter `madrid` (SIGMA) y corregir `municipio` en parser
  BOCM de `Madrid-Vallecas` → `Madrid`.
- **Limitaciones:** El parser BOCM genera slug de cola para alias geográficos compuestos
  (`Madrid-<barrio>`) que no son municipios INE.

## Decisión

- **Sin `manifest.yaml` ni adapter:** no hay entidad local ni portal scrapeable independiente.
- **Cola:** marcar como `skipped` (análogo a `madrid` capital y `madrid-alcobendas-*`).
- **Recomendación parser/cola:** normalizar en `aggregate_municipios_from_csv` los valores
  `municipio` que empiecen por `Madrid-` (salvo municipios reales de la CM) reasignándolos
  al slug `madrid`; o filtrar alias `Madrid-<distrito>` conocidos.

## Datos extraídos

- Proyectos: **N/A** (sin adapter — cubiertos por `madrid` SIGMA)
- Licencias: **N/A** (cubiertas por `madrid` open data)
- Parity: **N/A**
- geometry_status: **unavailable** (en este slug; disponible vía `madrid`)
