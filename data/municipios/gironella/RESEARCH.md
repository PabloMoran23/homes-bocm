# Gironella — INE 08092, Barcelona

Verified live on 2026-11-09 with the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Exactly one adapter, for a deliberately partial municipal planning inventory.
Scheduling, granted-licence ingestion and missing-coordinate jitter are disabled.

## Official source discovery

- Municipal normative inventory, HTTP 200:
  https://gironella.cat/ajuntament/normativa-municipal/
  The server-rendered `llista_normativa` inventory contains 64 cards. FacetWP
  reports page 1, total_pages 1, per_page -1, total_rows and
  total_rows_unfiltered both 64. Eight cards are classified as urbanism; one
  concerns facade subsidies and is excluded. Seven are named planning instruments.
  All seven are extracted; there is no sampling or first-N limit.
- Official transparency planning page, HTTP 200:
  https://seu-e.cat/ca/web/gironella/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  Links to the municipal RPUC search (`municipiSel=08092`) and MUC viewer.
  These are discovery/viewer links, not additional instrument records.
- Municipal identity, HTTP 200:
  https://do.diba.cat/data/ds/municipis/graella?filter-field=ine&filter-value=08092
  Diputació de Barcelona identifies Gironella, INE 08092, province Barcelona
  (08), and the municipal website. The six-digit Catalan identifier is 080924;
  the manifest uses the requested five-digit INE code.
- The guessed transparency `urbanisme/projectes-tecnics` endpoint returned 404.
  It supplies no records. No complete physical-works or granted-licence register
  is claimed. Licence application forms, fiscal ordinances, procurement and
  unrelated news are outside this extraction.

## Live extracted instruments

1. Modificació puntual del Pla general al sector de la plaça de cal Blau
2. Modificació puntual del Pla general al sector SUD-4R Riera d’Olvan
3. Modificació puntual del Pla general d’ordenació al sector del Càmping Gironella
4. Modificació puntual del Pla general d’ordenació per a la ubicació d’una llar d’infants a la plaça de l’Estació
5. Pla de millora urbana per a la regulació paisatgística de les edificacions de la façana del riu Llobregat
6. Pla especial urbanístic de la casa rural la Serreta
7. Revisió pla general ordenació urbana municipal

Each record retains the exact source title/category, inventory URL, and all
unique document URLs with labels and publisher provenance. The general-plan
revision has a PDF linked twice (including “Memòria”) plus RPUC dossier 86191;
it is one instrument with two unique documents, retaining both PDF labels.
Identity is derived from the instrument title, independent of document ordering.
A renamed source title would change that identity; no municipal expediente ID
is invented.

All eight unique document URLs were checked live and captured locally. Six are
HTTP-200 municipal PDFs. Their first two pages yielded no extractable text with
`pdftotext`; PDF content/OCR is not part of the adapter. The other two URLs
redirect to the Generalitat RPUC application shell at
`planejamenturbanisme.territori.gencat.cat`. The legacy cal Blau link carries
`codintExp=263546` but lands on the search application, so its link is retained
without claiming successful dossier-content extraction. The revision link keeps
the dossier 86191 fragment. Document check results retain original/final URLs,
content types, hashes and capture paths in validation evidence.

## Semantics and limitations

This is the inventory published now, not proof that every listed document is
legally current or that the inventory is exhaustive. The adapter does not crawl
the whole RPUC history, infer approval from listing under normative documents,
or convert a procurement announcement into a project.

No project dates are extracted: `fecha_publicacion`, `fecha_acuerdo`,
`fecha_aprob` and generic `fecha` remain null. Upload-directory years, crawl
time and page-update timestamps are not approval or publication dates.
`fase` remains null; instrument type is kept separately. No coordinates or
geometry are verified: `lat`, `lon`, `geometry` are null and
`publication_ready` is false. Municipal centroids are never substituted.

The adapter checks the complete server-rendered card count against FacetWP
metadata and rejects missing metadata, filters, multiple pages or count
mismatch. If the source introduces pagination, extraction stops explicitly
until full traversal is implemented. It never silently truncates. Requests use
a timeout, a streamed 4 MB bound for the HTML inventory and redirect checks.
Updates refresh the entire scoped inventory; state timestamps do not filter it.

## Validation and local evidence

- `.../venv/bin/python -m unittest municipio.test_gironella -v`: seven tests passed.
  Covers document grouping and duplicate labels, exclusion of non-instruments,
  unknown dates/geometry, pagination and count mismatch, changed/empty/foreign
  source rejection, stable document-order-independent IDs, manifest controls
  and disabled licence extraction without network access.
- Direct live `GironellaAyuntamientoAdapter.backfill_proyectos` run: seven real
  records, eight unique document URLs, no inferred dates or coordinates.
- `evidence/proyectos.jsonl`: actual adapter output.
- `evidence/validation.json`: live_records, source_urls, limitations, test result,
  retrieval time, completeness counts and document verification results.
- `evidence/normativa.html`: exact inventory fetched during live adapter run.
  Other source HTML and PDF captures are also under `evidence/`.

Evidence is local and is not a source deliverable. No shared sources,
dependencies, credentials, databases, deployments or git metadata were modified.
