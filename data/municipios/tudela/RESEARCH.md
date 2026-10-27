# Tudela — investigación portal ayuntamiento

## URLs base y semillas

| Fuente | URL |
|--------|-----|
| Web municipal | https://www.tudela.es |
| Urbanismo (contenido) | https://www.tudela.es/tu-ciudad/urbanismo-vivienda-obras |
| Anuncios urbanismo | https://www.tudela.es/anuncios/urbanismo-viviendas-obras |
| Instancias / modelos (PDF licencias) | https://www.tudela.es/ventanilla-municipal/instancias-modelos |
| Sede electrónica (STA) | https://sede.tudela.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_HOME |
| Tablón edictos | https://sede.tudela.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all |
| Catálogo trámites | https://sede.tudela.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO |

## Expedientes / planeamiento

- **Tablón STA:** HTML con `var dataset_PTS2_TABLON = [...]` (JSON embebido, ~117 entradas). Remitentes frecuentes: «URBANISMO», «Concejalía de Desarrollo Urbano Sostenible». Expedientes tipo `NN/AAAA/CÓDIGO` en `externString` (p. ej. `23/2026/AACC` para licencias de actividad).
- **Anuncios web:** listado paginado en `/anuncios/urbanismo-viviendas-obras` (10 por página). Detalle en `/anuncio/<slug>` con `<h1>` y fecha en `.fecha_actualidad` (formato `DD-MM-YYYY`). Incluye PEAU, participación ciudadana, consultas de ordenanzas de rehabilitación, etc.
- **Planeamiento documental:** PDFs/ZIP bajo `/docs/urbanismo/` enlazados desde la página de urbanismo (EMOT, PUM en tramitación, PMUS, PEPRI, normativa BON histórica).

## Licencias

- No hay listado público de concesiones con dirección/coordenadas.
- **Tablón STA:** solicitudes/edictos de licencia (actividad, obras) cuando se publican.
- **Catálogo STA:** trámites de licencia/comunicación (páginas informativas, no registro de concesiones).
- **Instancias PDF:** licencia de obras, obras comunicadas, ocupación vía pública, grúas (trámite presencial/telemático).

## Limitaciones

- CMS web antiguo (jQuery 1.7); anuncios requieren una petición por detalle para fecha.
- Tablón mezcla temas no urbanísticos; filtro por palabras clave + remitente.
- Sin API JSON pública del ayuntamiento para expedientes.
- BOCM/CCAA: municipio sin boletín asociado en cola (`bocm_count: 0`).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes consultadas:**
  - [SIUN](https://administracionelectronica.navarra.es/SIUN_Consulta/Index.html) / visor Tracasa (`CODMUN=201` Tudela): planeamiento regional y municipal a nivel de instrumentos y planos, **sin** enlace estable expediente-tablón → polígono por código.
  - IDENA / cartografía 1:1000 SIUN: capas de planeamiento, no acopladas al tablón municipal.
- **Estrategia:** el adapter no rellena `geom_geojson`; el orquestador usa centroide municipal (`manifest` `centroid_lat/lon`) + jitter en `geocode`.
- **Limitaciones:** publicaciones mayoritariamente PDF/HTML; visor autonómico no expone query por número de expediente del ayuntamiento.
