# Son Servera — INE 07062, Illes Balears

Verified live on 2026-11-07 using the preinstalled municipal venv. This adapter
extracts the official municipal NNSS revision and numbered modification
inventories. It emits **8 planning instruments with 115 document links**, not
115 projects. Coverage is partial; scheduling and missing-coordinate jitter are
disabled. No granted-licence register is claimed or scraped.

## Discovery and official sources

The municipal transparency urbanism index links to Urbanismo y vivienda and
Obras de infraestructura:
https://www.sonservera.es/portal/transparencia/se_contenedor2.jsp?codMenu=46&codMenuPN=21&codResi=1&language=ca&layout=se_contenedor2.jsp&seccion=se_seccion_menus.jsp

The live urbanism menu exposes NNSS, heritage catalogues, seven numbered NNSS
modifications, and infrastructure works. The scraper discovers the NNSS and
modification URLs from this menu on each run; it does not hardcode a selection of
documents from search results. All 11 extraction HTML requests succeeded:

- https://www.sonservera.es/portal/p_18_final_Contenedor1.jsp?seccion=s_p_21_menu_nivel1.jsp&language=es&codResi=1&codMenuPN=3&codMenu=16
- https://www.sonservera.es/portal/p_18_final_Contenedor1.jsp?seccion=s_ldes_d10_v1.jsp&codbusqueda=110&language=es&codResi=1&codMenuPN=3&codMenuSN=16&codMenu=104&layout=p_18_final_Contenedor1.jsp
- https://www.sonservera.es/portal/p_18_final_Contenedor1.jsp?seccion=s_fdes_d4_v1.jsp&contenido=2101&tipo=6&nivel=1400&layout=p_18_final_Contenedor1.jsp&codResi=1&language=es&codMenu=104&codMenuPN=3&codMenuSN=16
- https://www.sonservera.es/portal/p_18_final_Contenedor1.jsp?seccion=s_fdes_d4_v1.jsp&contenido=2103&tipo=6&nivel=1400&layout=p_18_final_Contenedor1.jsp&codResi=1&language=es&codMenu=104&codMenuPN=3&codMenuSN=16
- https://www.sonservera.es/portal/p_18_final_Contenedor1.jsp?seccion=s_ldoc_d4_v1.jsp&codbusqueda=649&language=es&codResi=1&codMenuPN=3&codMenuSN=16&codMenu=302&layout=p_18_final_Contenedor1.jsp
- https://www.sonservera.es/portal/p_18_final_Contenedor1.jsp?seccion=s_ldoc_d4_v1.jsp&codbusqueda=700&language=es&codResi=1&codMenuPN=3&codMenuSN=16&codMenu=335&layout=p_18_final_Contenedor1.jsp
- https://www.sonservera.es/portal/p_18_final_Contenedor1.jsp?seccion=s_ldoc_d4_v1.jsp&codbusqueda=1136&language=es&codResi=1&codMenuPN=3&codMenuSN=16&codMenu=436
- https://www.sonservera.es/portal/p_18_final_Contenedor1.jsp?seccion=s_ldoc_d4_v1.jsp&codbusqueda=1137&language=es&codResi=1&codMenuPN=3&codMenuSN=16&codMenu=437
- https://www.sonservera.es/portal/p_18_final_Contenedor1.jsp?seccion=s_ldoc_d4_v1.jsp&codbusqueda=940&language=es&codResi=1&codMenuPN=3&codMenuSN=16&codMenu=404
- https://www.sonservera.es/portal/p_18_final_Contenedor1.jsp?seccion=s_ldoc_d4_v1.jsp&codbusqueda=966&language=es&codResi=1&codMenuPN=3&codMenuSN=16&codMenu=409
- https://www.sonservera.es/portal/p_18_final_Contenedor1.jsp?seccion=s_ldoc_d4_v1.jsp&codbusqueda=1334&language=es&codResi=1&codMenuPN=3&codMenuSN=16&codMenu=476

