# Navas del Rey — investigación portal ayuntamiento

**Municipio:** Navas del Rey (Comunidad de Madrid)  
**Fecha:** 2026-08-08  
**BOCM regional (referencia):** 6 avisos

## Resumen

Navas del Rey publica anuncios en la **sede electrónica espublico gestiona**
(`navasdelrey.sedelectronica.es`) y la información institucional en **WordPress**
(`navasdelrey.es`). El planeamiento vigente en el **SIT de la Comunidad de Madrid**
(WFS `sitcm:VPLA_V_AMBITO`) incluye un único ámbito: **PERI PUENTE DE SAN JUAN**
(normas subsidiarias 1985).

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web municipal | `https://navasdelrey.es` | WordPress | Noticias, ayuntamiento, trámites |
| Concejalías | `https://navasdelrey.es/ayuntamiento/concejalias/` | WordPress HTML | Organigrama (Personal, Urbanismo y Hacienda) |
| Trámites web | `https://navasdelrey.es/tramites/` | WordPress HTML | Enlaces a sede y formularios |
| Tablón de anuncios | `https://navasdelrey.sedelectronica.es/board` | HTML tabla | Anuncios recientes (contratos, convocatorias) |
| Catálogo trámites | `https://navasdelrey.sedelectronica.es/dossier` | HTML sede (Wicket) | Licencias y procedimientos administrativos |
| Portal transparencia | `https://navasdelrey.sedelectronica.es/transparency/` | Wicket | Normativa y documentación municipal |
| SIT Comunidad Madrid | `https://idem.comunidad.madrid/geoserver3/ows` | WFS GeoJSON | 1 ámbito `PERI PUENTE DE SAN JUAN` |

## Tablón de anuncios (`/board`)

Tabla HTML con columnas: Documento, Expediente, Procedimiento, Categoría, Descripción,
Fecha de Publicación. Enlaces `preview-document/{uuid}` (PDF). En agosto 2026 predominan
convocatorias administrativas y contratos de obras (embellecimiento); no hay avisos
urbanísticos recientes en la ventana visible (~9 filas, sin paginación pública).

## Licencias

- Trámites informativos en sede `/dossier` (licencias, declaraciones responsables).
- No hay dataset histórico de concesiones con coordenadas.
- Anuncios de licencia aparecen en tablón cuando se publican (poco frecuente en muestra actual).

## Proyectos / planeamiento

- **PERI PUENTE DE SAN JUAN:** Plan Especial Reforma Interior, suelo urbano consolidado,
  aprobado 1985 (BOCM/BOE). Documentado en SIT como normas subsidiarias.
- **SIT WFS:** polígono WGS84 ~49 456 m² en zona Puente de San Juan.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='NAVAS DEL REY'` (`srsName=EPSG:4326`)
  - Visor regional SIT CM: `https://idem.comunidad.madrid/cartografia/sitcm/html/visor.htm`
  - `CD_MUNICIPIO=099` en capa SITCM
  - No hay visor ArcGIS propio del ayuntamiento ni GeoJSON en datos abiertos locales
- **Estrategia:** Semilla de ámbito desde WFS; enriquecer por coincidencia de nombre
  (PERI, Puente de San Juan) en títulos de anuncios.
- **Limitaciones:** Solo 1 ámbito en SIT; tablón/PDF sin georreferenciación; transparencia
  Wicket no automatizable; `/dossier` responde lento (>15 s en CI).

## Limitaciones

- Portal transparencia: árbol Wicket con sesión JS; no scrapeable de forma estable en CI.
- Tablón muestra solo anuncios recientes; sin paginación pública accesible.
- Web municipal sin sección dedicada `/urbanismo/` con PDFs de planeamiento.
- Dominio `www.navasdelrey.es` redirige a `navasdelrey.es`.

## Estrategia adapter

1. Scrape tablón `/board` (tabla data-label + fallback enlaces).
2. Trámites urbanismo desde seed pages (concejalías, trámites, dossier).
3. Semilla de ámbito SIT WFS con `geom_geojson`.
4. Páginas informativas de referencia (tablón, concejalías, dossier, transparencia).
5. IDs: `navas-del-rey-{lic|proy}-{sha256[:14]}`.
