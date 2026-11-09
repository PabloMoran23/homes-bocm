# Llançà — INE 17092, Girona, Catalunya

Verified live on 2026-11-09. This adapter covers the **current municipal technical
project inventory**, with one record per documented dossier. It does not claim
complete municipal planning, historical works or granted-licence coverage.
Scheduling and coordinate jitter are disabled; records have publication_ready=false.

## Official sources discovered

- https://www.llanca.cat/projectes-tecnics/ — HTTP 200, legacy works inventory.
  Municipal navigation and its replacement notice link to the current source below.
  The current source calls this ANTIGA WEB, with a planned end in 2024, although
  it remains reachable. It is researched, not combined with current dossiers:
  doing so would risk double counting migrated documents.
- https://llanca.eadministracio.cat/transparency/330458c5-008e-4021-b597-b61b6f6d3bf6/
  — HTTP 200, **WEB - Projectes Tècnics**, implemented source. Live year folders:
  2026 (14 documents), 2025 (15 documents), 2024 (7 documents). The figures are
  document counts, not project counts. The live source is newer than the search
  engine snapshot, which still showed only five 2026 documents.
- https://llanca.eadministracio.cat/transparency/10b36a2b-d06c-4613-b32d-e1662e49473c/
  — 2026: seven documented projects, 14 links. Includes beach preparation works,
  sediment removal in rec Boquer, sports-pavilion enclosure refurbishment,
  football-field lighting, street resurfacing, Rafel Estela reurbanisation and
  Casa Marly roof repair.
- https://llanca.eadministracio.cat/transparency/1585cc1c-2888-4d23-a740-f99e685ea352/
  — 2025: five projects, 15 links. Artificial turf replacement, access works to
  the town/Casa Marly, street resurfacing, motorhome service area and columbaria.
- https://llanca.eadministracio.cat/transparency/2649c694-8ed6-4afb-8ba7-c89cf031c798/
  — 2024: two documented projects, seven links (Centre de Fires modification and
  water-distribution network renewal). Three empty dossiers are visited and
  reported separately: 240/2024, 550/2024, 1306/2024. They do not become records.
- https://www.llanca.cat/planejament-derivat/ — HTTP 200, legacy detailed-planning
  documents grouped by instrument, with a replacement link to the current portal.
- https://llanca.eadministracio.cat/transparency/0370580a-5e7a-428e-8b14-0a59c87ace5c/
  — HTTP 200, current planning inventory: PGOU (0), PGOU modifications (30),
  derived planning (18), specific non-developable-land action project (1).
  These are outside this adapter's explicit technical-works coverage.
- https://llanca.eadministracio.cat/transparency/a9994130-2c8e-49c6-b4cf-a77dc7583ef0/
  — HTTP 200, current urban-management inventory: PMU 3 Super Fener urbanisation
  project update (3 documents), plus a legacy-site link. Outside implemented scope.
- https://www.llanca.cat/tramitacio-electronica/ — HTTP 200, application forms
  including major/minor works permits. Forms are not granted licences; none emitted.

## Extraction, identity and provenance

Anonymous requests use a fresh requests.Session. Wicket folder anchors contain
session-specific callbacks. Their response's Ajax-Location header identifies a
stable public /transparency/UUID/ folder. These callbacks are followed with GET;
no login or private citizen folders are accessed. Callback tokens are not record
identifiers or retained document links.

The crawler visits the root, every year and every dossier: **21 inventory pages**.
It emits **14 projects with 36 document links**, retaining the technical plans,
modified versions, BOP/DOGC notices and each source title/description together in
`documentos`. IDs derive from the stable dossier URL; expediente is copied from
the official folder title, including the source's short year in 2783/26. Different
expedientes remain distinct even if they concern the same building or street.
A repeated expediente across years causes an error pending grouping review.

Document URLs are the official stable /preview-document/UUID links, not guessed
PDF downloads. One was additionally checked anonymously with HTTP 200:
https://llanca.eadministracio.cat/preview-document/5441c38a-df9e-4ce0-9896-fd0350372eff
exposes the named beach-works document as a PDF resource, with metadata and a
copy-download action. The adapter does not download/parse all PDF contents and
does not claim that all underlying download actions were verified.

Publication, agreement and approval dates remain separate null fields. Folder
years, the seat's live clock, document creation timestamps and dates embedded in
filenames are not substituted for agreement dates. Labels mentioning initial or
definitive approval remain verbatim document metadata; no single dossier phase
is inferred from possibly mixed document versions. All coordinates and geometry
remain null; no municipal centroid, random point or filename-derived coordinates.

No pagination was present in the live inventory. Every project document count and
every year's aggregate count is checked against the advertised count, including
empty folders. Pagination controls, mismatches, unknown rows, nested document
folders, changed markup, duplicate dossiers, missing callbacks and response/traversal
limits raise errors before replacing the output. A full snapshot refresh implements
updates; it makes no unsupported incremental-date assumptions.

## Validation and local evidence

Runtime: /home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python

- `-m unittest municipio.test_llanca -v`: five parser/adapter tests cover document
  grouping, provenance, stable IDs, null date/coordinate semantics, non-record and
  pagination rejection, complete mocked traversal, empty folders, count mismatch
  with preservation of the previous snapshot, manifest loading and disabled licences.
- Real `LlancaAyuntamientoAdapter.backfill_proyectos`: 14 records, 36 document links,
  21 inventory pages, three explicitly reported empty folders.
- `evidence/proyectos.jsonl`: actual live records, not fixtures.
- `evidence/validation.json`: live counts, source URLs, limitations and test results.
- `evidence/captures/`: each fetched live inventory page, named by the first 16
  hex characters of SHA-256(source URL). Discovery pages and a document preview
  are also saved under evidence/. Evidence is local and ignored by Git.

Only the four requested source files are added. No shared code/dependencies,
credentials, databases, deployments or publishing operations are involved.
