# Santa Marta de Tormes — investigación portal ayuntamiento

**Municipio:** Santa Marta de Tormes (`santa-marta-de-tormes`)  
**Comunidad:** Castilla y León (`castilla-y-leon`)  
**Boletín:** BOCYL (`bocyl`, 5 entradas históricas)

## URLs base y páginas semilla

| Fuente | URL | Formato | Uso |
|--------|-----|---------|-----|
| Web municipal | https://www.santamartadetormes.es | CMS propio (Bootstrap) | Urbanismo, PGOU, modificaciones |
| Urbanismo (hub) | https://www.santamartadetormes.es/urbanismo | HTML | Índice de ~17 actuaciones urbanísticas |
| PGOU | https://www.santamartadetormes.es/plan-general-de-ordenacion-urbana-pgou | HTML + PDF | Documento PGOU completo (PDF) |
| Sede electrónica | https://santamartadetormes.sedelectronica.es/ | STA (referencia) | **Inaccesible** desde red del agente (timeout) |
| Mapa web | https://www.santamartadetormes.es/mapa-web | Leaflet | Mapa general municipal, sin capas urbanísticas enlazadas a expedientes |

## Cómo se listan expedientes

- **Portal web:** cada actuación urbanística es una página estática con `<h1>` descriptivo y metadatos JSON-LD (`datePublished`).
- **Sectores PGOU** referenciados en títulos: UZ-7, UNC-6, UNC-1-A, UNC-A3, etc.
- **PDFs:** el PGOU completo en `/pics/contenido/COMPLETO del PGOU...pdf`; páginas individuales suelen ser texto sin PDF adjunto.
- **Sin tablón STA scrapeable:** la sede electrónica no responde en el entorno de scraping.

## Cómo se publican licencias

- No hay listado público tabular de licencias de obra concedidas con dirección o coordenadas.
- Trámites de licencia/obra se gestionan vía sede electrónica (inaccesible en pruebas).
- Páginas informativas: ITE (`/inspeccion-tecnica-de-edificios`), requerimientos técnicos (`/requerimientos-tecnicos`).
- El adapter incluye estas páginas como filas informativas (patrón Pozuelo/Medina del Campo).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — filtro `n_mun='Santa Marta de Tormes'`, campo sector `n_num_sect` (p. ej. `UZ-7`, `UNC-6`, `UNC-1-A`, `UNC-A3`).
  - ~20 sectores PGOU con polígonos MultiPolygon en EPSG:4326.
  - Mapa web municipal (Leaflet) sin visor urbanístico con enlace expediente→geometría.
- **Estrategia:** si el título/URL incluye código de sector (`UZ-7`, `UNC-6`, `UNC-1A` → normalizado a `UNC-1-A`), consultar WFS SIUCyL y rellenar `geom_geojson` + centroide.
- **Limitaciones:**
  - WFS aporta polígonos de sector PGOU, no del expediente individual ni de licencias de obra.
  - Modificaciones puntuales sin código de sector (p. ej. artículos normativa, ref. catastral) no tienen geometría en WFS.
  - Sede electrónica inaccesible; sin tablón de anuncios scrapeable.

## Limitaciones

- Sede `santamartadetormes.sedelectronica.es` no responde (timeout) desde red del agente.
- Sin API ni dataset de licencias concedidas.
- Portal web actualiza planeamiento pero no expone expedientes individuales con geometría fina.
- Mayoría de filas de proyectos son documentación de planeamiento histórico (2015–2016).

## Referencia de implementación

Crawl portal web: `municipio/adapters/pozuelo.py`  
Geometría WFS SIUCyL: `municipio/adapters/medina_del_campo.py`, `municipio/adapters/salamanca.py`
