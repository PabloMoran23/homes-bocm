# Cenicientos — investigación portal ayuntamiento

**Municipio:** Cenicientos (Comunidad de Madrid)  
**Slug:** `cenicientos`  
**Fecha:** 2026-08-16  
**BOCM regional (referencia):** 3 avisos

## Resumen

Cenicientos es un municipio pequeño de la Sierra Oeste de Madrid. La **web corporativa**
(`www.cenicientos.es`) está **en construcción** (placeholder). La administración publica
trámites y anuncios en la **sede electrónica espublico gestiona**
(`cenicientos.sedelectronica.es`). No hay visor urbanístico municipal propio; la delimitación
de ámbitos del planeamiento (NNSS 1977) está en el **SIT de la Comunidad de Madrid** (WFS público).

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web corporativa | `https://www.cenicientos.es` | HTML estático | En construcción — sin contenido urbanístico |
| Sede electrónica | `https://cenicientos.sedelectronica.es` | espublico gestiona (Wicket) | Trámites, tablón, transparencia |
| Tablón de anuncios | `https://cenicientos.sedelectronica.es/board` | HTML tabla Wicket | Bandos, actuaciones urbanísticas |
| Portal transparencia | `https://cenicientos.sedelectronica.es/transparency` | Wicket AJAX | Sección 7: Urbanismo (5 docs) |
| Catálogo trámites | `https://cenicientos.sedelectronica.es/dossier` | Wicket | Timeout frecuente desde CI (>30 s) |
| SIT Comunidad de Madrid | WFS `sitcm:VPLA_V_AMBITO` | GeoJSON | 16 ámbitos (UA-01…UA-14, SAU-01…02) |
| Visor SITCM | `https://www.madrid.org/cartografia/sitcm/html/visor.htm` | ArcGIS | Referencia visual de ámbitos |
| NNSS históricas | [BOE-A-1978-1025](https://www.boe.es/diario_boe/txt.php?id=BOE-A-1978-1025) | PDF BOE | Normas subsidiarias aprobadas 1977 |

Dominio turístico `cenicientosdigital.es` — no es portal institucional de urbanismo.

## Tablón de anuncios (`/board`)

Tabla HTML responsive con columnas: Documento, Expediente, Procedimiento, Categoría,
Descripción, Fecha de Publicación (`DD/MM/YYYY`). Enlaces `preview-document/{uuid}` (PDF).

Ejemplos vigentes (ago 2026):

- Plan Especial Protección Civil Incendios Forestales (INFOMA) — Actuaciones Urbanísticas
- Bando Licencias de Ocupación Vía Pública / Terrazas — Actuaciones Urbanísticas
- Bandos fiestas patronales (fuego, hostelería) — no urbanísticos

## Licencias

- No hay dataset abierto de concesiones con coordenadas.
- Anuncios de licencia (ocupación vía pública, terrazas) aparecen en tablón.
- Consulta de expedientes (`/expedientes`) requiere Cl@ve.
- Catálogo de trámites (`/dossier`) inaccesible de forma fiable por timeout.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS Comunidad de Madrid `https://idem.comunidad.madrid/geoserver3/ows`
  — capa `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='CENICIENTOS'`.
  16 ámbitos: UA-01…UA-14 (unidades de actuación), SAU-01…SAU-02 (suelo urbanizable).
- **Estrategia:** Ingestar polígonos de todos los ámbitos SITCM como proyectos de planeamiento;
  enriquecer anuncios del tablón cuando el título mencione código UA-/SAU-.
- **Limitaciones:** Tablón sin georreferenciación; transparencia tras AJAX Wicket;
  web corporativa inactiva; sin ArcGIS/GeoJSON en portal del ayuntamiento.

## Limitaciones

- `www.cenicientos.es` sin contenido útil (en construcción).
- Tablón con pocos anuncios recientes (~4); histórico requiere paginación Wicket.
- Portal transparencia urbanismo (5 docs) no scrapeable sin tokens de sesión.
- `/dossier` timeout en entornos CI.

## Estrategia adapter

1. Scrape tabla tablón `/board` (parser `data-label`).
2. Páginas informativas: tablón, consulta expedientes, portal transparencia, NNSS BOE.
3. Ingestar 16 ámbitos SITCM WFS con geometría completa.
4. Geometría WFS cuando el título del tablón contenga código UA-/SAU-.
5. IDs estables: `cenicientos-{lic|proy}-{sha256[:14]}`.

## Referencia adapters

- Tablón espublico: `torrejon_de_velasco.py`, `humanes_de_madrid.py`
- WFS SIT + ámbitos: `venturada.py`, `talamanca_de_jarama.py`
