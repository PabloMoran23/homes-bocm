# Alcover — INE 43005, Tarragona, Catalunya

Verified 2026-11-09 using the preinstalled Python environment. This adapter covers
**only the POUM and numbered modifications section** of the municipal transparency
planning inventory. Live extraction returns 24 genuine planning instruments: the
POUM and modifications 1–23. This is partial municipal coverage, not a granted
licence register. Scheduling and coordinate jitter are disabled.

## Official inventories discovered

- [Urbanisme index](https://seu-e.cat/ca/web/alcover/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme):
  municipal index identifying the planning, public works, urban management and
  project/memoranda inventories. Captured locally as `evidence/urbanisme.html`.
- [Planejament urbanístic](https://seu-e.cat/ca/web/alcover/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic):
  extraction source, HTTP 200. All 24 instruments in the POUM/modifications section
  are extracted. This is an unpaginated HTML inventory, not a search-result page.
  The page also has special plans and specific-action projects **outside this
  adapter's section**. They are not attached to modification 23.
- [Obres públiques i infraestructures](https://seu-e.cat/ca/web/alcover/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/obres-publiques-i-infraestructures-197):
  HTTP 200, genuine technical projects including Avinguda de Reus pacification,
  tanatori extension, water network works and multipart project documents.
  Discovered and captured, outside implemented coverage. Tender labels in this
  inventory are not treated as approval dates, licences or separate projects.
- [Gestió urbanística](https://seu-e.cat/ca/web/alcover/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/gestio-urbanistica-209):
  HTTP 200, PAU-3 urbanisation and PAU-0 urbanisation/reparcelling documents;
  captured but outside implemented coverage.
- [Projectes/Memòries d'obres](https://seu-e.cat/ca/web/alcover/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/projectes/memories-d-obres-240):
  HTTP 200, technical project/memoranda inventory, including Avinguda de Mont-ral,
  a 16-HPO building and other interventions; captured but outside coverage.

## Provenance and semantics

Each record's `url` is the municipal inventory; `documentos` retains the official
links and source URL, with roles `rpuc_dossier`, `municipal_document` or `map_viewer`.
The POUM has its RPUC dossier 259791 and MUC viewer link in one record. Numbered
modifications each remain one instrument, even with multiple document links.
Stable record IDs use the municipal instrument identity (POUM/modification number),
not crawl order or an invented expediente number.

A live check of the [POUM dossier](https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/259791/documents)
returned HTTP 200 after redirect to the Generalitat's current RPUC host, serving
an application shell. Dossier document contents/geometry are not extracted.
Municipal PDFs for modifications 22 and 23 both returned HTTP 200 with actual PDF
bodies (captured locally); their text is not parsed by this adapter.

The inventory expressly states provisional approval for modification 17 and initial
approval for 22 and 23 (including the source's `inical` spelling). Other stages are
null: being linked to RPUC does not establish definitive approval. Publication,
agreement and approval dates are all null. The page's 02/11/2026 update timestamp
is page metadata and never a project event date. No coordinates or geometry are
verified, so those fields stay null and `publication_ready` stays false.

The shared registry annotator classifies these Catalan records as `pendiente`
with `insufficient_identity_evidence` (24 unknown; `adapter_incident` report).
This limitation is preserved in validation: no shared policy edits or invented
municipal expediente references are used to bypass it. Extraction readiness does
not mean ingestion/publication approval; independent review remains necessary.

## Extraction and validation

Requests have timeouts and a 4 MB bound on the inventory response. Oversize bodies,
missing/ambiguous content, missing official documents, duplicate instrument headings,
conflicting stages and pagination controls raise errors before output replacement.
The parser scopes the POUM section, retaining all its numbered headings and
excluding unrelated special plans and footer timestamps. Updates refresh the full
snapshot; they do not append duplicates or use a date cursor.

- `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_alcover -v`:
  eight passing tests covering grouping, source boundaries, provenance, dates,
  phases, stable IDs, malformed inputs, pagination, manifest and adapter methods.
- Live extraction through `load_manifest('alcover')`, `load_portal_adapter` and
  `backfill_proyectos(Path('evidence/proyectos.jsonl'))`: 24 records, 25 retained
  document/viewer links, 0 licences and 0 fabricated coordinates/dates.
- `evidence/validation.json`: count, source URLs, scope limitations, classification
  report, tests, source hash and live document checks. `evidence/planejament.html`
  captures the actual adapter response; other HTML/PDF captures and
  `document-checks.json` document source discovery. Evidence is local only.

Only the four requested source files are added. No dependencies, shared sources,
credentials, deployment tools or external write operations are involved.
