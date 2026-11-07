# La Roda (Albacete) — INE 02069

Verified live on 2026-11-07 using the preinstalled batch Python runtime. This
adapter extracts a deliberately partial municipal inventory: one POM instrument
and two actual building projects. It does not claim complete municipal coverage,
a granted-licence register or verified current planning status. `schedule.enabled`,
`geocode.jitter_missing` and `licencias.enabled` are false.

## Official source discovery

- https://laroda.es/urbanismo/ — municipal urbanism landing page, HTTP 200 with a
  browser-compatible user agent. Links to planning, urban regulations and the
  PAI. The first request with the default requests user agent returned HTTP 403;
  no authentication or credentials were used. Its news cards are not an inventory
  of licences and are not emitted as records.
- https://laroda.es/urbanismo/plan-de-ordenacion-municipal/ — HTTP 200. The live
  municipal document inventory exposes informative/justificatory memoranda,
  information and planning maps, urban rules and catalogues. All **53 distinct
  PDF URLs** are grouped into **one POM record**. The same memoria URL is also
  labelled `PORTADA TOMO I`; both source labels are retained, without inventing
  another document or instrument. Raw municipal HTTP document links are preserved.
- https://laroda.es/urbanismo/plan-de-actuacion-integrado-de-la-roda/ — HTTP 200.
  Named building sections publish genuine `Proyecto básico y de ejecución`
  documents. **Centro Sociocultural «La Báscula»** has one project PDF and a
  related procurement link. **Centro Joven y Deportivo** has written and graphic
  PDFs, grouped into one project. The procurement link is retained as context,
  never treated as a granted licence or a separate project. General PAI funding
  resolutions and its strategic document do not create additional works records.
- https://laroda.es/urbanismo/normativa-urbanistica/ — HTTP 200. Provides the
  historical subsidiary rules, a modifications subinventory and a POM link labelled
  `en tramitación`. This source was inspected and captured for discovery, but is
  outside the extraction scope. Its explicitly labelled historical approval and
  publication dates belong to the subsidiary rules, not to the POM or buildings.
- The linked modifications inventory is
  https://laroda.es/urbanismo/normativa-urbanistica/modificaciones-normas-subsidiarias-de-planeamiento-de-la-roda/ .
  It is not traversed by this adapter. No completeness claim extends to these
  rules/modifications, other municipal works, news, procurement or electronic-seat
  dossiers.

## Provenance, dates and geometry

Each record retains its municipal inventory URL and every extracted document's
source URL, title, aliases and original document URL. Stable identities come from
the POM page or the building title within the PAI page; replacing one document
version does not create a second building project.

The POM page contains an old consultation narrative saying it is in tramitación,
with a final appointment date of 26/03/2021 and an allegations deadline of
07/04/2021. These are consultation deadlines, not publication, agreement or
approval dates. The narrative is retained as `estado_fuente` with an explicit
warning that its current status is unverified; `fase` stays null. A page remaining
publicly accessible does not establish that the instrument is approved or current.

The building document labels establish the existence of technical projects, not
the award, approval or execution of works. Upload-path months, a funding-resolution
date in a filename and the crawl date are not used as project dates. `fecha`,
`fecha_publicacion`, `fecha_acuerdo` and `fecha_aprob` are null for all three
records. No PDF contents are parsed to assert further facts.

No verified coordinates or vector geometry were extracted. `lat`, `lon` and
`geometry` stay null and `publication_ready` is false. No centroid, address
geocoding or jitter is substituted.

## Extraction and validation

The adapter downloads both complete static HTML inventories with HTTP checks,
40-second timeouts, host/content-type checks and a 2 MB response limit. It scans
all document links in article content, with no record count cutoff. Neither live
source exposes pagination. If pagination appears, extraction raises an explicit
error requiring traversal support instead of silently returning page one. Missing
article content, missing substantive POM documents or a building section without
its technical project fail validation. Both sources must parse successfully before
the output snapshot is written. Updates refresh the full scoped snapshot.

Commands run from the workspace:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_la_roda -v
```

Seven tests passed: grouping and document aliases; two buildings with procurement
excluded as a record; stable identity across document revisions; retaining more
than 150 documents; forms/menu/procurement-only rejection; pagination rejection;
full refresh and failure preserving existing output; manifest and disabled
licences (several assertions share a test).

A real `LaRodaAyuntamientoAdapter.backfill_proyectos` call with
`config={"evidence_dir": "<workspace>/evidence"}` wrote `evidence/proyectos.jsonl`:
**3 actual records, 56 distinct project/instrument document links** (53 + 1 + 2).
`evidence/validation.json` records live count, source URLs, UTC retrieval time,
limitations, document counts and sampled PDF checks. Raw adapter responses are
`evidence/live-pom.html` and `evidence/live-pai.html`; discovery captures and PDF
prefixes are also local evidence. Four sampled documents (the POM memoria and all
three building PDFs) returned HTTP 206, `application/pdf`, with `%PDF-` prefixes.
The POM sample was requested over HTTPS on the same host; its original HTTP link
remains in the record. This sampling does not validate every POM PDF or its text.

Evidence remains local and is not committed. Only the requested manifest,
research, adapter and parser-test source files are added. No shared code,
dependencies, credentials, database, deployment or publishing operations are used.
