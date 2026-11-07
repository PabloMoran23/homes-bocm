# Cuarte de Huerva — INE 50089, Zaragoza, Aragón

Verified live on 2026-11-07. This adapter extracts a **partial municipal planning
inventory**, with two real instruments and twenty document links. It does not
claim comprehensive works, planning amendments or granted-licence coverage.
Scheduling, missing-coordinate jitter and licence extraction are disabled.
`publication_ready` is false: no verified project geometry was obtained.

## Official current inventories

All four municipal HTML pages below returned HTTP 200 during the adapter's live
run. Content is scoped to `#body_content_left`, avoiding duplicated navigation,
footer addresses, news and licence application forms.

- [Urbanismo](https://cuartedehuerva.es/ayuntamiento/urbanismo): four PDF links
  explicitly concerning the same modification of the study of detail for manzana
  5, sector 5.2, «El Plano». These are one instrument: BOPZ announcement, study,
  memory and plans. The page's list of departmental functions is not a record.
- [PGOU](https://cuartedehuerva.es/ayuntamiento/urbanismo/plan-general-de-ordenacion-urbana):
  substantive historical narrative and links to its two document inventories.
- [Memoria del PGOU](https://cuartedehuerva.es/ayuntamiento/urbanismo/memoria):
  one linked `TRPGOU.pdf`, labelled “Texto Refundido del Plan General”.
- [Planos del PGOU](https://cuartedehuerva.es/ayuntamiento/urbanismo/planos):
  five general plans (information, infrastructure, classification, planning areas,
  qualification) and ten linked classification sheets. Image-only map pieces
  without hyperlinks are not invented as PDF documents. All fifteen actual PDF
  links are retained, including image anchors with no visible text; those use
  the HTML title or real URL basename as document labels.

The PGOU narrative and sixteen PDFs are grouped into one PGOU record. Each
`documentos` entry retains its source page, label and absolute URL. Stable IDs
identify the municipal instruments rather than transient document filenames.
These pages expose no pagination. No page/record limit truncates the inventories;
new pagination causes an explicit failure. Unexpected documents in Urbanismo
require review rather than being silently discarded or assigned to this study.
Updates refresh the entire supported snapshot; they do not claim a historical
change feed. This adapter intentionally supports these two packages only.

Additional official inventory discovery:

- [Municipal transparency: plans and maps](https://cuartedehuerva.cumpletransparencia.es/cuartedehuerva/Ordenacion/planes-de-ordenacion-urbana-y-mapas-de-planos)
  and [PGOU amendments](https://cuartedehuerva.cumpletransparencia.es/cuartedehuerva/Ordenacion/planes-de-ordenacion-urbana-y-modificaciones-al-pgou-y-plane)
  were found by search. The browser fetch returned HTTP 403. Search text points
  to the Government of Aragón's SIUa archive for amendments; this is discovery
  evidence, not a parsed register. No records are synthesized from those snippets.
- The municipal navigation links its electronic office and procurement profile.
  No granted-licence register was verified. Neither procurement notices nor
  service descriptions are treated as projects or grants. The broader regional
  archive, procurement portal, PMUS and other municipal sections are outside the
  extraction implemented here.

## Dates, stage and document provenance

The [municipally hosted BOPZ announcement](https://cuartedehuerva.es/system/resources/BAhbBlsHOgZmIj4yMDI2LzA4LzA0LzEwXzAzXzQyXzg4Nl9hbnVuY2lvX2JvcHpfNF9kZV9hZ29zdG9fMjAyNi5wZGY/anuncio_bopz_4_de_agosto_2026.pdf)
was downloaded and converted with the already installed `pdftotext`. Its header
identifies BOPZ no. 177, **4 August 2026**, announcement 5259, page 51. The text
explicitly states an **initial approval** agreement of the Junta de Gobierno
Local on **28 July 2026** for manzana 5 sector 5.2. Thus the study has
`fecha_publicacion: 2026-08-04`, `fecha_acuerdo: 2026-07-28` and
`fase: aprobación inicial`. It is an actual planning instrument, not a building
licence. The same notice suspends certain licence grants; no granted licences
are inferred. The adapter verifies municipality, instrument and date semantics
before emitting the record. `date_source_url` identifies the PDF.

The PGOU page recounts provisional approval on 11 May 2000 and definitive
approval with prescriptions on 19 July 2000, explicitly suspending executory
force pending correction. This historical narrative is preserved in `descripcion`.
It does not establish the approval date or present legal status of the currently
linked consolidated text, so the PGOU's top-level dates and phase remain null.
Neither crawl time, encoded upload paths nor page/footer dates become approval
or publication dates. Generic `fecha` and `fecha_aprob` remain null for both
records. Other linked PDFs are retained as document provenance; their content
is not parsed, and their agreement/approval status is not independently asserted.

No cadastral centroid, municipal office location or random offset is substituted
for project geometry. `lat`, `lon` and `geometry` remain null. The unlocated
instruments still provide genuine planning inventory records, but not map-ready
features.

## Implementation and validation

Reviewed `municipio/manifest.py`, `municipio/adapters/portal.py`, registry loading
and existing Manlleu/Chipiona examples before implementing this municipal adapter.
No shared code or dependencies were changed. The adapter uses preinstalled
requests/BeautifulSoup plus the existing system `pdftotext`; HTTP requests have
40-second timeouts and bounded streamed responses. Unexpected redirects,
missing content, unrecognized notice semantics and ambiguous notices fail before
writing records. Licences return a disabled result with an empty output.

Runtime used for both checks:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- Parser/manifest tests: `-m unittest municipio.test_cuarte_de_huerva -v` — **5
  passed**. Covers grouping, image-only document links, duplicate links, date
  semantics, absent geometry, stable IDs, wrong municipality, navigation-only or
  missing content, changed notice stage, pagination, unknown documents, adapter
  resolution and required manifest safety settings.
- Live call: load manifest with `load_manifest('cuarte-de-huerva')`, set
  `manifest.portal.config['capture_dir'] = 'evidence'`, resolve with
  `load_portal_adapter(manifest)`, then call
  `adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))` — **2 records**,
  PGOU **16** document links and study **4** document links. Registry entity-policy
  annotation completed; both broad planning instruments have unknown entity
  category (2/2), not an inferred building category.
- Local evidence: `evidence/proyectos.jsonl`, `evidence/validation.json`, four HTML
  captures, `evidence/anuncio.pdf` and its extracted `evidence/anuncio.txt`.
  Validation includes extraction source URLs, live count, document counts,
  runtime, timestamp and limitations. Evidence is local and is not source code.
