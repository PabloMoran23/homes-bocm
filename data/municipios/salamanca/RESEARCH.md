# Salamanca — investigación portal ayuntamiento

**Municipio:** Salamanca (provincia Salamanca, Castilla y León)  
**Fecha:** 2026-07-27  
**BOCYL (referencia):** 20 avisos

## Resumen

Salamanca capital combina **Liferay** (`www.aytosalamanca.es`) para documentación de planeamiento
y **STA/BUROWEB** (`www.aytosalamanca.gob.es/sta/`) para sede electrónica, tablón de edictos y
catálogo de trámites. No hay listado público de concesiones de licencias georreferenciadas.

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Planes en tramitación | `/urbanismo-vivienda-y-obras/planes-tramitacion` | Liferay HTML | Enlaces `/w/*` a IP, convenios, aprobaciones |
| Archivo urbanístico | `/archivo-urban%C3%ADstico` | Liferay HTML | Histórico PGOU, PERI, sectores |
| Urbanismo (área) | `/urbanismo-vivienda-y-obras` | Liferay HTML | Semilla adicional |
| Tablón de edictos | `/es/edictos/` | STA + JSON embebido DataTables | Edictos municipales (mayoría plenos/presupuesto) |
| Catálogo trámites | `/sta/CarpetaPublic/?PAGE_CODE=CATALOGO` | STA JSON embebido | Licencias, planeamiento, urbanismo |
| Visor PGOU | `/w/visor-pgou-1` | iframe GeoVincles | `gis.geovincles.com/clients/viewer/salamanca/visor.php` |
| SIUCyL (CyL) | `idecyl.jcyl.es/geoserver/urbanismo/wfs` | WFS GeoJSON | Sectores `plau_cyl_sectores` municipio Salamanca |

## Tablón de edictos (STA)

Página `/es/edictos/` expone `metadata_TABLON_EDICTOS_LISTADO` con filas:

- Fecha publicación (`YYYY/MM/DD`)
- Descripción (enlace `TABLON_EDICTOS_DETALLE&DBOID=…`)
- Categoría

En julio 2026 predominan actas de pleno/junta de gobierno; pocos edictos urbanísticos recientes.
Se mantiene como fuente complementaria.

## Liferay — proyectos / planeamiento

Páginas `/w/*` incluyen metadatos estructurados:

- Título (`og:title`, `<h1>`)
- `Fecha Web: DD/MM/YYYY`, `Fecha B.O.C.Y.L: DD/MM/YYYY`
- Códigos de expediente en URL o texto (`expte. 4/2023/igur`)

Ejemplos: convenios urbanísticos, aprobaciones PGOU, planes parciales (Las Lanchas, Miralrío),
información pública sector SUNC, PERI acción 7.

## Licencias

No hay dataset ni visor de concesiones con coordenadas.

- **Catálogo STA:** páginas informativas (licencia obra mayor 0507, demolición, parcelación,
  declaración responsable obras, terrazas, etc.) vía `DETALLE={dboid}`.
- **Tablón:** anuncios de licencia cuando se publican (escasos en muestra actual).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS SIUCyL `urbanismo:plau_cyl_sectores` (`n_mun='Salamanca'`, filtro `n_num_sect`)
  - Visor PGOU GeoVincles (iframe sin API pública scrapeable)
- **Estrategia:** extraer códigos de sector del título (`SU-NC.31`, `SECTOR LL`, `SUNC-15`, …)
  y consultar WFS; centroide del polígono → `lat`/`lon`.
- **Limitaciones:**
  - GeoVincles no expone MapServer/WFS directo al scrapeador.
  - Muchos expedientes (convenios, PERI) no enlazan sector codificado en SIUCyL.
  - Tablón y licencias sin geometría; orquestador aplica centroide municipio + jitter.

## Limitaciones

- Liferay: ~37 páginas `/w/*` en semillas; sin API headless pública.
- Tablón STA: categorías mayoritariamente administrativas, no urbanismo.
- Catálogo STA: trámites informativos, no resoluciones de licencia.
- SIUCyL: geometría a nivel sector PGOU, no polígono de expediente individual.

## Estrategia adapter

1. Crawl semillas Liferay → enriquecer cada `/w/*` con título y fecha.
2. Parsear tablón STA (JSON embebido) filtrando keywords urbanismo.
3. Catálogo STA → licencias/trámites informativos.
4. Geometría: WFS SIUCyL por código de sector cuando aparece en título.
5. IDs: `salamanca-{lic|proy}-{sha256[:14]}`.
