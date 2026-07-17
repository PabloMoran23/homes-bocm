# Palencia — investigación portal ayuntamiento

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal (Drupal 9) | https://www.aytopalencia.es |
| Área urbanismo | https://www.aytopalencia.es/area/urbanismo-e-infraestructura |
| Documentos en trámite (IP) | https://www.aytopalencia.es/area/urbanismo-e-infraestructura/documentos-en-tramite |
| PGOU y modificaciones | https://www.aytopalencia.es/area/urbanismo-e-infraestructura/pgou-y-modificaciones |
| Archivo urbanístico | https://www.aytopalencia.es/area/urbanismo-e-infraestructura/archivo-urbanistico |
| Convenios urbanísticos | https://www.aytopalencia.es/area/urbanismo-e-infraestructura/convenios-urbanisticos |
| Avance PGOU (microsite) | https://pgou.aytopalencia.es/ |
| Sede electrónica (Absis) | https://sede.aytopalencia.es |
| Tablón de edictos | https://sede.aytopalencia.es/castellano/Externos/ASP/enlacesPortada/EnlacesPortadaSede.asp?enlacePortada=tablon |
| Trámites IP (licencias ambientales, etc.) | https://www.aytopalencia.es/tramite/tramites-de-informacion-publica |
| OVC (tributos; STA parcial) | https://ovc.aytopalencia.es/sta/CarpetaPublic/ |

## Cómo se listan expedientes / planeamiento

- **Drupal 9**: tablas HTML estáticas en las secciones de urbanismo con título, fechas de aprobación/publicación y enlaces a PDF (`/sites/default/files/Urbanismo/...`, `/sites/default/files/ayuntamiento/...`).
- **Documentos en trámite**: actualmente un expediente activo — *Avance de la Revisión del PGOU de Palencia* (BOCyL 12-jun-2026, IP 2 meses) con ~20 PDFs descargables.
- **PGOU/modificaciones**: tabla histórica de modificaciones puntuales (URPI, SUNC, sentencias TSJ, etc.) + índice de planos.
- **Archivo urbanístico**: PERI casco antiguo, estudios de detalle, planes parciales históricos (PDFs).
- **Convenios urbanísticos**: tabla de convenios SGE del PGOU 2008.
- **Tablón Absis (ASP.NET WebForms)**: listado renderizado server-side con fecha, unidad tramitadora, tipo documento y título; detalle en popup `dlgVerDetalleAnuncio.aspx?numuint=...`. Incluye anuncio de IP del avance PGOU (Gestión Urbanística).
- **No hay dataset STA embebido** (`dataset_PTS2_TABLON`) como en Segovia/Salamanca; el tablón principal usa Absis, no STA JSON.

## Licencias de obra

- No hay dataset público de concesiones de licencia con coordenadas.
- El tablón municipal publica edictos de diversas materias; las licencias urbanísticas aparecen esporádicamente como anuncios/edictos (no hay subsección TABURB dedicada).
- Trámites informativos en `/tramite/` relevantes: andamios, autorización de comienzo de obra, acceso garajes zona peatonal, modificación régimen división horizontal, trámites de información pública (licencia ambiental, ruina, etc.).
- El catálogo STA en OVC (`dataset_CATSERV`) solo expone trámites tributarios (5 entradas), sin urbanismo.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - **IDEPAL / GIS corporativo** (proyecto DigiPal): https://gis.aytopalencia.es/ — portal anunciado pero no accesible desde entorno CI (timeout / sin respuesta).
  - **Plano llave PGOU**: planos PDF descargables desde índice Drupal (`/pgou-y-modificaciones/indice-planos-pgou`); consulta vinculante requiere cita previa telefónica con servicio de urbanismo.
  - **pgou.aytopalencia.es**: microsite participativo del avance PGOU; paneles y plano a gran escala, sin API GeoJSON/WFS pública.
- **Estrategia:** sin visor ArcGIS/WFS operativo ni enlace expediente→polígono; el orquestador usará centroide municipio + jitter.
- **Limitaciones:** geometría solo en PDFs/planos no georreferenciados; GIS municipal en despliegue (DigiPal); tablón sin coords; licencias no publicadas como dataset.

## Limitaciones del scrape

- Tablón Absis: HTML WebForms sin API JSON; parsing por bloques de fecha + título.
- Muchos PDFs de gran tamaño en avance PGOU (no se descargan, solo se indexan URLs).
- Sin listado estructurado de licencias concedidas (solo trámites informativos + edictos puntuales).
- Boletín regional: BOCyL (`boletin_source_id: bocyl`), 14 entradas históricas ya en pipeline BOCM.
