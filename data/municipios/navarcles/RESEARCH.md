# Navarcles — INE 08140, Barcelona

Verified live on 2026-11-09 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
One real planning instrument, the **Avanç del POUM**, is extracted with eight
source documents. Coverage is deliberately partial, not a historical municipal
project inventory. Licence extraction, scheduling and missing-coordinate jitter
are disabled. No geometry or coordinates are inferred.

## Official source discovery

- https://www.navarcles.cat/ajuntament/poum — municipal POUM overview, HTTP 200.
  Its narrative explicitly identifies approval of the advance by the council on
  2026-04-28. This is not definitive approval of a new POUM. The page describes
  the consultation as ending 2026-09-03; extraction does not assert it remains open.
- https://www.navarcles.cat/ajuntament/poum/documentacio-avanc-poum — current
  municipal document inventory, HTTP 200. Three linked subsections, all followed:
  `anunci-poum`, `avanc-poum`, `document-inicial-estrategic-die`.
- https://www.navarcles.cat/ajuntament/poum/programa-de-participacio-ciutadana —
  related POUM participation programme, HTTP 200; followed from the overview.
- https://seu-e.cat/ca/web/navarcles/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  — official transparency inventory, HTTP 200. Shows a licence-suspension entry
  X2025000582 concerning the open-space network modification and links to RPUC/MUC.
  A suspension is not a granted licence and is not emitted as one. This adapter
  does not claim coverage of that separate modification.
- https://cido.diba.cat/normativa_local/6780199/planejament-urbanistic-ajuntament-de-navarcles
  — Diputació official planning publication inventory, HTTP 200. Contains historic
  amendments and 2026 entries for the 33rd NNSS modification and POUM participation.
  Used for discovery, not treated as one project per publication. Historical
  grouping across those instruments remains outside this adapter's coverage.

## Document provenance and date semantics

Six municipal HTML pages are visited, including the overview and document index.
Eight PDFs belong to the same instrument and remain grouped in `documentos`:
announcement, advance memory, four graphic-document parts, initial strategic
environmental document and participation programme. Each retains its official URL,
link title and referring page (`url_fuente`, `paginas_fuente`). PDF attachments are
in the `#page-documents` sidebar, outside `#readspeakerPage` article text.

The announcement PDF at
https://www.navarcles.cat/media/repository/POUM/Documents/ANUNCI_POUM.pdf
was downloaded and its text inspected. It confirms the council's 2026-04-28
agreement approving the advance, participation programme and environmental
document; its header identifies expediente 2026/000006/0808. That PDF-only number
is not guessed by the HTML adapter. Signature 2026-05-21 and print date 2026-05-27
are neither agreement nor publication dates.

`fecha_acuerdo` and `fecha_aprob` come from the explicit overview approval sentence.
`fecha_publicacion` and generic `fecha` remain null. Page-update timestamps are not
publication dates. `fase` is approval of the advance, not final approval or a
licence. The description retains the municipal narrative, including its historical
consultation wording, without asserting a new current stage. Stable record identity
is the municipal POUM advance, independent of attachment count or order.

## Extraction and limitations

The adapter discovers all descendants of the document inventory and the linked
participation programme, deduplicating URLs and retaining document provenance.
No pagination exists in the reviewed document tree; pagination controls/query
parameters trigger failure for review. The 30-page and 3 MB per HTML response
bounds raise errors rather than truncate output. Empty document pages, missing
inventory links, absent approval narrative and HTTP errors abort extraction before
replacing an existing snapshot. Update refreshes the complete supported tree.

The large planning PDFs are linked rather than downloaded on every run. No parcel,
sector boundary or project geometry has been verified; `lat`, `lon` and `geometry`
are null and `publication_ready` is false. The scraper does not cover every historic
planning instrument, municipal public work, granted licence, procurement notice,
form or general news article. The discovery inventories are documented separately
from the six pages actually used to produce the record.

## Validation and local evidence

- `.../venv/bin/python -m unittest municipio.test_navarcles -v`: eight tests pass,
  covering approval/publication semantics, missing narrative, pagination, document
  scope/deduplication, sidebar attachments, full-tree refresh, atomic failure and
  manifest/disabled-licence configuration.
- Live extraction through `load_portal_adapter(load_manifest('navarcles'))` and
  `backfill_proyectos`: one record, eight linked PDFs, six municipal HTML sources.
- `evidence/proyectos.jsonl`: actual live output including shared policy annotation.
- `evidence/validation.json`: extraction timestamp, record count, source URLs,
  discovery results, test result and explicit limitations.
- `evidence/*.html`: source captures; `ANUNCI_POUM.pdf` and `ANUNCI_POUM.txt`:
  independent announcement inspection. Evidence remains local and uncommitted.
