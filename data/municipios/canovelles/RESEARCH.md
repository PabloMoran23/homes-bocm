# Canovelles — INE 08041, Barcelona

Verified 2026-11-07 using the preinstalled batch virtualenv. One municipal adapter,
projects only. Scheduling, licence extraction and missing-coordinate jitter are
all disabled. This is a real but partial municipal snapshot, not map-ready data.

## Official source discovery

- [Municipal urbanism topic](https://www.canovelles.cat/temes/154-urbanisme)
  and [urbanism regulations](https://www.canovelles.cat/ajuntament/normativa/urbanisme/)
  identify municipal planning resources and link the official transparency portal.
- [Transparency urbanism index](https://seu-e.cat/ca/web/canovelles/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme)
  returned HTTP 200 and identifies the actual suffixed inventory URLs below.
- [Works inventory — implemented source](https://seu-e.cat/ca/web/canovelles/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/projectes-d-obres-i-activitats-211)
  returned HTTP 200. Its static HTML contains year sections from 2015 through 2026,
  with technical projects, plans, budgets, agreements and notices. Page update:
  18/09/2026. That update is not a project publication or agreement date. The
  unsuffixed guessed URL returned 404 and is not used by the adapter.
- [Planning inventory](https://seu-e.cat/ca/web/canovelles/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic)
  returned HTTP 200: one table entry for Sector Z Can Xarlet / Can Ferran phase 5,
  plus free-text planning material. That physical work is already included in the
  works inventory; the planning page is not separately scraped into duplicate rows.
- [Urban management](https://seu-e.cat/ca/web/canovelles/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/gestio-urbanistica-212)
  returned HTTP 200: Ca la Piua reparcel·lació and urbanisation versions, including
  repeated expediente 259/2021. Discovered but outside this adapter's coverage;
  extracting it would require deliberate version consolidation.
- [Avanç del POUM](https://www.canovelles.cat/temes/154-urbanisme/avanc-del-poum/)
  returned HTTP 200. Explicitly says the advance was approved in 2016 but never
  developed into a definitive POUM; the PGO remains governing planning. Numerous
  documents describe that single advance, not separate projects. Not extracted.
- [Urban licences](https://seu-e.cat/ca/web/canovelles/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/llicencies-urbanistiques-220)
  returned HTTP 200: “LLICÈNCIES EN CURS”, provisional use/works dossier 2034/2025,
  technical memorandum and public-information notice. No granted licence inferred.

## Extraction and provenance

The adapter fetches only the complete works inventory, with HTTP error checks,
40-second timeout, HTML content-type verification and a 4 MB response bound.
No page limit truncates results: the reviewed source is static and unpaginated.
A next-page control or server-side table declaration fails explicitly for review.
Unknown headings, unassigned documents, missing technical files, unexpected
provenance, duplicate identities and empty/login responses fail before output.

Live result: **35 published inventory entries, 137 retained document links**.
Three activity/legalisation dossiers and one service cost-structure proposal are
excluded. Each eligible heading must have actual technical documentation;
an announcement alone cannot establish a project. Source titles are retained.
All documents under a heading are grouped, including approval notices and annexes,
with link text, full list-item context, official URL and source page provenance.
Document URLs belong to the municipality's `/documents/2562153/` repository.
PDF content and the availability of every linked PDF have not been verified.

The five-building photovoltaic bundle remains one published inventory entry with
seven links, rather than five invented independent dossiers. The 2021 and 2025
Tagamanent vestibule entries have distinct technical documents and remain separate
published versions; no common expediente or identity is inferred from similar
names. Stable scraper IDs derive from the first technical document identifier,
not from an invented municipal expediente. Changing that document can change ID.
Updates refresh the full snapshot and do not maintain a historical event log.

Phase is the strongest explicit initial/definitive approval label in the linked
list-item descriptions; it does not prove construction progress or latest legal
status. Each document retains its own phase label. All exact publication,
agreement and approval dates remain null: the parser does not read PDF dates or
promote section years, filenames or crawl dates into legal dates.

No coordinates or feature geometry have been verified. Graphical documents remain
links, not extracted geometry. Latitude, longitude and geometry are null and
`publication_ready` is false. No municipal centroid or random jitter is used.

## Verification and limitations

- `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_canovelles -v`:
  five offline parser/interface tests passed. They cover grouping, phase/date
  semantics, stable identity, exclusions, missing technical files, pagination,
  unexpected headings, snapshot updates and disabled licences.
- Live extraction used `load_manifest('canovelles')` and `load_portal_adapter`,
  calling only `backfill_proyectos(evidence/proyectos.jsonl)`. Manifest identity
  and disabled settings were also asserted.
- The shared entity-policy wrapper classifies these rows as pending and reports
  `unknown_entity_spike` (35/35): it requires expediente evidence not exposed by
  this HTML inventory. No reference was invented to bypass that guard. This limits
  ingestion eligibility, not the existence of the source-backed works. Shared
  policy is unchanged; independent review is required before further ingestion.
- Local, uncommitted evidence includes `proyectos.jsonl`, `validation.json`, the
  entity-policy report, `live-obras.html`, and captures of the discovered inventories.
  Captures and validation explain the partial coverage and date/geometry limits.
- No dependencies or shared source files changed. No credentials, database,
  deployment, publishing or git mutation operations were used.
