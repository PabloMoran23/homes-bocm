# Ávila — investigación portal ayuntamiento

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.avila.es |
| Urbanismo | https://www.avila.es/areas-destacadas/urbanismo |
| Planeamiento (K2) | https://www.avila.es/areas-destacadas/urbanismo/planeamiento-urbanistico |
| RSS planeamiento | https://www.avila.es/areas-destacadas/urbanismo/planeamiento-urbanistico?format=feed&type=rss |
| Sede electrónica | https://sede.avila.es/GDCarpetaCiudadano/Sede.do |
| Tablón de anuncios | https://sede.avila.es/GDCarpetaCiudadano/Tablon.do?action=verAnuncios |
| Trámites licencias | https://www.avila.es/tramites/385-licencias |
| Trámites urbanismo | https://www.avila.es/tramites/877-urbanismo |
| eAdmin (alternativa) | https://sede.avila.es/eAdmin/Sede.do |

## Cómo se listan expedientes / proyectos

1. **Joomla K2 + RSS**: la sección *Planeamiento Urbanístico* publica noticias/anuncios (modificaciones PGOU, estudios de detalle, aprobaciones) con enlaces a PDFs en `/images/Documentos PDF para descargar/urbanismo/`. Feed RSS con ~10 entradas históricas.
2. **IDECyL WFS (SiuCyL)**: capas `plau_cyl_instrumentos_ambito`, `plau_cyl_planes_parciales`, `plau_cyl_sectores` filtradas por `n_mun = 'Ávila'`. Devuelven geometría MultiPolygon en EPSG:4326, metadatos (`n_titulo`, `c_id_sect`, `f_aprob`, `url_doc_info`).
3. **Tablón digital (GDCarpetaCiudadano)**: HTML con filas `verAnuncio&id=…`, título, periodo de publicación y PDF firmado (`abrirOriginal`). Búsqueda POST por palabra clave. Pocos anuncios de urbanismo en el listado general (~30 activos, mayoría administrativos).
4. **Trámites WP**: páginas informativas bajo `/tramites/877-urbanismo` (sin expedientes individuales publicados).

No hay visor ArcGIS propio del ayuntamiento ni catálogo STA tipo Segovia/Salamanca.

## Cómo se publican licencias

- **Tablón**: licencias concedidas/notificadas aparecen como PDF en el tablón (cuando se publican); en la muestra actual no hay licencias de obra recientes.
- **Trámites informativos**: `/tramites/385-licencias` enlaza a licencia de obra mayor/menor, ambiental, comunicación previa, cambio de titularidad, ITE, etc. Son páginas descriptivas que redirigen a la sede para iniciar el trámite (`Registrar.do?tipoReg=…`), no listados de concesiones.
- **Sede**: registro telemático vía `GDCarpetaCiudadano/Registrar.do`; sin API pública de licencias otorgadas.

## Geometría / visor

- **geometry_status**: `partial`
- **Fuentes**:
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito` (1 feature PGOU), `urbanismo:plau_cyl_planes_parciales` (19), `urbanismo:plau_cyl_sectores` (74)
  - Filtro: `CQL_FILTER=n_mun = 'Ávila'`, `srsName=EPSG:4326`
- **Estrategia**: descarga WFS por capa en el adapter; enriquecimiento por coincidencia de título para filas RSS/tablón sin geometría propia.
- **Limitaciones**:
  - No hay visor urbanístico municipal con enlace a expediente individual.
  - Licencias del tablón son PDF sin georreferencia.
  - El PGOU consolidado en la web es documentación estática (PDF), no GIS enlazable por expediente.
  - Ámbitos WFS cubren planeamiento (sectores/PP), no licencias puntuales de obra.

## Limitaciones generales

- CMS Joomla/K2 con contenido histórico disperso; RSS limitado a la categoría planeamiento.
- Tablón sin dataset JSON embebido (HTML + búsqueda POST).
- Sin geometría para licencias individuales.
- Boletín regional: BOCyL (`boletin_source_id: bocyl`).
