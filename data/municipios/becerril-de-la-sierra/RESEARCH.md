# Becerril de la Sierra — investigación portal ayuntamiento

**Municipio:** Becerril de la Sierra (Comunidad de Madrid)  
**Fecha:** 2026-08-04  
**BOCM regional (referencia):** 9 avisos

## Resumen

Becerril de la Sierra publica normativa urbanística en la **web corporativa Joomla** (`becerrildelasierra.org`)
y anuncios/trámites en la **sede electrónica espublico gestiona** (`becerrildelasierra.sedelectronica.es`).
Los ámbitos de planeamiento municipal (planes parciales P-* y unidades de actuación UA-*) están en el
**SIT de la Comunidad de Madrid** (WFS `sitcm:VPLA_V_AMBITO`).

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web urbanismo | `https://www.becerrildelasierra.org/index.php/servicios-municipales/109-urbanismo-y-licencias` | Joomla HTML + descargas | NNSS, normativa urbanística, modelos licencia/DR |
| BOCM normativa CM | `https://www.comunidad.madrid/sites/default/files/doc/urbanismo/becerril.pdf` | PDF | Normativa urbanística publicada en BOCM |
| Tablón de anuncios | `https://becerrildelasierra.sedelectronica.es/board/974e6d5e-f59b-11de-b600-00237da12c6a/` | HTML tabla Wicket | Bandos, desbroce parcelas, cobros |
| Catálogo trámites | `https://becerrildelasierra.sedelectronica.es/dossier` | HTML enlaces `/catalog/t/{uuid}` | Licencia urbanística, DRUO, certificados |
| Portal transparencia | `https://becerrildelasierra.sedelectronica.es/transparency/` | Wicket AJAX | Ordenanzas urbanismo (preview-document estático en HTML inicial) |
| Incidencias urbanas | `https://becerrildelasierra-publicform.incidenciasurbanas.com/` | Formulario externo | Consulta incidencias (sin listado público) |
| SIT Comunidad Madrid | `https://idem.comunidad.madrid/geoserver3/ows` | WFS GeoJSON | 23 ámbitos `DS_NOMB_AMB` para `DS_MUNICIPIO='BECERRIL DE LA SIERRA'` |

## Tablón de anuncios (`/board/`)

Tabla HTML con columnas: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha.
Enlaces `preview-document/{uuid}` (PDF). En agosto 2026 el tablón muestra ~10 anuncios recientes
(bandos desbroce parcelas, cobros tasas, prevención incendios); entradas de desbroce parcelas urbanas
clasificables como proyectos urbanísticos.

## Licencias

- Trámites informativos en catálogo sede `/dossier`: licencia urbanística, declaración responsable, etc.
- Modelos PDF en web Joomla: licencia urbanística 2022, declaración responsable 2022, ordenanza 31/12/2021.
- No hay dataset histórico de concesiones con coordenadas.
- Formulario incidencias urbanas (incidenciasurbanas.com) sin listado scrapeable.

## Proyectos / planeamiento

- **Web Joomla:** normas subsidiarias, normativa urbanística, ordenanza licencia/DR (descargas `/descargas/send/`).
- **BOCM CM:** PDF normativa urbanística becerril.pdf.
- **Transparencia:** ordenanzas urbanismo con enlaces `preview-document` en HTML inicial (BOCM 293/2021 DR urbanística).
- **SIT WFS:** 23 ámbitos (P-1 a P-13, UA-1 a UA-10) con polígonos reprojectables a WGS84.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='BECERRIL DE LA SIERRA'` (`srsName=EPSG:4326`)
  - No hay visor ArcGIS propio del ayuntamiento ni GeoJSON en datos abiertos locales
  - incidenciasurbanas.com sin capa GIS pública
- **Estrategia:** Semillas de ámbitos SIT WFS con `geom_geojson`; enriquecer por código P-/UA- en títulos.
- **Limitaciones:** Tablón/PDF sin georreferenciación; transparencia Wicket parcialmente scrapeable;
  licencias sin GIS enlazable.

## Limitaciones

- Web `becerrildelasierra.org` devuelve 403 sin User-Agent identificable.
- Portal transparencia: subcarpetas Wicket con `wicketAjaxGet`; solo enlaces estáticos en HTML inicial.
- Tablón muestra solo anuncios recientes (~10 filas); histórico requiere búsqueda POST Wicket.
- `/dossier` accesible pero lento desde CI; catálogo trámites como fallback.

## Estrategia adapter

1. Scrape web Joomla urbanismo (descargas NNSS, normativa, modelos licencia).
2. Scrape tablón `/board/{uuid}/` (tabla + fallback enlaces).
3. Catálogo trámites urbanismo desde `/dossier`.
4. Enlaces transparencia con `preview-document` en HTML inicial.
5. Semillas de ámbitos SIT WFS (23 P-/UA-) con `geom_geojson`.
6. Páginas informativas de referencia (tablón + trámites + sede).
7. IDs: `becerril-de-la-sierra-{lic|proy}-{sha256[:14]}`.
