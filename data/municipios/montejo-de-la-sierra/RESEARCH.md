# Montejo de la Sierra — investigación portal ayuntamiento

**Municipio:** Montejo de la Sierra (Comunidad de Madrid)  
**Fecha:** 2026-08-10  
**BOCM regional (referencia):** 5 avisos

## Resumen

Montejo de la Sierra publica normativa y ordenanzas en su **web municipal WordPress Divi**
(`montejodelasierra.net`) y gestiona trámites y tablón en la **sede electrónica espublico gestiona**
(`montejodelasierra.sedelectronica.es`). Los ámbitos de planeamiento municipal están en el
**SIT de la Comunidad de Madrid** (WFS `sitcm:VPLA_V_AMBITO`).

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web municipal | `https://www.montejodelasierra.net/` | WordPress Divi | Portal general, normativa |
| Normativa | `https://www.montejodelasierra.net/normativa/` | WP HTML + PDFs | Ordenanzas fiscales, tasas licencias, enlace visor SITCM |
| Sede electrónica | `https://montejodelasierra.sedelectronica.es/` | espublico gestiona | Trámites, tablón, licencias |
| Tablón sede | `https://montejodelasierra.sedelectronica.es/board/` | HTML tabla | Ordenanzas urbanísticas, desbroce, procedimientos (7 docs ago 2026) |
| Licencias urbanísticas | `https://montejodelasierra.sedelectronica.es/citizen-service/89b9a1a7-18ab-4a39-97b4-0760fd5f5330` | HTML | Sección trámites licencias |
| PDF licencias | `https://montejodelasierra.sedelectronica.es/preview-document/cb12b067-5d92-4d1c-ab7e-04c813a9d4ef/` | PDF sede | Documento «Licencias Urbanísticas MONTEJO» (sep 2025) |
| Visor SITCM | `http://idem.madrid.org/cartografia/sitcm/html/visor.htm` | Visor web | Planteamiento urbanístico CM |
| SIT Comunidad Madrid | `https://idem.comunidad.madrid/geoserver3/ows` | WFS GeoJSON | 13 ámbitos `UA-1`..`UA-13` para `DS_MUNICIPIO='MONTEJO DE LA SIERRA'` |

## Cómo se listan expedientes

- **Planeamiento:** Enlace al visor SITCM desde `/normativa/`; ámbitos UA en WFS regional.
- **Tablón sede:** Tabla HTML espublico con columnas Documento/Expediente/Procedimiento/Categoría/Descripción/Fecha.
  Incluye ordenanzas de procedimientos urbanísticos, tasas urbanísticas y desbroce de solares.
- **Normativa web:** Listado de PDFs de ordenanzas fiscales (algunas relacionadas con licencias urbanísticas).
- **No hay** visor urbanístico propio del ayuntamiento ni API JSON de expedientes.

## Licencias

- Sección «Licencias Urbanísticas» en sede (`citizen-service/89b9a1a7-...`).
- Documento PDF informativo en sede (sep 2025).
- Ordenanzas de tasas de licencias urbanísticas en web `/normativa/`.
- No hay dataset histórico de concesiones con coordenadas; anuncios de licencia aparecerían en tablón.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='MONTEJO DE LA SIERRA'` (`srsName=EPSG:4326`)
  - Visor SITCM enlazado desde `/normativa/` (`idem.madrid.org/cartografia/sitcm/html/visor.htm`)
  - 13 ámbitos: UA-1, UA-2, … UA-13 (unidades de actuación)
- **Estrategia:** Semillas de ámbitos desde WFS con `geom_geojson`; enriquecer proyectos del tablón cuando el título contiene código UA.
- **Limitaciones:** PDFs sin georreferenciación directa; dominio `.es` del ayuntamiento no resuelve (web en `.net`); licencias sin polígono individual.

## Limitaciones

- Web oficial en `montejodelasierra.net` (no `.es`).
- Tablón con pocos documentos; mayoría ordenanzas, no expedientes de planeamiento activos.
- Licencias solo como páginas de trámite y PDF informativo, sin concesiones publicadas con coords.
- Sede `/dossier` puede responder lentamente (timeout >20s en CI).

## Estrategia adapter

1. Semillas de 13 ámbitos SIT WFS (UA-*) con `geom_geojson`.
2. Tablón sede (ordenanzas urbanísticas, desbroce).
3. PDFs de normativa web filtrados por urbanismo/licencias.
4. Páginas informativas de licencias (sede + PDF).
5. IDs: `montejo-de-la-sierra-{lic|proy}-{sha256[:14]}`.
