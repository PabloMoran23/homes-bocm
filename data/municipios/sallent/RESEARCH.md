# Sallent — INE 08191, Barcelona

Verified on 2026-11-09 using the preinstalled batch virtualenv Python. The
adapter extracts a complete snapshot of the **supported subset** of the public
municipal Urbanisme / Actuacions inventory. This is partial municipal coverage,
not an exhaustive historical project registry or a register of granted licences.
Scheduling, licence ingestion and coordinate jitter are disabled.

## Official source discovery

- https://www.sallent.cat/temes/207-urbanisme — HTTP 200. Its `Actuacions`
  block links to individual planning instruments, technical works projects,
  policy plans, maps and an ordinance consultation. The adapter reads only this
  block, excluding news and navigation. No pagination was present. Future
  pagination causes a failure, rather than silently dropping pages.
- https://www.sallent.cat/tinformem/plans-campanyes-i-programes — HTTP 200.
  General municipal document inventory, with repeated title groups and blank
  continuation cells. Useful for discovering and cross-checking documents;
  not used as a row-per-document project source. Some groups are duplicated.
- Detail pages linked from Urbanisme are the extraction units. Only titles
  starting with Projecte, the physical repair Memòria Valorada, POUM, numbered
  Modificació Puntual, Modificació Puntual, Document de l'avanç de la Modificació
  Puntual or Pla Especial are supported. The published inventory currently yields
  28 records (20 planning instruments and 8 works/specific-action projects).
- https://www.sallent.cat/projecte-denderroc-duna-finca-entre-mitgeres
  links to the real technical demolition project at Carrer Sant Esteve 30.
  Its PDF was fetched (HTTP 200, 4,848,887 bytes) and its first three pages checked
  with pdftotext. It contains technical project sections, not a tender notice or
  evidence of a granted licence. No approval is inferred from it.

Excluded: licence application procedures, procurement announcements, unrelated
news, ordinance consultation, PAES policy programme, accessibility plan, acoustic
map and forest-fire delimitation map. No verified inventory of granted licences
was found in the reviewed sources. This does not assert that none exists.

## Grouping, provenance and semantics

Each supported detail URL supplies a stable hashed ID. All document links in
its attachment/link sections and relevant narrative links are retained in
`documentos`, with source page, label and document/register type. Repeated links
are deduplicated, including the site's doubled repository path slash. Related
instruments under `Et pot interessar` are excluded from that record's documents.
The inventory URL and detail URL are both retained. Missing titles, mismatched
pages, empty inventories or missing supporting documentation raise an error
before replacing the output. Updates refresh the whole snapshot, including
undated instruments; no date-based cursor loses those records.

RPUC URLs are provenance, not project IDs. The municipality publishes the same
RPUC reference for modifications 3.1 and 3.2, despite distinct descriptions and
approval dates. Modifications 11 and 16 also share a published reference. The
adapter preserves those references without correcting them or merging the
separate municipal instruments. Legacy RPUC links may redirect or become stale;
linked dossier/PDF contents are not systematically downloaded or parsed.

Dates are parsed only from explicit narrative event wording, with calendar
validation. `fecha_acuerdo` and `fecha_aprob` contain the stated approval meeting
or approval date, and `fecha_publicacion` the stated publication date. Generic
`fecha` remains null. For example:

- POUM: approval 2010-05-19; DOGC publication 2010-07-16.
- Modification 16: approval 2024-02-06; DOGC publication 2024-03-20.
  The subsequent graphical correction meeting stays in the description and does
  not replace the instrument's approval date.
- Modification 14: publication of the initial approval 2023-03-07;
  no agreement date inferred from that publication.
- Masies plan: a stated effective date is not converted to an approval date.
- Undated works retain null dates. Page update times are preserved verbatim as
  `source_updated_at_text`, never treated as publication or approval dates.

Phase reflects the explicitly described planning stage; type does not become
phase. An inventory page remaining online does not establish that an old
initial stage is still legally current. Descriptions retain this context.
No parcel, municipal centroid or invented coordinate is supplied. `lat`, `lon`
and `geometry` are null, and `publication_ready` is false throughout.

## Validation and local evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_sallent -v`: six tests passed. Tests cover inventory
  scoping/deduplication, pagination rejection, document grouping, separate event
  dates, invalid/missing dates, rejection of changed pages, stable identity,
  complete snapshot updates, disabled licences, output preservation on failure,
  and manifest municipality/safety settings.
- Real `SallentAyuntamientoAdapter.backfill_proyectos` extraction: 28 actual
  records. All records have documentary links and the exact municipality code.
- `evidence/proyectos.jsonl`: live records.
- `evidence/validation.json`: count, fetched source URLs, limitations, parser
  test result and sample-document check.
- `evidence/live_sources/`: raw HTML captured by the live adapter, named by
  SHA-256 of each source URL. Discovery captures also remain under `evidence/`.
- `evidence/demolition-source.pdf` and `evidence/demolition-first-pages.txt`:
  sampled physical-project evidence. Evidence is local and uncommitted.

No shared source files, dependencies, credentials, external write operations,
publishing, deployment or database access are required or used.
