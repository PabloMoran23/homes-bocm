# Patones — investigación portal ayuntamiento

**Municipio:** Patones (Comunidad de Madrid)  
**Fecha:** 2026-07-09  
**BOCM regional (referencia):** 17 avisos

## Resumen

Patones combina **web WordPress** (`patones.net/site/ayto`) con **sede electrónica espublico gestiona**
(`patones.sedelectronica.es`). El planeamiento urbanístico (NNSS, planes especiales de aparcamientos, PAMIF,
PAMINUN, CITECO) se publica como PDFs en la sección de urbanismo. El tablón de anuncios de la sede lista
edictos recientes (pocos registros; sin histórico abierto masivo). No hay visor urbanístico municipal propio.

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Urbanismo (WP) | `https://patones.net/site/ayto/arquitecto-municipal/` | WordPress | Enlaces a NNSS, planes especiales, PAMIF/PAMINUN/CITECO |
| Normas subsidiarias | `https://patones.net/site/ayto/normas-subsidiarias/` | PDFs | Memoria, acuerdo, catálogo NNSS (Tomo II) |
| Plan aparcamientos (inicial) | `https://patones.net/site/ayto/plan-especial-de-aparcamientos-y-mejora-de-accesos-para-el-fomento-de-la-sostenibilidad-turistica-en-patones/` | PDFs | UP2403 bloques I–IV |
| Plan aparcamientos (subsanado) | `https://patones.net/site/ayto/plan-especial-de-aparcamientos-y-mejora-de-accesos-en-patones-subsanado-de-acuerdo-con-iae-e-informes-sectoriales/` | PDFs | Revisión informes sectoriales, IAE |
| Tablón de anuncios | `https://patones.sedelectronica.es/board` | HTML tabla Wicket | Edictos, ordenanzas, bandos |
| Transparencia | `https://patones.sedelectronica.es/transparency` | Wicket | Carpeta «5. URBANISMO» (34 docs; AJAX) |
| Consulta expedientes | `https://patones.sedelectronica.es/expedientes` | Cl@ve | Requiere autenticación |
| Boletín municipal | `https://patones.net/site/ayto/boletin-municipal/` | PDFs | Boletines trimestrales |
| Bandos | `https://patones.net/site/ayto/bandos/` | WP | Bandos municipales |

## Tablón de anuncios (`/board`)

Tabla HTML con columnas: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha (`DD/MM/YYYY`).
Enlaces `preview-document/{uuid}` (PDF). Ejemplos (jul 2026): aprobación inicial ordenanza punto de recarga,
bando desbroce fincas, calendario fiscal. Pocos anuncios visibles sin búsqueda Wicket POST.

## Licencias

- No hay dataset abierto de concesiones con coordenadas.
- Trámites de licencia no listados públicamente; consulta de expedientes requiere Cl@ve.
- El adapter incluye páginas informativas del tablón y la consulta de expedientes.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** SITCM WFS Comunidad de Madrid — capa `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='PATONES'`
  (15 unidades de ejecución UE-1 … UE-15 con polígonos en EPSG:4326).
- **Estrategia:** Tras extraer metadatos del expediente/documento, consultar WFS por código UE/SR en el título
  (`resolve_ambito_geometry` / `municipio.gis.sitcm`). Sin visor municipal ArcGIS ni enlace expediente→polígono.
- **Limitaciones:** PDFs de planeamiento sin georreferencia directa; tablón sin coords; transparencia Wicket no
  scrapeable sin tokens de sesión; `/info` y `/dossier` con redirect loop.

## Limitaciones

- Sede `/info` y `/dossier`: redirect infinito (no usable en CI).
- Transparencia urbanismo: 34 documentos tras clic AJAX Wicket (no implementado).
- Tablón muestra ~4 anuncios recientes.
- Planes especiales (aparcamientos UP2403) no incluyen código UE explícito en título → geometría vía SITCM solo
  cuando el título menciona UE/SR/ámbito.

## Estrategia adapter

1. Scrape PDFs y páginas semilla WordPress (urbanismo, NNSS, planes especiales, bandos, boletín).
2. Scrape tabla tablón `/board` (patrón espublico, dominio `patones.sedelectronica.es`).
3. Páginas informativas licencias (tablón + consulta expedientes).
4. Semillas de ámbitos SIT WFS (15 UE) con `geom_geojson`.
5. Enriquecer geometría con SITCM WFS cuando el título contiene código de ámbito (UE-n).
6. IDs estables: `patones-{lic|proy}-{sha256[:14]}`.

## Referencia adapters

- WordPress + PDFs: `el_boalo.py`, `algete.py`
- Tablón espublico: `humanes_de_madrid.py`
- Geometría SITCM: `majadahonda.py`, `municipio/gis/sitcm.py`
