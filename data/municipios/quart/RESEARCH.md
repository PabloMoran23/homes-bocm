# Quart — INE 17142, Girona

Verified live on 2026-11-09 using
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
One municipality adapter, with a deliberately partial snapshot of two actual
planning instruments. Scheduling, missing-coordinate jitter and licences are
disabled. No geometry is asserted; `publication_ready` is false.

## Official inventories investigated

- [Municipal urbanism landing page](https://www.quart.cat/ca/urbanisme-i-medi-ambient.html):
  HTTP 200; navigation to environment, activities and ordinances, without a
  project inventory. The website's municipal navigation links to its official
  transparency portal. Capture: `evidence/urbanisme.html`.
- [Transparency planning index](https://seu-e.cat/ca/web/quart/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic):
  HTTP 200; links to RPUC municipal search with `municipiSel=17142` and MUC
  with `municipi=17142`. These are external register/viewer entry points,
  not individual projects. Capture: `evidence/planejament-urbanistic.html`.
- [Urbanism regulations inventory — extraction source](https://seu-e.cat/ca/web/quart/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/normativa-d-urbanisme):
  HTTP 200; four named rows, including POUM and the mobility study. The public
  road inventory and tree catalogue are deliberately excluded because they
  are inventories, rather than projects or the selected planning instruments.
  Captures: `evidence/normativa-d-urbanisme.html` and fresh adapter request
  `evidence/live-inventory.html`. The portal shows an update in November 2022;
  current availability does not imply that it covers all subsequent planning.
- The municipal urbanism news category was also discovered in search. A news
  category is not used as a project or granted-licence register. No procurement
  announcements, application forms or unrelated news are emitted.

## Actual instruments and document provenance

The adapter emits one record per instrument, grouping every link in that row's
reference and document columns. Identity derives from the document URL, not
the crawl date. The live extraction has two instruments and four retained links.

1. **PLA D'ORDENACIÓ URBANISTICA MUNICIPAL (POUM)**. Inventory publication:
   2022-11-25. Links to
   [DOGC document 943323](https://dogc.gencat.cat/ca/document-del-dogc/?documentId=943323)
   and the [municipal POUM PDF](https://seu-e.cat/documents/2305750/15016052/POUM/602375e3-b853-4e58-997b-30b46fcbe20a).
   Both return HTTP 200. DOGC HTML is a JavaScript shell. The accessible PDF
   is the 217-page DOGC edict and urbanistic regulations, not a complete plan
   archive. Its first page identifies Quart, dossier 2013/051781/G, definitive
   approval on 2022-06-08 and conformity to the consolidated text on 2022-09-28.
   These are separate agreements from the publication on 2022-11-25.
   The adapter parses the inventory only and therefore leaves agreement,
   approval and phase null rather than deriving them from the publication date.
2. **Estudi d'ordenació de la mobilitat al municipi de Quart 2022**. Inventory
   publication: 2022-11-14; its additional-information column explicitly states
   definitive approval in the ordinary November 2022 plenary session. The
   adapter preserves that phase but leaves exact approval/agreement dates null.
   The linked [diligenced study PDF](https://seu-e.cat/documents/2305750/5786895/Estudi+d%27ordenaci%C3%B3+de+la+mobilitat+diligenciat/d26c38fc-9d36-41f6-8ceb-51de088d7731)
   returns HTTP 200 and identifies municipal dossier X2021000105; its diligence
   states approval on 2022-11-07. Its print/signature date is 2022-11-14, which
   must not become an agreement date. The linked municipal announcement returns
   HTTP 200 and is dated 2022-11-08. That news publication is distinct from
   the inventory publication. The study concerns circulation, parking signage
   and a cycle lane; it is emitted as one mobility planning instrument, without
   claiming its proposed interventions are individually completed works.

PDFs, reference HTML and their HTTP checks are saved under `evidence/`:
`detail-1-1-0.pdf`, `detail-2-1-0.pdf`, `detail-1-0-0.html`,
`detail-2-0-0.html`, `document-checks.json`. First-page text inspection is in
`poum-first-pages.txt` and `mobility-first-pages.txt`. PDF extraction is research
only, not an adapter dependency.

## Pagination, failure handling and coverage

All four rows occur in the source HTML. Its DataTables initialization orders
and filters those embedded rows; there is no AJAX/server-side page source.
The parser reads every embedded row, with no row limit. Tests cover 25 embedded
instruments and the live malformed/unclosed row layout. A next-page link,
remote DataTables configuration, changed column schema, missing instruments,
invalid dates, unexpected document origins or conflicting duplicate entries
raise an error. Exact duplicates collapse to one instrument. Incremental mode
refreshes the complete same snapshot, without a date watermark.

Coverage is limited to POUM and mobility-study entries in this inventory. It
does not claim all planning modifications, public works, historical files,
public information notices or granted licences. No parcel or municipal-centroid
coordinates are substituted. PDFs contain maps but this adapter extracts no
verified vector geometry. The shared registry's entity policy currently labels
both records `pendiente / insufficient_identity_evidence`; that annotation is
retained in evidence and does not imply eligibility for activity publication.

## Validation

- `.../venv/bin/python -m unittest municipio.test_quart -v`: **5 tests passed**.
  They cover grouped documents, excluded non-project rows, distinct date
  semantics, absent dates, stable IDs, duplicates, all embedded rows, failure
  cases, manifest loading and snapshot update through the registry.
- A real `load_portal_adapter(load_manifest('quart')).backfill_proyectos(...)`
  request returned **2 records**. Its runtime config enabled a local HTML capture.
- `evidence/proyectos.jsonl` contains actual extracted records;
  `evidence/validation.json` records source URLs, HTTP document checks, the live
  count, limitations and registry policy results. Evidence stays local.
- No shared source files, dependencies, credentials, databases, production,
  deployment, publishing or Git metadata were modified.
