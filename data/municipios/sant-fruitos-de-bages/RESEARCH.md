# Sant Fruitós de Bages — INE 08213, Barcelona

Verified live on 2026-11-07 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
The adapter extracts one genuine planning instrument: the municipal POUM at
initial approval, grouping its complete published folder of 18 documents.
This is deliberately partial municipal coverage. Scheduling and licence
extraction are disabled; missing geometry is never replaced with jitter or a
municipal/town-hall point. `publication_ready` is false.

## Discovery and official inventories

- https://www.santfruitos.cat/ambits/urbanisme-i-habitatge — HTTP 200.
  Municipal urbanism page links to the RPUC and, in its highlighted links, to
  the municipal POUM transparency folder below. Capture: `evidence/urbanisme.html`.
- https://www.santfruitos.cat/ambits/urbanisme-i-habitatge/registre-de-planejament-urbanistic-de-catalunya-sant-fruitos-de-bages-rpuc
  redirects to https://planejamenturbanisme.territori.gencat.cat/rpucportal/index.html#/consulta/cerca
  (HTTP 200). Returns the application shell, not municipality-specific dossier
  rows. Not emitted as an instrument. Capture: `evidence/discovery-1.html`.
- https://santfruitosdebages.eadministracio.cat/transparency/270cead3-327c-4745-90f0-633eaaf9e14d/
  — HTTP 200, official inventory titled with this municipality's POUM. It
  advertises one initial-approval folder containing 18 documents. Following its
  public navigation callback resolves to the stable folder URL
  https://santfruitosdebages.eadministracio.cat/transparency/a4435025-2902-466b-bfca-a0437fe67cc6/.
  This has 10 document rows and a public “Veure'n més” callback. Its next response
  supplies the remaining 8 rows in Wicket XML CDATA components. All 18 unique
  official preview-document URLs are retained under one instrument, including
  information/ordering reports and plans, environmental/mobility studies,
  heritage catalogue, agreement certificate and notices. No study or split PDF
  is counted as a separate project.
- https://santfruitosdebages.eadministracio.cat/preview-document/906f0d82-0204-4346-9cfe-83ba26ac802e
  — HTTP 200. Agreement certificate preview exposes PDF metadata and a PDF
  viewer. The displayed document creation timestamp is not an agreement date.
  Capture: `evidence/certificate-preview.html`. Preview checked during research;
  the adapter retains its stable link but does not parse PDF contents.
- https://www.santfruitos.cat/seu-electronica/informacio-oficial — HTTP 200;
  navigation to notices, council minutes, budgets and procurement. This is not a
  project inventory. Capture: `evidence/oficial.html`.
- https://santfruitosdebages.eadministracio.cat/board — HTTP 200, mixed notice
  board with load-more pagination. First page contains staffing and subsidy
  notices. Not crawled beyond that page, not used as records, and no claim of
  complete board coverage. Capture: `evidence/inventory-1.html`.
- https://seu-e.cat/ca/web/santfruitosdebages/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  — HTTP 200; descriptive page links to the generic RPUC. Its update date is
  not an instrument date. Capture: `evidence/inventory-3.html`.
- Municipal site search `/@@search?SearchableText=POUM` returned HTTP 403.
  No access bypass attempted. No procurement announcement, application form,
  news story or licence suspension is emitted as a granted licence/project.

## Extraction semantics and completeness

Each run opens a fresh anonymous HTTP session, reads the POUM index, follows
its sole initial-approval folder, and follows every supplied load-more callback.
Only navigation URLs parsed from the public HTML are requested; JavaScript is
never evaluated. Wicket XML is parsed for component HTML. Documents use stable
municipal `/preview-document/<uuid>` links rather than transient callback URLs.
The record identity uses the stable POUM index UUID, not a fabricated expediente.

The number of unique documents must equal the index's declared number before
output is atomically replaced. Missing rows, empty pages, unexpected folders,
changed stages, cycles, HTTP errors, foreign URLs, response-size overflow or the
100-page safety bound fail the extraction instead of writing a partial snapshot.
Update performs the same full folder refresh. This does not cover every municipal
plan, historical stage, public work or licence, and the adapter fails for review
if the reviewed single-stage index changes.

Initial approval is a phase from the folder heading, not a claim of final
approval or current statutory force. Publication, agreement and approval dates
are all null: filenames, the site clock and preview creation times do not
establish those dates. PDF textual dates and geometry are not extracted. No
coordinates, parcel matches or municipal centroids are inferred. The PDF links
provide provenance for further review, not verified spatial features.

## Validation and evidence

- `.../venv/bin/python -m unittest municipio.test_sant_fruitos_de_bages -v`:
  6 tests passed. Covers declared inventory counts, public folder navigation,
  document grouping/deduplication, date/geometry nulls, XML load-more parsing,
  incomplete counts, changed stages, and rejection of navigation/login/form or
  foreign-document responses. Tests are offline and independent of local evidence.
- A real `SantFruitosDeBagesAyuntamientoAdapter.backfill_proyectos` call using
  the loaded manifest produced **1 record with 18 documents**, after 3 HTTP
  fetches (index, first folder page, load-more response).
- `evidence/proyectos.jsonl` contains that actual record;
  `evidence/validation.json` records `live_records`, `source_urls`, parser test
  count and limitations. `evidence/poum-live-1.html` through
  `evidence/poum-live-3.html` are exact response body captures from this run;
  the third is XML despite its capture suffix. Transient callback URLs in
  validation are provenance only, not reusable document identities.
- Evidence is local and excluded from the four source-file deliverables.
  No shared source or dependency changes, credentials, database access,
  publishing or git mutation are needed.
