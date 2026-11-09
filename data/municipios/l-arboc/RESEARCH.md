# L'Arboç — INE 43016, Tarragona

Verified on 2026-11-09 using the preinstalled batch virtual environment.
One adapter, deliberately partial coverage: the publicly accessible municipal
POUM document inventory. This is a genuine planning instrument, not an invented
project derived from a form or tender. Scheduling and licence extraction are
disabled. Missing geometry is never replaced by a municipal centroid or jitter.

## Official sources discovered

- https://www.arbocenc.cat/ — HTTP 200, current municipal website. Links to the
  current electronic headquarters at https://arbocenc.eadministracio.cat/ and
  its transparency portal. Municipal news is not treated as a project inventory.
- https://arbocenc.eadministracio.cat/transparency — HTTP 200; current public
  transparency folder tree. Its action/government folder at
  https://arbocenc.eadministracio.cat/transparency/04c8b7e6-1774-4813-be5b-cf02bcdb0c7d/
  exposes council minutes, government-board minutes and decrees, rather than
  a direct project inventory. The wider session-driven document archive is
  outside this adapter's coverage; no claim of exhaustive archive discovery.
- https://seu-e.cat/ca/web/arboc/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/normativa-d-urbanisme
  — HTTP 200, municipal transparency inventory, explicitly sourced to “Propi ens”.
  Four table rows: three POUM document sections and an acoustic map. The three
  sections are Memòria ambiental (5 documents), Normativa (7), Annexos (2).
  All three specify publication on **2016-02-24**. Table update is **2018-06-28**,
  not a project agreement or publication date. The acoustic map is excluded as
  an environmental regulation resource rather than another physical project.
- https://seu-e.cat/ca/web/arboc/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  — HTTP 200, links to the official RPUC municipal query:
  https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=43016
  — HTTP 200 after redirect to an Angular application shell at
  planejamenturbanisme.territori.gencat.cat. No dossier rows or verified geometry
  are available in that HTML. This query is not emitted as a second project.
- The linked normative PDF was downloaded successfully (HTTP 200,
  application/pdf, 1,629,854 bytes):
  https://seu-e.cat/documents/8061681/8642920/Normativa.pdf/023813c8-d96b-40bb-ab02-f742e246d3a0
  Its first page identifies the POUM of L'Arboç, “Text refós”, May 2009, and
  corrections incorporated under a CTUT agreement dated 25.06.2009. That
  corrections reference is not assigned as the POUM approval date. The adapter
  retains the original document link; it does not parse PDF dates as agreements.

## Extraction semantics and limits

One stable record (`l-arboc-poum`) groups all 14 document URLs and titles, with
section provenance and original section publication dates. No document becomes
an independent instrument. A shared document is deduplicated while retaining
all section memberships. Unknown new POUM sections fail for grouping review.
`fecha_publicacion` is populated only if every included section has the same
date; otherwise dates remain at section level. `fecha`, `fecha_aprob`,
`fecha_acuerdo` and `fase` remain null. Document dates do not establish present
legal phase. The inventory is accessible now but dated: consolidated current
validity and subsequent modifications have not been certified.

All table rows are present in server HTML. DataTables is configured for local
sorting/filtering/pagination without AJAX or server-side loading. The parser
reads every embedded row with no page/row slice, including the site's malformed
nested `tr` markup. It rejects detected remote loading or pagination controls,
unexpected tables, foreign document provenance and missing normative documents.
HTTP errors, redirects outside the exact inventory and oversized responses fail
before writing records. Update refreshes the entire snapshot, without a
publication-date watermark. Licence forms and procurement notices are excluded.

Coordinates and geometry are null, `publication_ready=false`. The shared entity
policy labels this document inventory `unknown`, with activity eligibility false;
it is not evidence of a newly approved or executed development. Neither broader
planning coverage nor a public granted-licence register is claimed.

## Validation and local evidence

- `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_l_arboc -v`
  — 8 parser/contract tests: real malformed table shape, grouping/deduplication,
  publication semantics, rejection of forms and foreign sources, no row limit,
  pagination failure, new-instrument grouping guard, manifest loading and disabled licences.
- Live extraction through `load_portal_adapter(load_manifest('l-arboc'))` and
  `backfill_proyectos`: **1 record, 14 linked documents**. Evidence includes the
  shared policy annotation and extraction time, never substituted for source dates.
- Local uncommitted `evidence/proyectos.jsonl`, `evidence/validation.json`,
  `evidence/live-inventory.html`, discovery HTML captures, `evidence/normativa.pdf`
  and `evidence/normativa-first-pages.txt` retain the review trail.
- Only the four requested source files are added. No shared code or dependencies
  changed; no publish, deployment, database, credential or git-write operations.