The infrastructure inventory was also inspected during research:
https://www.sonservera.es/portal/p_18_final_Contenedor1.jsp?codMenu=348&codMenuPN=3&codMenuSN=16&codResi=1&codbusqueda=755&language=ca&seccion=s_ldes_d10_v1.jsp
It lists nine historical physical works (2015–2017 dossiers). These are outside
this adapter's deliberately documented NNSS scope. Heritage catalogues, general
news, procurement and the electronic noticeboard are also outside coverage.
The transparency page's procurement link is not used as a source of projects or
licence grants; application forms are not grants.

## Grouping, provenance and semantics

The revision inventory has two entries: the actual revision and its maps. These
are combined into one instrument (51 files: 3 normative/uses documents and 48
maps). The municipal narrative explicitly states definitive approval on
2014-03-28; this is `fecha_aprob`, not publication or crawl time.
`fecha_publicacion`, generic `fecha`, and `fecha_acuerdo` remain null.

Each numbered modification is one instrument. Document totals after grouping
are 12, 9, 6, 12, 9, 13 and 3 for modifications 1 through 7 respectively.
Modification 6's page has 16 rows, including three explicitly grouped under
"Modificación 7 NNSS". Section headings control instrument attribution; those
three are deduplicated with modification 7's own inventory by file URL. Both
source-page URLs are retained on repeated documents. The convenio section for
modification 6 stays attached to that modification, with its original section
label preserved. File and municipal metadata-card links are retained together.
Stable record IDs derive from the actual instrument number, not a document,
page order, or date.

Modification 1 explicitly says "Suspensión del procedimiento por ejecución de
sentencia." This is retained in its description. Historical initial/definitive
approval files are not sufficient to infer current legal status. All modification
`fase`, approval, agreement and publication dates remain null. PDFs are linked,
not text-parsed; signature dates or BOIB dates are not guessed from filenames.
The output is a documentary instrument inventory, not a legal consolidation of
currently effective provisions.

All geographic fields remain null. The raster/PDF map links are retained but no
vector geometry is extracted. No municipal centroid or fabricated coordinates
are supplied. `publication_ready` is false. Records identify Son Servera,
Illes Balears and INE 07062 explicitly.

## Completeness and failure behavior

The NNSS revision inventory reports 2 contents. Modification pages report
12, 9, 6, 12, 9, 16 and 3 contents. The parser checks all row counts against these
official totals, rejects active pagination links or missing totals, and fails
without replacing the output when source markup, document files or instrument
groups are missing. Pagination is not silently truncated: a future paginated
inventory requires extending the crawler before it can succeed. There is no
fixed record limit or date cutoff. Update performs the same full snapshot as
backfill and does not use unknown dates as incremental cursors.

HTML fetching uses 40-second request timeouts and a 4 MB response bound. It
requires municipal HTTPS HTML content. JSONL is replaced only after all source
pages have been parsed. Licence methods explicitly return disabled, zero rows.

## Reproduction and local evidence

- Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
- Parser tests: `-m unittest municipio.test_son_servera -v`: 6 passed. They cover
  source selection, login/markup failure, cross-listed grouping, missing files,
  pagination and count mismatch, date semantics, suspension text, deduplication,
  full-snapshot update and manifest/disabled-licence integration.
- Live run: `load_manifest('son-servera')`, set
  `manifest.portal.config['capture_dir']='evidence/captures'`, then
  `load_portal_adapter(manifest).backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
- `evidence/proyectos.jsonl`: actual 8 live records, written through the registry
  adapter and annotated with the shared entity policy (all 8 category unknown;
  no narrower entity category is invented).
- `evidence/validation.json`: live record count, exact source URLs, limitations,
  document count and UTC observation timestamp.
- `evidence/captures/`: all extraction HTML responses;
  `evidence/capture_index.json` maps exact URLs to captured files. Earlier
  research captures are also local under `evidence/`.

Evidence is local and excluded from source changes. No shared modules,
dependencies, database, deployment, authentication or publication were used.
