# Vilanova i la Geltrú — investigación portal ayuntamiento

## URLs base

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.vilanova.cat |
| Urbanisme (índice) | https://www.vilanova.cat/espai_public/urbanisme.html |
| Planejament (PDFs) | `/espai_public/planejament_*`, `projectes_urbanitzacio`, `convenis_urbanistics`, etc. |
| Seu electrònica | https://seuelectronica.vilanova.cat |
| STA carpeta / trámites | https://tramitacio.vilanova.cat/sta/CarpetaPublic/ |
| Catálogo trámites | `PAGE_CODE=CATALOGO` (dataset `CATSERV` embebido en HTML) |
| Tablón edictos | `PAGE_CODE=PTS2_TABLON&KEY=all` (DataTables + `submitAjax.aa`, sin `dataset_*` en HTML inicial) |
| Visor SIG (Leaflet) | https://www.vilanova.cat/SIG/mapa |
| MapServer urbanisme | https://gis.vilanova.cat/mapserv?map=urbanisme |

## Proyectos / planeamiento

- CMS propio (wetown): secciones bajo `espai_public/` listan documentación PDF en `/doc/doc_*.pdf`.
- Fuentes con contenido: `planejament_general_en_tramit` (~61 PDFs), `projectes_urbanitzacio` (~63), `estudis_de_detall` (~44), `convenis_urbanistics`, avanç POUM en `urbanisme.html`.
- Subpáginas de planejament derivat enlazan a `plans_parcials_dordenacio`, `plans_especials`, etc.
- Tablón STA TAO: página responde 200 pero el listado se rellena por AJAX; no hay `var dataset_PTS2_TABLON` en el HTML (a diferencia de otros ayuntamientos STA).

## Licencias

- No hay tablón público de concesiones de licencia con dirección/coords.
- Catálogo STA (`CATSERV`, 562 trámites): ~28 relacionados con obres/llicències urbanístiques (CA/ES).
- Seu: trámites informativos (p. ej. còpies d'expedients id=3836) requieren identificación.

## Limitaciones técnicas

- Certificado TLS de `*.vilanova.cat` no encadena con CA pública estándar → `insecure_ssl: true` en el adapter.
- Tablón STA: dataset solo vía POST `submitAjax.aa` (no replicado en esta versión del adapter).
- `seuelectronica.vilanova.cat/edictes_anuncis` apunta a e-Tauler AOC (sin listado scrapeable directo en pruebas).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** MapServer municipal `https://gis.vilanova.cat/mapserv?map=urbanisme` (capas WMS `LEVEL_*`, `SERIE_B_*`); visor Leaflet en `/SIG/mapa` con `default_serv_SIG_Base`.
- **Estrategia:** las capas muestran clasificación PGOU/derivado pero **no** exponen código de expediente ni enlace 1:1 con anuncios/PDFs del portal; ICV `terramapas.icv.gva.es` no devolvió features filtrables por INE 08307 en pruebas WFS JSON.
- **Limitaciones:** sin join expediente→polígono; el orquestador usará centroide municipal + jitter.

## Adapter

- `municipio.adapters.vilanova_i_la_geltru:VilanovaILaGeltruAyuntamientoAdapter`
- Proyectos: crawl PDFs `espai_public/*` + intento tablón STA.
- Licencias: catálogo STA (trámites informativos) + filas del tablón si en el futuro embebe dataset.
