# Ruente — investigación portal ayuntamiento

Municipio: **Ruente** (`ruente`), Cantabria. INE **39066**. Boletín: `boc_cantabria`.

## URLs base y semillas

| Fuente | URL | Uso |
|--------|-----|-----|
| Web municipal | https://ruente.es | WordPress (Elementor); bandos, ordenanzas |
| Bandos y anuncios | https://ruente.es/bandos-y-anuncios/ | Categoría WP `11` (6 entradas) |
| Ordenanzas | https://ruente.es/ordenanzas/ | Categoría WP `10` (ordenanzas fiscales urbanísticas, etc.) |
| REST API | https://ruente.es/wp-json/wp/v2/posts | Ingesta determinista de posts |
| Sede electrónica | https://ruente.sedelectronica.es/ | Trámites (sin tablón scrapeable en esta run) |
| Transparencia | http://ruente.cumpletransparencia.es/Ruente/Ordenacion | PGOU/NSM y enlaces a AUCAN |
| AUCAN (Cantabria) | https://aplicacionesweb.cantabria.es/aucan/public/zona/saja/ruente | Archivo planeamiento municipal |
| Territorio Cantabria | https://www.territoriodecantabria.es/ | Contexto autonómico (no usado en scrape) |

## Cómo se listan expedientes / proyectos

- **Planeamiento vigente:** no hay PGOU reciente publicado en la web; el instrumento referenciado es **Normas Subsidiarias Municipales de Ruente** (CRU 05/07/1983; BOC 06/08/1983). Las modificaciones puntuales se documentan en **AUCAN** (aplicación web del Gobierno de Cantabria, descarga documental).
- **Web municipal:** publicaciones en bandos (subvenciones, proyectos DUS-5000 alumbrado, base de datos de áreas degradadas) y **ordenanzas fiscales** (tasa licencias urbanísticas, construcciones/obras).
- **Formato:** HTML WordPress + PDFs en `/wp-content/uploads/`. No hay API JSON de expedientes urbanísticos en la sede accesible sin autenticación.

## Licencias de obra

- No hay dataset ni tablón dedicado a concesiones de licencia con dirección/fecha en abierto.
- Marco normativo publicado: [Ordenanza fiscal reguladora de la tasa por licencias urbanísticas](https://ruente.es/ordenanza-fiscal-reguladora-de-la-tasa-por-licencias-urbanisticas/) y ordenanza de construcciones/instalaciones/obras.
- Tramitación vía sede electrónica (enlace en menú principal).
- El adapter incluye **páginas informativas** de trámite (patrón Pozuelo/Miengo) y entradas de bandos que mencionan licencias/urbanismo.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - WFS SIUCAN Cantabria `Urbanismo:Sectores` (`geoservicios.cantabria.es`) — sin features para INE 39066 / Ruente en el servicio consultado.
  - AUCAN — repositorio documental; no expone geometría vectorial enlazable por expediente en API pública simple.
  - Proyecto municipal «Base de datos de áreas degradadas» — en elaboración; sin visor GeoJSON público en la ficha WP (feb 2026).
- **Estrategia:** metadatos + centroide municipal en orquestador (`manifest.portal.config.centroid`).
- **Limitaciones:** planeamiento solo PDF/HTML; sin visor ArcGIS municipal; AUCAN y transparencia pueden bloquear bots (Incapsula) desde algunos egress.

## Limitaciones generales

- Portal transparencia con protección WAF (Incapsula) en HTTPS desde el entorno del agente.
- Sede electrónica redirige a `info.0` (sin listado de anuncios scrapeado).
- Paginación WP REST acotada a 20 páginas × 100 posts.
- Licencias concedidas no publicadas de forma tabular.

## Referencia adapter

Patrón cercano: `municipio/adapters/miengo.py` (Cantabria, WP + AUCAN + WFS), adaptado a REST API de `ruente.es`.
