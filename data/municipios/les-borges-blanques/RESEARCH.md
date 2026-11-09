# Les Borges Blanques — INE 25058, Lleida

Verified live on 2026-11-09 using the preinstalled Python 3.12 virtual environment.
This adapter covers the municipal **section 3.1 Normativa urbanística** inventory:
13 instruments with 19 associated source links (17 PDFs and two RPUC dossiers).
It is a partial municipal snapshot, not a complete works or granted-licence
register. Scheduling and coordinate jitter are disabled; publication_ready is
false because no verified project geometry is extracted.

## Official discovery and scope

- https://www.lesborgesblanques.cat/ajuntament/normativa_local — live HTTP 200;
  the municipal classification table identifies section 3.1 as urban planning,
  improvement plans and urban projects. All 13 linked instruments in that section
  are extracted, including the cemetery pedestrian/cycle route, Carrasco i
  Formiguera, President Tarradellas, Masia les Garrigues, Vila de Toluges, POUM,
  municipal theatre, Placeta 79, three-street reurbanisation, Magí Morera, PAU 03
  reparcellation modification, and POUM modification 1.
- https://lesborgesblanques.cat/ajuntament/mod_pla_ordenacio_poum — live HTTP 200;
  five linked PDFs (catalogue, report, executive document, rules, plans) form
  **one** initially approved POUM modification record, not five projects.
- https://lesborgesblanques.cat/magimorera — live HTTP 200; technical document,
  council agreement certificate and signed convention/annexes form one urban
  management instrument associated with the street extension.
- https://dtes.gencat.cat/rpucportal/#/consulta/fitxaExpedient/268728 and
  https://dtes.gencat.cat/rpucportal/#/consulta/fitxaExpedient/295365 — official
  register dossier references linked by the inventory, retained verbatim. Live
  requests return HTTP 200 HTML application shells, not PDFs or geometries.

Discovery also found the municipal information/news inventory at
https://lesborgesblanques.cat/ajuntament-informa and the separate “Normativa en
tràmit” section of the normativa page. Those are outside this adapter's explicit
section-3.1 scope. The latter includes additional plans (Tennis Borges, Castellots,
non-developable land and sustainable mobility); they are not silently represented
as covered. Fiscal rules, licence application procedures, procurement, general
news and strategic/social plans outside section 3.1 do not become records.

Initial direct access to the bare-host inventory with the default requests agent
returned 403; the actual adapter's canonical www HTTPS source and identifying
User-Agent returned 200. No authentication or credentials were used.

## Semantics, grouping and provenance

Records retain their exact source titles, source status, inventory URL, instrument
URL and document URLs, with a provenance URL on every document. Identity hashes
the actual instrument URL; repeated identical links deduplicate, conflicting
entries fail. The source's combined Masia les Garrigues PMU/urbanisation title is
retained as one instrument rather than split without evidence.

“Vigent” is retained only as estado_fuente, never inferred as definitive approval
or completed construction. Explicit “Aprovació inicial” gives an initial phase.
The PAU 03 title explicitly states definitive approval by JGL agreement on
18-9-2025, parsed into fecha_acuerdo and fecha_aprob as 2025-09-18.
fecha_publicacion and generic fecha remain null throughout: upload directories,
PDF filename dates, signature dates and page-update dates are not publication or
approval dates. No expediente number or location is invented.

All 19 document links were separately probed live: 17 returned HTTP 200 with PDF
magic bytes; both RPUC URLs returned HTTP 200 HTML. The captured reurbanisation
PDF is an actual edict approving a basic/execution street project initially on
9 March 2022, rather than a procurement advertisement. Its signature is dated
10 March 2022. These PDF-only dates are **not extracted** by this HTML adapter;
the corresponding record deliberately keeps unknown date/phase fields null.
The source's current “Vigent” label and the historical initial approval are not
collapsed into an invented definitive approval.

PDF bodies are linked, not generally parsed; RPUC dossier documents and vector
geometry are not expanded. There is no verified granted-licence register. All
coordinates and geometry remain null; no town centroid or random jitter is used.

## Extraction and validation

The adapter fetches three HTML pages, each with a 35-second timeout and a 3 MB
response bound. Selectors require the municipal article and section heading;
empty inventories, unknown item types, missing statuses, changed grouping,
missing attachment sets, unexpected hosts and pagination indicators fail rather
than produce an apparently complete result. The observed inventory has no
pagination. Future pagination requires extending the crawler. Updates refresh
the whole reviewed snapshot; no date filter or row cap truncates history.
Output is replaced atomically after all detail pages succeed.

Run with `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`:

- `-m unittest municipio.test_les_borges_blanques -v`: 9 tests passed. Covers
  source scope, date semantics, grouped attachments, identity, invalid sources,
  pagination rejection, manifest switches and adapter output.
- Direct adapter backfill with the loaded manifest: 13 live records, 19 links.
- `git diff --check`: passed. Only the four requested source files were added.

Local, uncommitted evidence lives under `evidence/`: `proyectos.jsonl`,
`validation.json`, HTML captures in `captures/`, `document_checks.json`, and
`reurbanitzacio_carrers.pdf` with its text extraction. The validation report lists
source URLs and coverage limitations. No shared source/dependency changes,
credentials, databases, deployment or publication operations were used.
