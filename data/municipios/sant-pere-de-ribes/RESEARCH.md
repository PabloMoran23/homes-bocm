# Sant Pere de Ribes — investigación portal ayuntamiento

## URLs base y semillas

| Fuente | URL | Uso |
|--------|-----|-----|
| Web corporativa (Liferay) | https://www.santperederibes.cat | Secciones `ajuntament/informaciourbanistica/*` (gestió, projectes, planejament PGOU/PAUM/derivat) |
| Documentos | `https://www.santperederibes.cat/documents/10180/<folder>/<nombre>.pdf/<uuid>` | PDFs de expedientes, edictos, memòries |
| Sede (Liferay) | https://seuelectronica.santperederibes.cat/seuelectronica | Trámites + información pública (`informacio-publica/*`) |
| Seu-e (AOC transparència) | https://seu-e.cat/es/web/santperederibes/govern-obert-i-transparencia | Urbanismo, edictos, proyectos normativos en curso (portlet `aoctransparenciavisualitzaciopagina`) |
| Sitemap | https://www.santperederibes.cat/sitemap.xml | Descubrimiento de URLs urbanísticas (filtrado `/en/`) |

## Proyectos / expedientes

- **Listado:** no hay API JSON municipal. La gestión urbanística se publica como **páginas Liferay** con enlaces a carpetas `/documents/…` (vigents / en tràmit, projectes, modificacions PGOU, PAUM, planejament derivat).
- **Seu-e:** transparencia con tablero de edictos (`tauler-d-edictes-i-anuncis`) y estudios de impacto; parte del contenido se carga vía portlet JavaScript (tablas DataTables), pero las páginas de urbanismo enlazan PDFs en `santperederibes.cat/documents/…`.
- **RPUC:** https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=08231 (consulta expedientes de planeamiento INE **08231**).

## Licencias de obra

- No hay tablón estructurado de licencias concedidas con coordenadas.
- Trámites informativos: cita con técnicos de urbanismo, instancia genérica en sede, sección obres en espacio público.
- Algunos **edictos** en documentos de gestión urbanística mencionan obras/licencias (PDF); el adapter los captura cuando el título/enlace coincide con patrones de licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Visor MUC Generalitat: https://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi=08231&set-locale=ca
  - RPUC (metadatos + consulta expediente, sin GeoJSON directo en scrape)
  - Enlaces desde seu-e «Normativa d'urbanisme» a RPUC/MUC
- **Estrategia:** el adapter ingiere metadatos + URLs de documentos y referencias RPUC/MUC; no hay REST ArcGIS/WFS por código de expediente enlazado al PDF. El orquestador geocode usa `centroid` del manifest + jitter.
- **Limitaciones:** certificado SSL de `www.santperederibes.cat` falla verificación en entornos estándar (`insecure_ssl: true` en manifest). Tablero seu-e de edictos depende de JS para listados completos; el crawl usa semillas HTML + sitemap.

## Limitaciones operativas

- Páginas con cientos de PDF (p. ej. `projectes/vigents`) — el adapter limita filas por página (`max_doc_rows_per_page`) agrupando por carpeta Liferay.
- `seuelectronica.santperederibes.cat` puede responder vacío desde algunas redes; la web principal y seu-e suelen ser suficientes.
