# Úbeda — investigación portal ayuntamiento

## URLs base y páginas semilla

| Fuente | URL | Tipo |
|--------|-----|------|
| Web municipal (Drupal) | https://ubeda.es | CMS Drupal 9 + Porto theme |
| Área urbanismo | https://ubeda.es/es/node/548 | Enlace desde transparencia |
| Portal transparencia (WordPress/Divi) | https://transparencia.ayuntamientodeubeda.com | WP REST API + PDFs |
| Planes urbanísticos | https://transparencia.ayuntamientodeubeda.com/2023/02/02/planes-urbanisticos/ | Listado HTML con ~50 PDFs |
| Transparencia local (Absis) | https://aytoubeda.transparencialocal.gob.es/es_ES/urbanismo | PDFs legacy PGOU/PEPCH |
| Archivos urbanismo legacy | http://ayuntamientodeubeda.com/carga_archivos/urbanismo/ | PDFs directos |
| Sede electrónica | https://sede.ubeda.es | eAdmin (tramites, perfil contratante) |
| Trámites sede | https://sede.ubeda.es/eAdmin/Registrar.do?action=inicioPortalTramites | Formularios licencias/obras |
| Perfil del contratante | https://sede.ubeda.es/eAdmin/PerfilContratante.do?action=verPublicaciones | Contratos obras públicas |
| Portal tributario | https://portaltributario.ayuntamientodeubeda.com | Autoliquidación tasa urbanística |
| Geoportal Diputación Jaén | https://ide.dipujaen.es | WMS cartografía base (EIEL) |
| Datos abiertos transparencia | https://transparencia.ayuntamientodeubeda.com/datos-abiertos/ | Enlace geoportal provincial |

## Cómo se listan expedientes / planeamiento

1. **Transparencia WordPress**: la página «Planes Urbanísticos» publica un listado HTML con enlaces a PDFs (PGOU, PEPCH, planes parciales, modificaciones puntuales, juntas de compensación, reparcelaciones). También hay posts WP vía REST API (`/wp-json/wp/v2/posts`).
2. **Transparencia local (Absis)**: documentos históricos PGOU/PEPCH en `/es_ES/media/{id}`.
3. **Archivos legacy**: PDFs en `carga_archivos/urbanismo/` (consultas previas, modificaciones).
4. **Perfil del contratante**: expedientes de contratación de obras públicas (tipo «Obras») con identificador y descripción.
5. **No hay** listado público de expedientes de licencias urbanísticas individuales ni tablón de anuncios de licencias concedidas.

## Cómo se publican licencias

- La sede electrónica ofrece **formularios de solicitud** (licencia de obras, declaración responsable, ocupación vía pública, etc.) pero **no publica concesiones** en tablón.
- El portal tributario permite autoliquidación de tasa urbanística (ICIO + tasa licencias).
- Las licencias concedidas no están indexadas públicamente; consulta presencial/cita previa en área de Urbanismo.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes exploradas:**
  - Geoportal Diputación Jaén (`ide.dipujaen.es/wms`) — cartografía base MTA10, EIEL, catastro; sin capa de expedientes urbanísticos ni sectores PGOU enlazables por código.
  - Datos abiertos transparencia — enlace al geoportal provincial, no visor municipal de planeamiento.
  - No hay visor urbanístico municipal (ArcGIS, SITUA embebido, WFS de sectores) accesible sin login.
  - Los PDFs de planeamiento no incluyen geometría machine-readable enlazable a expedientes.
- **Estrategia:** no aplicable; el orquestador usará centroide municipal + jitter.
- **Limitaciones:** patrimonio UNESCO (centro histórico); planeamiento solo en PDF; sin API GIS municipal.

## Limitaciones

- Sin tablón público de licencias de obra concedidas.
- Sede en ISO-8859 (latin-1); encoding mixto en algunas páginas.
- Algunos PDFs en dominio legacy `ayuntamientodeubeda.com` (HTTP).
- Perfil contratante solo cubre obras públicas municipales, no licencias privadas.
- BOJA: 2 entradas históricas en CSV (boletín andaluz).
