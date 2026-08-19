# Casarrubuelos — investigación portal ayuntamiento

**Municipio:** Casarrubuelos (Comunidad de Madrid)  
**Fecha:** 2026-08-12  
**BOCM regional (referencia):** 4 avisos

## Resumen

Casarrubuelos publica trámites y formularios de urbanismo en la web WordPress municipal
(`casarrubuelos.es`) y anuncios recientes en la **sede electrónica espublico gestiona**
(`casarrubuelos.sedelectronica.es/board`). Los ámbitos del Plan General están en el **WFS SITCM**
de la Comunidad de Madrid (8 polígonos, 5 nombres únicos: SUS-I, SUS-R1–R4).

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Urbanismo web | `https://casarrubuelos.es/areas-municipales/urbanismo/` | WordPress HTML + PDFs | Modelos URB (licencias obra, actividad, ocupación vía, vados) |
| Tablón de anuncios | `https://casarrubuelos.sedelectronica.es/board` | HTML tabla | ~10 anuncios recientes (licencias, proyectos, bandos) |
| Sede trámites | `https://casarrubuelos.sedelectronica.es/info.0` | Wicket SPA | Enlace desde web urbanismo; presentación telemática |
| Transparencia sede | `https://casarrubuelos.sedelectronica.es/transparency` | Wicket | Sin sección urbanismo destacada |
| WFS SITCM | `https://idem.comunidad.madrid/geoserver3/ows` | GeoJSON WFS | Capa `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='CASARRUBUELOS'` |
| Visor SITCM | `https://www.madrid.org/cartografia/sitcm/html/visor.htm` | Visor web | Referencia cartográfica regional |

## Tablón de anuncios (`/board`)

Tabla HTML con columnas: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha (`DD/MM/YYYY`).
Enlaces `preview-document/{uuid}` (PDF).

Ejemplos vigentes (ago 2026):

- **ANUNCIO PROYECTO CONCESIÓN CENTRO TRANSFORMACIÓN ELÉCTRONICA** (exp. 74/2026, Calle Virgen Victoria 18)
- BANDO autorizaciones instalaciones eventuales (licencias de ocupación)
- Padrón IBI urbana (categoría fiscal, no expediente urbanístico)

## Licencias

- Formularios URB en web municipal (obra mayor URB101, declaración responsable DR URB203, licencias actividad URB302, etc.).
- Tablón sede: bandos de ocupación y autorizaciones eventuales cuando procedimiento/categoría coincide.
- No hay dataset histórico de concesiones con coordenadas ni listado público de expedientes (consulta requiere sede).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS Comunidad de Madrid `sitcm:VPLA_V_AMBITO` (`DS_MUNICIPIO='CASARRUBUELOS'`).
  Ámbitos: SUS-I (industrial), SUS-R1, SUS-R2, SUS-R3, SUS-R4 (suelo urbanizable sectorizado residencial).
  Visor regional: `https://www.madrid.org/cartografia/sitcm/html/visor.htm`.
- **Estrategia:** Descarga WFS por municipio; polígonos en `proyectos.jsonl` para ámbitos PGOU.
  Enriquecimiento por código SUS-* en títulos de expedientes tablón (si aparece).
- **Limitaciones:** Licencias y anuncios del tablón son PDFs sin georreferenciación.
  No hay visor municipal propio ni enlace expediente→geometría en sede.
  Múltiples features WFS con mismo `DS_NOMB_AMB` (polígonos fragmentados) se fusionan.

## Limitaciones

- Tablón muestra ~10 anuncios recientes; histórico requiere búsqueda Wicket no implementada.
- `/info.0` en sede puede devolver vacío en algunos contextos CI (enlace SPA).
- Formularios web son modelos de trámite, no concesiones publicadas.
- Portal transparencia sede sin catálogo urbanismo explícito.

## Estrategia adapter

1. Scrape tablón `/board` + formularios PDF en página urbanismo.
2. Ámbitos PGOU desde WFS SITCM con `geom_geojson`.
3. Páginas informativas (tablón, urbanismo web, sede trámites).
4. IDs estables: `casarrubuelos-{lic|proy}-{sha256[:14]}`.

## Referencia adapters

- Tablón espublico + SITCM: `valdemorillo.py`, `venturada.py`
- Formularios WP urbanismo: `humanes_de_madrid.py`
