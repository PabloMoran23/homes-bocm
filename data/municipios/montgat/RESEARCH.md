# Montgat — INE 08126, Barcelona

Verified live on 2026-11-07 using the preinstalled Python 3.12 virtual environment.
The adapter extracts the complete visible municipal public-exhibition list:
14 named instruments/physical works, including one Mallorquines planning
instrument enriched with 20 document links. Municipal coverage is partial.
`publication_ready` is false; scheduling, licences, and coordinate jitter are disabled.

## Official inventories examined

- [Public-exhibition inventory](https://seu-e.cat/ca/web/montgat/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/processos-en-exposicio-publica-361),
  HTTP 200. A static `.journal-content-article` contains 14 paragraphs, updated
  27/04/2026. These name concrete works/plans: pavement repairs on named streets,
  parcel 57's special plan, Passeig Marítim repairs, Escola TIMÓ accessibility,
  petanca facilities in Parc de les Bateries, Joaquim Costa urbanisation,
  Catalunya slope regeneration, Buenos Aires drainage connection, Passatge Alt
  collector, Les Costes electricity connections, Escola Norai wall, Biblioteca
  Tirant lo Blanc repairs, Avenir pedestrianisation, and the Mallorquines PGM
  modification. The actual response has no document anchors within this list,
  no individual identifiers and no project dates. Its update date is NOT a
  publication, agreement, approval or works-start date. Listing here does not
  prove that works are underway or that exposure is still open.
- [Municipal planning index](https://www.montgat.cat/ajuntament/regulacio-urbanistica/planejament-urbanistic),
  HTTP 200. Two unique detail links, repeated in desktop/mobile widgets.
  Both concern Mallorquines; they are grouped, not emitted as separate projects.
  Generic AMB/RPUC search links are not themselves project records.
- [Initial approval dossier](https://www.montgat.cat/ajuntament/regulacio-urbanistica/planejament-urbanistic/aprovacio-inicial-de-la-modificacio-del-pla-general-metropolita-en-lambit-del-barri-de-les-mallorquines-ha-finalitzat-el-termini-dexposicio-publica),
  HTTP 200. Narrative explicitly states initial approval by the Ple on
  **2025-12-18**, renewed public-exhibition agreement **2026-01-29**, and dossier
  **2248-7868/2025**. The consultation deadline (2026-04-16) and page-update
  timestamp (2026-06-02) are not approval dates. Ten technical-document CSV
  validation links and four newspaper/BOPB notice PDFs are retained with source
  page provenance. D8-02 is described as withdrawn and has no published link;
  no replacement URL is invented.
- [Advance/participation dossier](https://www.montgat.cat/ajuntament/regulacio-urbanistica/planejament-urbanistic/avanc-de-planejament-dun-sector-del-barri-de-les-mallorquines-darrer-trimestre-2022-i-primer-trimestre-2023),
  HTTP 200. Six attachments (including the unitary plan, environmental and
  mobility documents, participation programme/results and an image) are retained
  under the same instrument with `etapa=avance`. Its narrative says approval on
  19 October without an explicit year in that sentence: no complete agreement
  date is inferred from its heading or surrounding participation chronology.
- [Public-works table](https://seu-e.cat/ca/web/montgat/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/obres-i-actuacions-en-l-espai-public-342),
  HTTP 200. Five works labelled awarded, with planned starts in November/December
  2017 and an update of 27/10/2017. Inspected and captured, but excluded from the
  deliberately current exhibition-list coverage. No claim of completed works.
- The municipal planning index also links AMB's Montgat-filtered search, RPUC
  and CIDO. The AMB response was captured during research. Full metropolitan or
  historical planning-register coverage is outside this adapter's scope.

## Dates, grouping and provenance

Each inventory paragraph becomes one record, using a deterministic hash of its
normalised source title (not a fabricated expediente). Mallorquines is enriched
only if there is exactly one matching inventory instrument and one initial
approval detail. All planning-index detail pages are visited and their document
links grouped by exact URL. Every document retains its original label, source
page, stage, URL and link kind; CSV query strings are preserved.

`fecha_acuerdo` and `fecha_aprob` are 2025-12-18 for the initial approval only.
The later renewed-exhibition agreement is a separate event, not another approval.
`fecha_publicacion` remains null at record level. The explicitly labelled BOPB
notices preserve 2026-01-08 and 2026-02-05 at document level with the label as
provenance. The first BOPB PDF was also downloaded and converted with the existing
`pdftotext`: it confirms bulletin date 8-1-2026, session 18 December 2025,
dossier 2248-7868/2025 and signature 29 December 2025. Those dates have distinct
meanings. Other projects have no inferred dates or execution phase.

The adapter preserves document links but does not claim to download/parse all
PDF contents or resolve the CSV validation workflow. There is no verified vector
geometry; `lat`, `lon`, and `geometry` are null. No town centroid, jitter or
address geocoding is substituted. No licence applications, procurement notices
or unrelated news are emitted as granted licences or projects.

## Transport and completeness

The municipal host serves its leaf and YR2 certificates but omits the Root YR
cross-sign needed by this runtime's trust store. Initial research captures used
unverified TLS solely to diagnose this; the final live extraction uses verified
TLS throughout. The adapter obtains the [official cross-signed certificate](https://letsencrypt.org/certs/gen-y/root-yr-by-x1.pem)
over already verified HTTPS and loads it into a local SSL context. It does not
change the system trust store, disable verification, or install dependencies.

Responses have 35-second timeouts and a 4 MB limit. Unexpected containers,
empty lists, unknown entries/instruments, ambiguous grouping, missing documents
or changed date narratives raise errors before output replacement. Sources are
static, unpaginated lists; next links or active pagination controls cause an
explicit failure rather than silent first-page extraction. There is no row cap.
Updates refresh the entire snapshot and ignore incremental state. Desktop/mobile
menu duplicates do not create duplicate instruments. Output replacement is atomic.

## Validation and remaining limits

- `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_montgat -v`:
  **6 tests passed**. They cover date separation, no inferred advance year,
  grouping/document provenance, menu deduplication, pagination/change rejection,
  preservation of an existing snapshot on failure, and disabled licences.
- Live extraction through `load_manifest` and `load_portal_adapter`, calling only
  `backfill_proyectos`: **14 records**, **20 document links**, unique IDs,
  no invented coordinates. No pipeline all/publish or external writes were used.
- Shared entity-policy annotation is retained in the evidence: Mallorquines has
  a referenced expediente; the other **13 title-only entries remain pending**.
  The shared policy reports `adapter_incident / unknown_entity_spike`. This is
  disclosed, not bypassed by inventing official IDs or editing shared policy.
  The scraper is reviewable, but these entries are not publication-ready.
- Local evidence: `evidence/proyectos.jsonl`, `evidence/validation.json`, verified
  response captures in `evidence/live/`, research HTML snapshots, the cross-sign,
  and the first BOPB PDF/text. Evidence is local only and is not committed.

This is not an exhaustive historical municipal register, proof of current
execution, granted-licence coverage, or a map-ready dataset.
