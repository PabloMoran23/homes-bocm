# Canyelles — INE 08043, Barcelona

Verified live 2026-11-09 using the preinstalled batch virtualenv. Implemented a
partial current snapshot of the official municipal transparency inventory, with
10 genuine project/planning records and 41 attachment links. No licence register
is claimed. Scheduling and coordinate jitter are disabled.

## Discovery and source provenance

- Municipal urbanism service: https://www.canyelles.cat/urbanisme . Describes
  planning consultation and points to the Generalitat planning register. General
  service information and the historic licence-suspension notice are not records.
- Official municipal transparency inventory (HTTP 200):
  https://seu-e.cat/ca/web/canyelles/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme
- Current planning page (HTTP 200):
  https://seu-e.cat/ca/web/canyelles/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  Its live HTML contains the February 2026 verification of MP2 and 13 attachments.
  Search-engine results also expose an older base-POUM table and MP1 content;
  those are not present in the fetched current HTML and are NOT used as records.

All ten detail URLs are discovered afresh from the official inventory, rather
than constructing records from a fixed fixture. Their path suffixes, under the
inventory URL, and coverage are:

| Detail suffix | Instrument / works | Grouped links |
| --- | --- | ---: |
| projecte-executiu-8a-fase_xarxa-de-distribucio-d-aigua-potable.-sector-3-217 | Water distribution, phase 8, sector 3 | 1 |
| memoria-modificat_renovacio-xarxa-aigua-5-carrers-218 | Modified water-network renewal memory, five streets | 1 |
| projecte-d-obres-natura-park-i-piscina-municipal-203 | Natura Park / municipal pool, basic and phased executive documents | 3 |
| projectes-urbanistics-199 | Les Palmeres urbanisation, phase 7 | 2 |
| reparcel-lacio-voluntaria-pau-8-torrent-de-cal-deus-201 | PAU 8 voluntary reparcelation | 3 |
| modificacio-puntual-num.-2-del-poum-204 | POUM amendment 2, combined with current planning page | 22 |
| projecte-d-obres-d-adequacio-de-la-sala-multicultural-fase-1-205 | Sala Multicultural adaptation, phase 1 | 4 |
| modificacio-puntual-num.-3-del-poum-207 | POUM amendment 3 proposal and environmental report | 2 |
| projecte-d-instal-lacio-de-tendals-per-ombra-al-pati-de-l-escola-214 | School-yard shade installation | 2 |
| projecte-executiu-canonada-d-interconnexio-dipostits-atll-daltmar-cogullada.-219 | ATLL–Daltmar–Cogullada reservoir interconnection | 1 |

The generic `projectes-urbanistics-199` page contains one explicitly named project;
its title comes from the page narrative. Changes that make this ambiguous fail.
MP2 initial and verified documents are one instrument: 11 + 13 links, with two
shared attachment UUIDs deduplicated. Both page origins are retained on shared
attachments. Earlier and later document versions with distinct UUIDs are kept.
The Natura Park group retains all phased documents without asserting a single
approval phase for the whole complex.

Other inventory pages were inspected and captured: normative guidance, geographic
information, territorial plans and environmental studies provide generic guidance
or no project documents. `alineacio-sol-195` is a municipal parcel-sale process;
`operacions-delimitadores-del-terme-municipal-197` is boundary demarcation;
`declaracio-de-be-cultural-d-interes-local-215` is a heritage declaration. These
are outside this scraper's project scope. Neither procurement announcements nor
application forms are ingested as granted licences.

## Dates, identity and limits

Only MP2 has an extracted agreement date: **2026-02-18**, from the explicit
verification narrative. This is municipal verification, not definitive approval.
The page update **2026-02-23** is stored separately in `source_updates`; publication
and approval dates stay null. All other dates remain null except explicitly
labelled page-update metadata. Dates embedded in document titles are not parsed.

One MP2 verification certificate was downloaded as an additional evidence check:
HTTP 200, application/pdf, 287141 bytes. Local `pdftotext` output confirms the
18 February session, signature on 20 February and issue date 23 February; these
are distinct events. This manual check does not add hardcoded PDF facts to the
adapter. No PDF text parser or dependency was added.

Stable scraper IDs derive from the official detail URL; these are not claimed as
municipal expediente numbers. The shared entity-policy wrapper reports all ten
as `unknown` / `unknown_entity_spike` because its rules do not establish activity
identity from these unnumbered Catalan inventory pages. This is preserved in the
live validation and not bypassed with invented references. Records are available
for review, but `publication_ready` remains false. No geometry, coordinates,
parcel centroid, grant dates or approval dates are fabricated.

Coverage is the current supported transparency inventory, not every historical
planning instrument, project or licence in Canyelles. Attachment links are
retained with page provenance; their full contents, accessibility and version
history are not systematically crawled. No public granted-licence inventory was
verified.

## Extraction and validation

The adapter fetches the complete supported inventory and each detail, plus the
current planning page for MP2. No pagination was present in inspected pages.
Pagination links cause an explicit error rather than silent truncation. Empty
inventories, missing content/documents, changed MP2 narratives, ambiguous generic
project pages, HTTP failures and oversized HTML abort before replacing output.
Requests use timeouts and a bounded stream. Updates replace the complete current
snapshot, without using page-update dates as incremental cursors.

Commands (from repository root):

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_canyelles -v
```

Six parser/integration tests cover inventory exclusions/deduplication, pagination,
missing documents, update-date semantics, MP2 grouping and attachment provenance,
snapshot refresh, atomic failure, disabled licences and manifest adapter loading.
The real extraction used `load_manifest('canyelles')`, `load_portal_adapter`, then
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, including the normal shared
entity-policy annotation. `capture_dir=evidence` only affects local capture files.

Local uncommitted evidence: `evidence/proyectos.jsonl`, `evidence/validation.json`,
HTML captures of the inventory and inspected detail pages, and the MP2 certificate
PDF/text. Validation includes count, fetched source URLs, limitations and the
shared entity-policy incident. No shared code, dependencies or git metadata were
modified; no external write, database, deployment or publication operation used.
