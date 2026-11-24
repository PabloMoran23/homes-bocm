# Vila-seca — investigación portal ayuntamiento

Municipio: **Vila-seca** (`vila-seca`) — Catalunya, Tarragona. INE **43177**. Sin boletín regional asociado en cola BOCM.

## URLs base

| Recurso | URL |
|---------|-----|
| Web municipal (Joomla / Helix) | https://vila-seca.cat |
| Urbanismo (ES) | https://vila-seca.cat/es/urbanismo |
| Urbanisme (CA) | https://vila-seca.cat/ca/urbanisme |
| Trámites urbanismo | https://vila-seca.cat/es/tramits-urbanisme |
| Sede electrónica (espublico gestiona) | https://vila-seca.eadministracio.cat |
| Tablón de anuncios | https://vila-seca.eadministracio.cat/board |
| Geoportal urbanístico (EnMapa / Nexus Geographics) | https://geoportal.vila-seca.cat/urbanisme/ |
| Info geoportal en web | https://vila-seca.cat/es/geoportal-urbanistico |
| PGOU normes (PDF) | https://geoportal.vila-seca.cat/urbanisme/assets/doc/PGOU_ANNEXOS_2023.pdf |
| RPUC Generalitat (cerca expedients) | https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=43177 |

## Cómo se listan expedientes / planeamiento

### Tablón sede (espublico / Wicket)

HTML en `/board` con filas `<td class="class_name">`, expediente (`class_folderCode`), procedimiento (`class_folderName`), categoría, descripción, fecha (`class_dateFrom` DD/MM/YYYY), enlace `preview-document/{uuid}`.

Procedimientos urbanísticos observados (nov 2026):

- **Planejament General** — modificaciones PGOU, suspensiones de licencias (con planol PDF).
- **Llicències Urbanístiques** — anuncios BOP/BOPT (p. ej. aprobación PAE).

### Web Joomla

Páginas informativas de trámites bajo `/es/tramits-urbanisme/…` (comunicación de obras, licencia urbanística, PAE, certificados). No hay listado histórico de licencias concedidas con dirección.

### RPUC / Geoportal

- **RPUC** permite búsqueda por municipio (43177) pero requiere formulario web; no hay API REST pública scrapeable por código de expediente del tablón.
- **Geoportal** muestra PGOU, sectores y parcelas (identify por coordenadas / referencia catastral) vía capas WMS internas al frontend Angular; configuración embebida en bundles EnMapa sin endpoint documentado enlazado al número de expediente del tablón.

## Licencias de obra

No hay dataset abierto de licencias concedidas con coordenadas. Fuentes:

1. **Trámites** telemáticos en vila-seca.cat (informativos).
2. **Tablón** — anuncios puntuales bajo procedimiento «Llicències Urbanístiques» cuando se publican.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Geoportal EnMapa (`geoportal.vila-seca.cat/urbanisme/`) — OpenLayers + WMS Nexus; consulta por parcela/sector, no por `class_folderCode` del tablón.
  - RPUC Gencat — expedientes normativos, sin geometría directa en respuesta HTML.
- **Estrategia:** el adapter documenta semillas del visor y PGOU; no hay query determinista expediente→polígono. El orquestador usa centroide municipal + jitter (`geocode`).
- **Limitaciones:**
  - Config WMS no expuesta como ArcGIS REST `query?where=expediente=…`.
  - Anuncios del tablón son PDFs/planoles sin georreferencia embebida scrapeable.
  - Posible enriquecimiento futuro vía referencia catastral extraída de PDF (fuera de alcance MVP).

## Limitaciones generales

- Sede y tablón accesibles por HTTP; SSL OK.
- Tablón mezcla urbanismo con personal, subvenciones y tributos — filtrado por procedimiento en adapter.
- Sin RSS de noticias urbanísticas verificado en vila-seca.cat.
