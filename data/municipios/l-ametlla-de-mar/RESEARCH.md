# L'Ametlla de Mar — Tarragona — INE 43013

Verified live on 2026-11-09 with the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
This adapter extracts **derived planning instruments**, not granted licences.
Scheduling and missing-coordinate jitter are disabled. `publication_ready` is
false: there is no verified project geometry in this extraction.

## Official source discovery

- [Municipal Urbanisme page](https://www.ametllamar.cat/ajuntament/per-temes/urbanisme/)
  (HTTP 200) embeds the municipal document directory in an iframe. This is the
  provenance chain for the inventory, checked again on every extraction.
- [Directory root](https://ametllamar.cat/ajuntament/backoffice/seccions/urbanisme/)
  (HTTP 200) exposes five branches: POUM, consolidated urban area, derived
  planning, POUM amendments and acoustic capacity map. These are document
  inventories, not a register of granted building licences. The Urbanisme page
  also links procurement and application procedures; neither becomes a record.
- [Derived-planning inventory](https://ametllamar.cat/ajuntament/backoffice/seccions/urbanisme/?dir=03.+Planejament+derivat)
  (HTTP 200) contains seven instrument folders. Every descendant directory in
  this branch was traversed, including nested annexes and information/ordering
  drawings. The current inventory has no pagination. The parser rejects paging
  controls, unexpected traversal, missing structure and empty instrument bundles
  instead of silently writing partial output.

## Live coverage

| Source instrument folder | Retained PDF/DOC links |
| --- | ---: |
| PEU CÃ mping Ametlla Village | 4 |
| PMU Sant Jordi Bosc | 1 |
| Pla Parcial 3 Cales Segona Fase | 60 |
| Sector K1 | 2 |
| Sector O | 2 |
| Sector PPU 21 | 1 |
| Sector PPU 22b1 | 5 |

Total: **7 records, 75 document links, 15 fetched HTML pages**. One record is a
municipally defined instrument folder, with all associated documents, versions
and amendments retained in `documentos`; drawings and reports do not become
separate projects. For example, the camping folder includes its environmental
report, consolidated text, BOP document and modification. Stable IDs derive from
the exact municipal folder path. The camping name's mojibake exists in the live
HTML/path and is preserved to keep source URLs and provenance exact.

Two representative PDFs were also downloaded successfully (HTTP 200, PDF magic
bytes verified), captured and converted to text with preinstalled `pdftotext`:

- Camping environmental report: identifies a special plan for Càmping Ametlla
  Village Platja in Ametlla de Mar. Its August 2010 cover date is a document date,
  not a claimed approval or publication date.
- Sector K1 consolidated regulations: identifies the sector's partial urban plan
  and its regulatory scope. Dates of earlier plans cited in its legal framework
  are not assigned to Sector K1 as its approval date.

All 75 document URLs are retained; only these two PDFs were downloaded for this
validation. Full PDF/DOC content extraction is outside the adapter's scope.

## Semantics and partial coverage

This is a complete snapshot **of the derived-planning branch only**, not complete
municipal coverage. The other four root branches, public works, notices, general
news and licences are excluded. The inventory's presence does not prove that
every document is currently legally effective. No approval phase is inferred
from folder names, document filenames, upload dates or a consolidated-text label.

`fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` and `fase` remain null.
The site's file modification timestamps are retained solely under each document's
`fecha_modificacion_archivo`. Document URLs, source paths and their directory URL
are preserved separately from the municipal landing URL and inventory URL.
No coordinates, parcel geometry, municipality centroid or invented location is
used: `lat`, `lon` and `geometry` remain null.

## Implementation and validation

The adapter implements the existing `AyuntamientoAdapter` contract and loads
through the existing manifest/registry without shared edits. Backfill and update
both refresh the full selected branch. Only after successful complete traversal
is the output atomically replaced; HTTP failures and response/directory limits
raise errors. Anonymous GET requests use explicit timeouts; no authentication is
needed. Licence methods explicitly return disabled with zero records.

Command: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_l_ametlla_de_mar -v`

Seven tests passed: complete recursive grouping/date semantics, stable IDs and
deduplication, pagination rejection, path/source-boundary rejection, missing
structure, empty/changed inventories, manifest safeguards and disabled licences.
The live extraction used `load_manifest`, `load_portal_adapter` and
`backfill_proyectos`, including the existing entity-policy wrapper. Its seven
records receive unknown entity categories; no category or legal status is invented.

Local, uncommitted evidence in `evidence/`:

- `proyectos.jsonl`: actual live adapter output.
- `validation.json`: live count, all fetched source URLs, limitations, test result,
  entity-policy report, validation timestamp and two PDF checks with SHA-256.
- `captures/`: raw HTML captures plus URL sidecars for all 15 fetched pages.
- `document-*.pdf`, `sector-k1.txt`, `camping-ambiental.txt`: representative source
  documents and their extracted text. Additional discovery HTML captures remain
  alongside these files.

No dependencies, shared source files, credentials, databases, deployment systems,
Git internals or external publishing operations were changed or used.
