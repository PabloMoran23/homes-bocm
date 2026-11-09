# Navàs — Barcelona — INE 08141

Verified live 2026-11-09 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
This adapter provides a deliberately partial snapshot of two official municipal
planning document inventories. It does not establish the complete consolidated
planning regime or claim a public granted-licence register.

## Official sources discovered

The current municipal homepage https://www.navas.cat/ links to the POUM and
heritage catalogue pages, plus an RPUC link for the rural-house special plan.
The homepage and https://www.navas.cat/ajuntament/transparencia/ returned HTTP 200;
captures are in local evidence. Only the two detailed municipal inventories below
are extracted, not navigation links or generic service descriptions.

- https://www.navas.cat/municipi/navas/poum/ — HTTP 200, six document blocks:
  rules, planning sheets, classification of other settlements, urban/developable
  land, non-developable land and heritage map. These are **one POUM record**.
  The page describes the Text Refòs and states definitive approval in April 2019.
  That claim is retained with its exact source text and month precision in
  `fecha_aprob_mes=2019-04`. No day is inferred: `fecha_aprob`, `fecha_acuerdo`
  and `fecha_publicacion` remain null. The 2021/01 upload directory is neither
  an agreement date nor a publication date. The page's claim is not independent
  verification of the approval instrument or subsequent consolidation.
- https://www.navas.cat/municipi/navas/pla-especial-urbanistic-de-proteccio-del-patrimoni-i-cataleg-de-bens-arquitectonics-historics-i-ambientals-de-navas/
  — HTTP 200, describes the actual heritage special plan. Its three volumes
  (memory/rules/maps and two catalogue volumes) form **one record**, rather than
  three projects or 227 individual projects from the catalogue's asset count.
  No phase or dates are stated in this page's narrative; all remain null.
- https://navas.eadministracio.cat/info.0 and
  https://navas.eadministracio.cat/board — HTTP 200, actual current municipal seat
  and notice board. The board includes an initial-approval notice for the new
  multifunctional building at the sports complex, dossier 2651/2026, published
  30/10/2026. Its procedure column says Contractacions, which alone cannot
  establish a physical project or its approval. The board has **Veure'n més**;
  this adapter excludes the entire board, rather than pretending the first ten
  visible notices are complete. Neither that notice nor unrelated recruitment,
  tax, subsidy or procurement notices are emitted.
- https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/233214 — municipal
  navigation link labelled as the rural-house special plan. Not fetched or
  emitted as a third record: navigation alone is insufficient detailed evidence.

## Extraction contract and limitations

One adapter, two explicitly scoped single-page document inventories. It requests
both pages on every backfill/update, using 35-second request timeouts and a 3 MB
HTML response limit. It requires instrument headings, a Navàs narrative, and
usable official PDF links in every document block. It preserves all linked
attachments and labels with their parent source URL, deduplicates identical URLs
within each instrument, and derives stable record IDs from instrument page URLs.
It does not parse PDF contents or check each attachment's availability.

A changed heading, missing content/documents, unexpected document host or detected
next/load-more control fails extraction. No pagination is silently truncated.
Both pages must parse before output replaces the previous snapshot. No checkpoint
or date filter discards older documents. Updates refresh both complete pages.
The separate paginated notice board remains outside the declared coverage.

No project geometry was verified. Coordinates and geometry remain null;
`publication_ready=false`, `schedule.enabled=false`,
`geocode.jitter_missing=false`, `licencias.enabled=false`.
The shared registry's entity policy annotates both records as `pendiente` /
`insufficient_identity_evidence` because these pages do not provide dossier
references recognized by that policy. They remain `activity_eligible=false`;
no fake expediente or policy override is introduced. These are real documented
planning instruments, but not publication-ready activity records.

## Validation and local evidence

- `python -m unittest municipio.test_navas -v`: six tests passed, covering grouping,
  partial date precision, absent dates/phase, invalid content and document URLs,
  pagination rejection, failed-snapshot preservation, update output and manifest.
- A real live run through `load_manifest('navas')` and `load_portal_adapter`
  produced **2 records with 9 retained document links**.
- `evidence/proyectos.jsonl`: actual live records, including shared policy
  annotations. `evidence/validation.json`: live count, source URLs, runtime,
  parser-test result and coverage limitations.
- `evidence/poum.html`, `evidence/patrimoni.html`: exact live adapter responses.
  `evidence/discovery-0.html` through `discovery-3.html`, `catalog.html`, and
  `board.html`: source discovery captures.
- Evidence is local and excluded from the four source files for review. No
  credentials, external workspaces, databases, deployment or publishing used.
