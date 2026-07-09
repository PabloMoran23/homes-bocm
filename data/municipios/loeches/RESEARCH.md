# Loeches — investigación portal ayuntamiento

**Municipio:** Loeches (Comunidad de Madrid)  
**Fecha:** 2026-07-09  
**BOCM regional (referencia):** 17 avisos

## Resumen

Loeches publica urbanismo en web corporativa WordPress y sede electrónica espublico/eHome:

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Web urbanismo | `https://loeches.es/urbanismo/` | WordPress informativo | Contexto; sin listado de expedientes |
| Categoría urbanismo | `https://loeches.es/category/urbanismo/` | WP REST + HTML | Proyectos (noticias PGOU, sector industrial) |
| PGOU en redacción | `https://loeches.es/plan-general-de-ordenacion-urbana/` | PDFs (planos, memoria, tríptico) | Proyectos (planeamiento) |
| Tablón sede | `https://loeches.sedelectronica.es/board/` | HTML tabla eHome | Proyectos y licencias vigentes |
| Catálogo trámites | `https://loeches.sedelectronica.es/info.0` | eHome (requiere cookies) | Informativo licencias |
| SIT Comunidad Madrid | WFS `sitcm:VPLA_V_AMBITO` | GeoJSON polígonos UE | Geometría parcial por nombre de ámbito |

## Fuentes detalladas

### 1. Web corporativa — Urbanismo (WordPress)

- **URL:** `https://loeches.es/urbanismo/`
- **Contenido:** Descripción del departamento; sin tablón ni PDFs indexables.
- **Categoría urbanismo:** 5 entradas (PGOU, sector industrial Calle Ronda, contratación PGOU, etc.).
- **API REST:** `https://loeches.es/wp-json/wp/v2/posts?categories=34`

### 2. Plan General de Ordenación Urbana

- **URL:** `https://loeches.es/plan-general-de-ordenacion-urbana/`
- **PDFs (mar 2023):**
  - `PLANOS.pdf`
  - `MEMORIA-PRELIMINAR.pdf`
  - `TRIPTICO.pdf`
- **Estado:** En redacción; municipio regido por Normas Subsidiarias 1997.

### 3. Sede electrónica eHome — Tablón de anuncios

- **URL:** `https://loeches.sedelectronica.es/board/`
- **Formato:** Tabla con clases `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Enlaces:** `preview-document/{uuid}` por fila.
- **Ejemplos urbanismo (jul 2026):**
  - `2025P305__Anuncio_Informacion_Publica_AAP+AP.pdf` — modificación líneas eléctricas 220 kV (exp. 2744/2026, Licencias Urbanísticas).
  - `BOCM-20260703-61` — licencia actividad taller reparación automóviles (Urbanismo).
- **Limitación:** Solo anuncios vigentes (~11 filas); sin paginación pública fiable.
- **SSL:** Certificado inválido en sede — requiere `insecure_ssl: true`.

### 4. Sede electrónica — Trámites

- **Catálogo:** `https://loeches.sedelectronica.es/info.0` (accesible con cookie jar; `/info.0` sin cookies provoca redirect loop).
- **Urbanismo:** `/citizen-service/7f14c9f4-69e3-4ff8-87ea-4b62749bdce5`
- **Declaración responsable:** enlace ofuscado desde catálogo (sin listado de concesiones).
- **Consulta expedientes:** requiere Cl@ve; no hay listado público.

### 5. Fuentes descartadas

| Fuente | Motivo |
|--------|--------|
| `sector_geometry/madrid_*` | Pipeline Madrid capital — fuera de alcance |
| Visor urbanístico municipal | No existe visor propio |
| BOCM re-parse | Ya cubierto en pipeline regional |
| Tablón web `/tablon-de-anuncios/` | 404 |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO ILIKE '%Loeches%'`
  - 8 polígonos (S-1…S-6 suelo urbanizable, U-1/U-2 suelo urbano)
- **Estrategia:** Tras obtener metadatos del proyecto, `_match_wfs_geometry()` cruza tokens del título con `DS_NOMB_AMB` (p. ej. «Valdepozuelo», «Pancho Chico»). Sin enlace expediente↔polígono en el portal.
- **Limitaciones:**
  - Tablón y noticias WP no enlazan visor ni `objectId`.
  - Licencias BOCM son PDFs sin georreferencia.
  - No hay ArcGIS municipal ni GeoJSON en datos abiertos.

## Estrategia de ingesta

- **proyectos.jsonl:** WP urbanismo (REST) + PDFs PGOU + tablón sede filtrado.
- **licencias.jsonl:** tablón sede (licencias/actividad) + trámites informativos sede.
- **IDs:** `loeches-{lic|proy}-{sha256[:14]}`.
- **source:** `ayuntamiento`.

## Paridad esperada

- `proyectos`: ok (≥5 noticias + 3 PDFs PGOU + anuncios tablón).
- `licencias`: partial (anuncios tablón + trámites; sin dataset con coordenadas).
- `with_geometry`: 0–2 (solo si título cita ámbito SIT).
