# Celrà — INE 17049, Girona

Verified live on 2026-11-09 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
The adapter extracts the municipal **current-planning inventory**, not licences,
procurement notices or news. Live result: **27 instruments, 120 PDF links**.
Coverage is partial at municipal level; no verified geometry is available.
`schedule.enabled`, `geocode.jitter_missing` and `licencias.enabled` are false.

## Official inventories and provenance

- [Municipal documentation index](https://www.celra.cat/wp/ajuntament/documentacio/)
  (HTTP 200) links to the planning inventory under municipal regulations and
  separately lists council minutes, public information and transparency sections.
  These navigation entries and minutes are not emitted as project records.
- [Planejament urbanístic vigent](https://www.celra.cat/wp/ajuntament/documentacio/normativa-municipal/planejament-urbanistic/)
  (HTTP 200) is the extraction source. Its complete HTML contains the current PGOU
  revision, 20 numbered PGOU modifications, four special plans and two partial
  plans. The missing modification numbers are absent from this inventory; they
  are not synthesized. The most recent displayed approval is 2025-10-01 for the
  community-equipment special plan. No pagination is present in the captured page.
- [RPUC search](https://dtes.gencat.cat/rpucportal/#/consulta/cerca) is linked as a
  general search from the municipal inventory. It is not a dossier-specific link
  and is not used to infer additional records, identifiers or geometry. The
  adapter does not claim full regional-register coverage.
- The municipal community-equipment plan's linked PDF was independently checked
  with HEAD: HTTP 200, `application/pdf`, Content-Length 11474130. This verifies
  availability of one sample, not the contents or availability of all 120 PDFs.

## Extraction and semantics

One HTTP GET retrieves the entire planning page (40-second timeout, streaming
4 MB response limit). The parser requires its exact page heading, finds dated
instrument accordion headings and the two partial-plan list items, and groups
all linked PDFs under the corresponding instrument. Container accordions such
as “Modificacions” are not records. Stable IDs derive from instrument titles,
not approval dates or accordion IDs, which contain changing widget identifiers.
Duplicate identities, empty inventories, missing documents, changed approval
labels and detected pagination raise errors. There is no pagination cutoff.
Updates refresh the complete single-page snapshot; no date cursor is invented.
Output replaces the previous JSONL only after fetching and parsing succeed.

Each record retains the source heading, source URL, original approval-date text,
PDF titles/URLs and explicit approval narrative where available. `fecha_aprob`
comes only from the labelled approval date. Definitive approval is asserted only
where the instrument's own narrative explicitly says “Aprovació definitiva”.
Other records retain an unspecified approval stage. Publication, agreement and
generic dates stay null: neither page footer dates nor crawl time is an approval
or publication date.

Both Falgueres partial-plan headings say **18/09/20007**. The adapter preserves
that exact text, flags it and leaves the normalized date null; it does not assume
2007. The nucli antic panel includes a “Modificació puntual” PDF alongside its
base-plan documentation: it remains a related document under the municipality's
grouping, without inventing a separate approval date or applying the base plan's
2007 approval to that document. The extra “Altres documents” heritage-plan link
and road-inventory documents outside these instrument groups are excluded to
avoid duplicate or unverified instrument identities.

No PDF text, scanned maps or parcel geometry is parsed. PDF links are provenance,
not separate projects. No granted-licence inventory was verified; application
forms are excluded. No coordinates, municipal centroids or inferred geometry
are supplied. Records have null lat/lon/geometry and `publication_ready: false`.

## Reproducible checks and local evidence

- `python -m unittest municipio.test_celra -v`: six tests pass. They check grouped
  documents, independent date semantics, invalid source years, stable IDs,
  nested containers, rejection of forms/navigation-only content, missing
  documents, pagination, duplicate identities, manifest loading, snapshot update,
  preservation of output on parser failure and disabled licences.
- Live extraction used `CelraAyuntamientoAdapter.backfill_proyectos`, with
  `capture_dir` set to `evidence`; result `status: ok`, 27 unique records.
- Local-only `evidence/proyectos.jsonl` contains actual live records;
  `evidence/validation.json` records counts, source URLs, runtime, limitations and
  checks. `planejament.html` captures the actual extraction response;
  `documentacio.html` captures the discovery index; `document_check.json` records
  the sample PDF HEAD response. These are evidence, not source files to commit.
