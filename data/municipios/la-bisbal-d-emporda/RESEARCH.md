# La Bisbal d'Empordà — INE 17022, Girona

Verified 2026-11-07 using the preinstalled Python 3.12 virtual environment.
This adapter covers the **complete current Obres locals inventory page**, not
the entire municipality's planning history. Scheduling and granted-licence
extraction are disabled. No coordinates are fabricated; publication_ready is false.

## Official source discovery

- https://www.labisbal.cat/serveis/urbanisme/obres-locals/ redirects to
  https://labisbal.cat/serveis/urbanisme/obres-locals/ and returns HTTP 200.
  The municipal content column is headed “Obres locals” and “En exposició
  pública”. The direct live response has 14 PDF links representing four projects:
  carrer Nou reurbanisation (two parts, budget, drawings, specifications),
  plaça del Call urbanisation (one document), carrer del Call urbanisation (one),
  and the accessibility project (seven parts labelled APROVACIO INICIAL).
  The web search rendering omitted the later documents; the adapter uses the
  direct live HTML, never the search result as its inventory.
- https://labisbal.cat/serveis/urbanisme/en-exposicio-publica/ is an additional
  municipal planning-document inventory. Live HTML captured for research;
  outside this adapter's deliberately limited works scope. Its licence-suspension
  drawings are not granted licences.
- https://www.labisbal.cat/serveis/urbanisme/aprovats-definitivament/ returns
  HTTP 200 with approved planning and SUD-08 documents. Captured but not ingested;
  reparcellation and urbanisation documents need separate instrument analysis.
- https://www.labisbal.cat/serveis/urbanisme/poum/ returns HTTP 200 with the POUM
  documents, graphic sheets, RPUC/DOGC links and amendments. Captured but not
  ingested by this public-works adapter.
- https://labisbal.cat/serveis/urbanisme/tramits-urbanisme/ contains application
  forms. These are not a granted-licence register and are excluded.

Some direct requests to the non-www entry returned 403 or disconnected during
research. The www entry with the adapter's User-Agent succeeded in discovery and
in the independent live backfill. HTTP failures propagate; there is no fallback
to fixtures, search results or previously captured HTML.

## Semantics, grouping and coverage

The content column is selected by its actual heading, excluding navigation and
footer links. All list links in that column must be recognized municipal PDF
project documents; an unexpected link fails extraction. Explicit PART, PRESSUPOST,
PLÀNOLS and PLEC DE CONDICIONS suffixes group component documents under one
project, preserving each original label, URL and inventory provenance. Carrer del
Call and plaça del Call stay separate. IDs hash the base project title and remain
stable when document order changes or another part is added.

The page labels these works as in public exposure; the accessibility document
labels additionally assert initial approval. Neither asserts completed execution
or final approval. PDF contents are not parsed or claimed to have been validated.
No publication, agreement or approval dates are available from the parsed labels:
all date fields remain null. Upload-directory months are not event dates.
No project geometry is extracted from PDF drawings, and neither municipal
centroids nor contact-address coordinates substitute for project locations.

This is a current single-page snapshot. No pagination was present in the captured
inventory. Next links, pagination widgets or infinite-scroll markers cause a
failure requiring review, rather than silently truncating. Update re-fetches the
whole snapshot. Empty/missing/login pages fail before replacing existing output.
Responses are bounded at 2 MB with connection/read timeouts. No shared source or
dependency modifications are required.

## Reproduction and local evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_la_bisbal_d_emporda` — four tests passed:
document grouping and distinct locations, initial-stage and stable identity,
rejection of forms/login/empty inventories, and pagination/untrusted-host failure.

Live `LaBisbalDEmpordaAyuntamientoAdapter.backfill_proyectos` completed with
**4 records and 14 document links**. Manifest loading was also verified.
The optional adapter config `evidence_dir` saved the actual fetched HTML.
Local uncommitted artifacts under `evidence/` are `proyectos.jsonl`,
`validation.json`, `obres-locals.html`, `poum.html`,
`aprovats-definitivament.html` and `en-exposicio-publica.html`.
Validation records source URLs, live count, timestamp and coverage limitations.
