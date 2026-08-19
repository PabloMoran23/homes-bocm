# Candelaria — investigación portal ayuntamiento

Municipio: **Candelaria** (`candelaria`)  
Provincia: Santa Cruz de Tenerife · CCAA: Canarias  
Código INE municipio (Grafcan): `38011`

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal (WordPress) | https://www.candelaria.es/ | Noticias, áreas, formularios (certificado SSL autofirmado → `insecure_ssl`) |
| Sede electrónica principal (Galileo GIYS) | https://sedeelectronica.candelaria.es/ | Trámites, edictos, tablón, transparencia |
| Sede alternativa | https://candelaria.sedelectronica.es/ | Carpeta ciudadana (requiere certificado) |
| Área urbanismo | https://www.candelaria.es/areas/planificacion-y-gestion-urbanistica/ | Noticias urbanísticas, enlaces sede/transparencia |
| Descarga solicitudes | https://www.candelaria.es/descarga-de-solicitudes-last/ | PDFs licencias (obra mayor/menor, urbanización, vado, cambio uso…) |
| Categoría WP | https://www.candelaria.es/category/planificacion-gestion-urbanistica/ | Noticias PGO, convenios licencias, obras |
| Edictos RSS | https://sedeelectronica.candelaria.es/publico/sindicacion/edictos/RSS | Sindicación edictos (~44 ítems activos) |
| Tablón edictos | https://sedeelectronica.candelaria.es/publico/tablon | Listado HTML edictos |
| Transparencia urbanismo | https://sedeelectronica.candelaria.es/transparencia/indice/indicador/IT21/11 | Indicador planeamiento (actas pleno, documentos) |
| Procedimientos | https://sedeelectronica.candelaria.es/publico/procedimientos | Catálogo trámites municipales |

## Cómo se listan expedientes / proyectos

- **WordPress:** posts en categoría `planificacion-gestion-urbanistica` (convenios licencias, obras municipales, PGO) y PDFs en `wp-content/uploads/`. Descubrimiento vía sitemap (`post-sitemap*.xml`) filtrando URLs con `urbanismo`, `planeam`, `licenc`, `informacion-publica`, `pgo`, `convenio`.
- **Sede Galileo:** edictos en HTML + RSS XML; sin API JSON pública. Ejemplo urbanístico: «Exp 1144/2020 aprobación modif. sustancial PGO Huertas D. Pablo».
- **Transparencia:** actas de pleno en PDF (no indexadas por expediente urbanístico).
- **No hay** visor municipal de expedientes urbanísticos ni listado tabular de proyectos en curso.

## Cómo se publican licencias

- **No hay** listado público de licencias concedidas con coordenadas ni decretos tabulados.
- Formularios en **descarga-de-solicitudes-last**: SOL-LICENCIA-OBRA-MAYOR, SOL-LICENCIA-OBRA-MENOR, SOL-LICENCIA-PROYECTO-URBANIZACIÓN, comunicación previa, cambio uso, segregación, etc.
- Sede: catálogo de procedimientos y carpeta ciudadana (requiere certificado digital).
- Edictos RSS incluyen «padrón de vados» (tasa licencia vado) pero no concesiones de obra con ubicación.
- El adapter devuelve filas informativas de trámites + formularios; `min_rows: 0` aceptable para licencias reales.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - SITCAN Open Data: https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-candelaria (21 recursos SIPU/PDF/HTML del PGO y modificaciones)
  - IDECanarias WMS planeamiento: `https://idecan2.grafcan.es/ServicioWMS/Planeamiento`
  - Visor GRAFCAN: https://visor.grafcan.es/visorweb/
  - GeoBDP: https://geobdp.grafcan.es/core/documentos/ (instrumentos PGO Candelaria)
- **Estrategia:** el planeamiento municipal está sistematizado a nivel autonómico (capas vectoriales PGO, AUAC, modificaciones) pero **sin campo de enlace** al código de expediente del tablón/edicto municipal. No es posible consultar geometría por `exp. 1144/2020` desde el portal.
- **Limitaciones:** sin visor municipal ArcGIS/WFS con expedientes; edictos solo PDF/HTML; SSL autofirmado en www.candelaria.es. El orquestador usará centroide municipal + jitter.

## Limitaciones generales

- Certificado SSL autofirmado en www.candelaria.es (requiere `insecure_ssl` en adapter).
- Sede Galileo: edictos RSS limitado (~44 entradas); sin paginación API.
- Sin re-parse BOCM; 4 entradas en `boc_canarias` ya en `projects.json`.
