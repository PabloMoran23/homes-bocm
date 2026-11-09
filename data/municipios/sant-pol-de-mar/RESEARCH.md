# Sant Pol de Mar — INE 08235, Barcelona

Verified live on 2026-11-09 using the preinstalled Python runtime at
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
This adapter covers the municipal public-works document inventory. It does not
claim complete municipal planning coverage, granted licences, or map readiness.
Scheduling and coordinate jitter are disabled.

## Official source discovery

- https://www.santpol.cat/seu-electronica/informacio-municipal/informacio-urbanistica
  links the municipal **Projectes d'obres** inventory to
  https://www.santpol.cat/node/14628 and **Normativa i planejament** to
  https://www.santpol.cat/node/12724. All returned HTTP 200.
- https://www.santpol.cat/node/14628 is the implemented source: four explicit
  sections, public exhibition, contracting stage, execution and executed works.
  It directly names real physical projects and links their technical documents;
  the contracting-stage entry is an energy-efficiency project PDF, not a tender
  announcement. The current full HTML has no pagination or load-more control.
- https://www.santpol.cat/node/12724 and its equivalent
  https://www.santpol.cat/ajuntament/plans-i-programes/planejament-urbanistic
  publish planning regulations, modifications and a horse-riding PAE with
  several documents. These inventories were inspected but are outside this
  adapter's public-works scope. Licence suspensions are not granted licences.
- https://www.santpol.cat/poum/documentacio publishes the POUM at the explicitly
  labelled initial-approval/in-progress stage, with many grouped plan documents
  and two e-Tauler notices. It is not treated as a definitively approved POUM,
  nor are its separate plans, annexes or notices emitted as individual projects.
  This separate planning inventory is outside the implemented scope.
- https://www.santpol.cat/institutescola is an overview linked by the works
  inventory for the Sant Pau school extension. It links project versions and
  a preliminary design. The captured page supports grouping the three inventory
  entries as one overarching extension work. The scraper retains the overview
  link but does not recursively crawl it or its internal attachments.

## Live results and provenance

The manifest-loaded adapter's actual HTTP extraction produced **55 records with
58 distinct linked resources**: 4 in public exhibition, 1 in contracting, 5 in
execution, and 45 in the executed section. All 58 resources returned HTTP 200 to
HEAD requests (57 PDF URLs and one overview page). These availability checks do
not establish PDF contents or administrative approvals.

The bus-stop modification memory was also downloaded and inspected as a PDF:
https://www.santpol.cat/ARXIUS/2026/URBANISME/Memoria_aprovada_JGL_17-8-2026.pdf.
Its first pages identify the physical N-II PK 664 bus-stop modification and carry
a diligence stating initial approval on 17 August 2026, separately from the
20 August digital signature and July drafting month. The scraper does not parse
PDF bodies for dates, so its output date fields remain null even for this sample.

Each record retains the inventory URL, original document titles and URLs,
source section, municipality and province. `fase` is the literal municipal
section label; it is not derived from the project type or independently verified
as a completion certificate. No approval, agreement or publication date is
inferred from a filename, URL year, capture time or signature.

The asphalt memory and its addendum are grouped using the title without the
addendum suffix. Three school-extension entries (overview, executive project
and older project) are grouped; all three original links and titles remain,
without claiming identical scopes. Separate network construction and EDAR
rehabilitation projects, and different-floor Mas Morell renovations, remain
separate works. A stray empty link to Parc del Litoral beside the pumping-station
entry is ignored only because the same URL has its own named inventory entry;
it is not wrongly attached to the pumping station.

Project identity is deterministic from the normalized inventory title, including
the reviewed school grouping. Reordering documents or moving between categories
does not change the ID. A substantive title change can change identity; this is
a full current-inventory snapshot, not an append-only history.

## Extraction behavior and limits

The adapter uses the server-declared ISO-8859-1 encoding, a 35-second request
timeout and a 3 MB HTML bound. It reads the whole current page and never slices
its records. Pagination controls, missing/changed sections, unexpected resource
hosts/types, unnamed orphan documents or conflicting document ownership raise
errors before replacing output. Incremental update refreshes the full snapshot;
it applies no date cutoff. HTML captures can be enabled with `capture_dir` in
local adapter config; no capture path is hard-coded into the manifest.

The source provides project documents without dossier numbers. Accordingly
`source_entity_type=documento` honestly describes the source evidence. The
unchanged shared entity policy classifies all 55 as `documento`, with
`activity_eligible=false`; these records do not establish counted administrative
activity or granted licences. No invented expediente is supplied to bypass that
policy. Licence extraction explicitly returns disabled with zero rows.

Coordinates and geometry remain null, `publication_ready=false`. No municipal
centroid, random jitter or inferred project location is substituted. Most linked
PDF bodies and internal attachments have not been parsed. The page mixes recent
and older works, has no completeness guarantee or per-entry publication dates,
and can retain stale category labels. Its complete extraction is still partial
coverage of the municipality.

## Verification and local evidence

`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_sant_pol_de_mar`
passes 6 tests covering document grouping, stray-link attribution, null dates and
geometry, source provenance, shared entity classification, identity stability,
changed markup, pagination refusal, URL/ownership validation, manifest loading,
Latin-1 responses, snapshot writing and disabled licences.

Live extraction used `load_manifest('sant-pol-de-mar')`,
`load_portal_adapter(manifest)` and `backfill_proyectos`, including the shared
entity-policy annotation. Final policy report: status ok, 55 records, zero
unknown entities. No shared source or dependency files were changed.

Local, uncommitted `evidence/` contains:

- `proyectos.jsonl`: the actual 55 live records.
- `validation.json`: record/document counts, source URLs, phase counts, tests,
  limitations and capture hashes.
- `works-live.html`: exact live response bytes (ISO-8859-1).
- `index.html`, `works.html`, `norms.html`, `plans.html`, `poum.html`,
  `institutescola.html`: discovery captures, saved as UTF-8 text.
- `document-checks.json`: all 58 HEAD results and final URLs.
- `bus-project.pdf` and `bus-project-first-pages.txt`: representative physical
  project and text from its first three pages.
- `extraction-result.json` and `proyectos.entities.json`: extraction/policy reports.
