# Tona — INE 08283, Barcelona

Verified on 2026-11-08 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
This adapter extracts real physical public works from the current municipal
inventory. It does not claim full planning or licence coverage. Scheduling,
licences and missing-coordinate jitter are disabled.

## Source discovery

- https://tona.cat/ajuntament/informacio-oficial/projectes-dobres-municipals/
  — HTTP 200, current municipal public-works inventory, selected extraction
  source. One static page with 27 project headings across the source's year
  sections 2023, 2025 and 2026. All 27 are extracted, without a row cap. Each
  provides a named work, municipal expediente, and linked project or technical
  memoir. There are 29 distinct document links: 26 works have one document and
  URB/2025/337 groups three well-recovery projects. Procurement milestones occur
  within these independently documented physical works; they are not standalone
  tender announcements emitted as projects.
- https://tona.cat/ajuntament/informacio-oficial/planejament-urbanistic/
  — HTTP 200. Separate planning inventory linking the POUM, centre-protection
  special plan, a Balenyà street volume-ordering detail study, acoustic-capacity
  map, and the RPUC search. Discovered but not extracted by this adapter. These
  navigation links are not treated as detailed instrument records.
- https://tona.cat/ajuntament/informacio-oficial/gestio-urbanistica/
  — HTTP 200, explanatory urbanisation/reparcellation page with a CIDO link,
  rather than detailed project rows. Excluded.
- https://tona.cat/ajuntament/informacio-oficial/plans-programes-i-projectes/
  — guessed discovery path returned HTTP 404; not an extraction source.
- https://tona.cat/poum/ — discovered through official-site search as an
  alternative POUM explanation. Not requested by the adapter and not included
  as an additional record or independent evidence of approval.

Source captures: `evidence/obres.html` (the exact adapter live response),
`evidence/discovery-0.html` (planning), `discovery-1.html` (urban management),
and `discovery-2.html` (404). These are local evidence, not source files.

## Parsing, identity and provenance

The parser requires the inventory title and content container, year headings,
structured project fields, one genuine expediente and at least one technical
document per work. Missing or changed structure raises an error. Stable IDs
are hashes of the municipal expediente, not title or document position. Works
with the same title but different expedientes remain distinct (e.g. the two
street-paving entries). Identical repeated entries are deduplicated; conflicting
entries for one expediente fail for review. Each record retains all its document
links, titles, source field labels and source inventory URL, including the three
well documents in one record. Electronic-office query parameters are preserved
because they form part of the public document links.

The complete inventory is refreshed on updates, including existing milestones.
There is no pagination in the reviewed source. Pagination markup or next-page
links cause failure rather than silently return the first page. Responses have
connection/read timeouts, a 4 MB limit, HTTP error handling, and a municipal-host
redirect check. Output is replaced only after successful complete parsing.

## Date and location semantics

All original labelled fields and date milestones are retained. Initial approval,
definitive approval and technical-memoir approval have separate fields.
`fecha_aprob` selects definitive approval when present, otherwise initial or
memoir approval. `fase` describes only that explicitly stated approval stage;
it does not infer current construction status from milestone dates. Tender,
award, execution and framework-agreement dates retain their original labels in
`hitos`, including missing dates as null. `fecha`, `fecha_publicacion` and
`fecha_acuerdo` are null: the page provides no separate project publication date
or generic agreement date. Inventory year is not an approval date. In particular,
source approval dates in 2024 under the 2025 section are preserved, not corrected.

Milestones are municipal assertions, not independently checked against signed
agreements or PDF contents; scheduled dates do not prove completed work. No PDF
contents were downloaded or parsed. Source links are document provenance, not a
claim that every linked download remains accessible. There is no verified project
geometry in this extraction: lat, lon and geometry remain null and
`publication_ready` is false. No centroid, address geocoding or random location
is substituted. No granted-licence register was verified; forms and unrelated
news are excluded.

## Validation

- `python -m unittest municipio.test_tona -v`: six tests passed. Covers separate
  date meanings, old colon syntax and memoir approvals, missing dates, multiple
  documents, identity/deduplication, malformed records, invalid dates, pagination
  rejection, manifest settings, disabled licences and snapshot updates.
- Direct live `TonaAyuntamientoAdapter.backfill_proyectos` with capture enabled:
  status ok, **27 records, 29 document links**, 27 unique expedientes.
- `evidence/proyectos.jsonl`: actual live output.
- `evidence/validation.json`: live count, source URL, timestamp and limitations.
- Only the four requested source files are added. Evidence remains local;
  no shared source, dependencies, database or deployment was changed.
