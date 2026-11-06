# Torrox — investigación portal urbanismo

## URLs base y semillas

- Web oficial (HTTP; el dominio en HTTPS expone **certificado caducado**): `http://www.torrox.es`
- Menú **Ayuntamiento → Urbanismo** carga por AJAX vistas bajo `/sac/`:
  - Servicio de urbanismo (normativa, declaración responsable obras menores): `http://www.torrox.es/sac/urba_servicio`
  - PGOU — textos y planos PDF: `http://www.torrox.es/sac/urba_pgou`
  - Adaptación parcial a LOUA (memoria y planos): `http://www.torrox.es/sac/urba_loua`
  - Plan playas (documentación PDF): `http://www.torrox.es/sac/plan_playas`
- Sede electrónica enlazada desde la web: `https://torrox.sedelectronica.es` (y variantes). En este entorno **no es usable**: cadena de redirecciones 302 que curl sigue hasta límite (50) y certificado SSL inválido/caducado en `https://torrox.es`. No se ha podido localizar tablón/API de expedientes de la sede.
- Punto de información catastral (enlace externo a GoolZoom, sin API integrada en el ayuntamiento): `http://www.torrox.es/sac/punto_catastral`

## Cómo se publica el planeamiento

- Listados **HTML** con bloques `enlace_ayto` que enlazan a `http://www.torrox.es/resources/files/<hash>.pdf` (sin metadatos JSON embebidos en la página).
- Tipos de contenido: PGOU (texto refundido, ordenanzas, fichas), adaptación LOUA (memorias y planos voluminosos), normativa de obras menores (ordenanza BOP), Plan playas.

## Licencias de obra

- No hay **listado público** de licencias concedidas en las secciones consultadas; la página de servicio describe trámites y cuelga PDFs de procedimientos (declaración responsable), no resoluciones de concesión con expediente.
- La sede electrónica, donde suele estar el tablón, no ha sido accesible técnicamente.

## Geometría / visor

- `geometry_status`: **unavailable**
- Fuentes: no se ha localizado visor municipal ArcGIS/WFS ni dataset GeoJSON de ámbitos por expediente; solo planos en **PDF** (georreferenciación no extraíble de forma determinista aquí).
- Estrategia adaptador: ingerir **documentos PDF** como filas de proyecto (`entity_type: document`) sin polígono; el orquestador asignará **centroide del municipio + jitter** en geocode.
- Limitaciones: HTTPS roto en `torrox.es`; sede con bucle de redirecciones; contenido urbanístico principalmente **PDF** sin enlace a expediente/GIS.
