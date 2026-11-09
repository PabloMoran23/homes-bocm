# Maçanet de la Selva — INE 17103, Girona

Verified live on 2026-11-08 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Candidate ready for independent review; not accepted automatically.

## Official source discovery

- Municipal Urbanisme inventory entry point:
  https://www.massanetdelaselva.cat/gestio-del-territori/urbanisme
  HTTP 200. Provides service information, application forms, ETRAM and a link to
  the municipal transparency site. Applications are not granted licences.
- Municipal transparency planning page:
  https://www.seu-e.cat/ca/web/macanetdelaselva/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  HTTP 200. Explicitly links the municipality-filtered official RPUC inventory:
  https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=17103
  This redirects to the current Angular viewer at
  https://planejamenturbanisme.territori.gencat.cat/rpucportal/index.html#/consulta/cercaPublic?reqCode=cerca&municipiSel=17103
  The municipal page also links MUC, which was not used as a project/geometry source.
- Municipal transparency normativa page:
  https://seu-e.cat/ca/web/macanetdelaselva/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/normativa-d-urbanisme
  HTTP 200; repeats the RPUC/MUC links rather than providing its own dossiers.
- Probed transparency URLs ending in `urbanisme/projectes-tecnics` and
  `urbanisme/gestio-urbanistica` returned HTTP 404. These do not supply records.
- Current RPUC public API was discovered from the viewer's JavaScript bundle,
  captured locally. Anonymous GET endpoints, no authentication or credentials:
  `https://planejamenturbanisme.territori.gencat.cat/RPUC-portal/rest/consulta/`.

## Inventory scope and extraction

`basica?municipi=17103&idioma=ca&firstRecord=1&rpp=20` returns `totals=47`,
`infoFiltre=Maçanet de la Selva` and `llistat`. Despite its name, `firstRecord`
is a **one-based page number**, confirmed against the viewer's
`e.first/e.rows+1` calculation and live pages 1, 2 and 3 (20, 20 and 7 rows).
Using offsets 20 and 40 returns empty pages. Early discovery probes are retained
as evidence, not treated as successful pagination. The adapter traverses until
all 47 unique IDs are accounted for. Changed totals, repeated IDs, short/empty
pages before the total, missing municipality filter and the page safety limit
raise errors before replacing output. No silent truncation.

For each locally headed dossier it requests
`detall?codiExpedient=<id>&idioma=ca&cercaPublic=false`. The result must match
both the RPUC ID and municipality. Supported ranks are PG (general planning),
PD (derived planning) and TUC (consolidated urban-area delineation). Unknown
instrument ranks fail closed. The snapshot contains **39 instruments**:
PGOU revision and amendments, partial/special plans and the TUC delineation.

Seven entries headed by other municipalities are explicitly excluded, including
regional plans, a gas pipeline plan and regional renewable-energy criteria.
They may affect Maçanet but are outside this adapter's locally headed scope.
The urban agreement dossier 285432 is also excluded: a convention is not itself
a planning instrument or physical work. The extraction report and validation
list all excluded IDs and titles. No procurement announcements or general news
are emitted as projects. No public granted-licence inventory was verified.

Each RPUC dossier becomes one record with a stable RPUC-based ID, its actual
expediente reference and **all documents listed in detail.documents** grouped
under that record (1,108 links across 39 records). Documents sharing a name but
having different source IDs are retained. Related dossier links and relation
labels are preserved without speculative merging. The detail endpoint can list
historical/replaced documents and null status flags: these are retained as
source metadata, not asserted to be the sole current operative document set.
The record links the municipal provenance page, viewer and detail API.

`dataAprovacio` maps only to `fecha_aprob`; `dataPublicacio` maps only to
`fecha_publicacion`. Generic inventory `data` is unused. Registry-entry dates
remain within `asientos_registro`; they are not project approval/agreement dates.
`fecha`, `fecha_acuerdo` and `fase` remain null. An approval phase is not inferred
from an instrument name, register appearance or document filename. Example:
PGOU revision 36758 has approval 2002-05-28, publication 2002-07-18 and separate
registry entries beginning 2007-12-20.

## Limitations

This is a refreshed snapshot of the reviewed RPUC inventory, not comprehensive
coverage of all municipal works, licences, historical notices or registry events.
Updates refresh the same complete inventory. PDF contents and plan geometry are
not parsed. One linked PDF was downloaded successfully (HTTP 200,
`application/pdf`, valid PDF signature) as a provenance/link check; the remaining
document binaries were not downloaded or individually validated. No centroid,
address guess or invented coordinates is substituted: lat/lon/geometry are null,
`publication_ready=false`. Schedule, licences and geocode jitter are disabled.

## Validation and local evidence

- `python -m unittest municipio.test_macanet_de_la_selva -v`: **8 tests pass**.
  Covers date separation, missing dates, identity and schema rejection, document
  grouping, TUC/convention distinction, municipal filtering, full one-based
  pagination, duplicate/changing/incomplete inventory failures, atomic output
  preservation and manifest/adapter loading.
- Direct live `MacanetDeLaSelvaAyuntamientoAdapter.backfill_proyectos`:
  **39 records**, 47 inventory rows examined, no fabricated coordinates.
- `evidence/proyectos.jsonl`: actual extracted records.
- `evidence/validation.json`: live count, complete requested source URLs,
  explicit exclusions, limitations and sample-document check.
- `evidence/rpuc-basica-{1,2,3}.json` and `rpuc-detall-*.json`: live API captures;
  municipal HTML, viewer HTML/JS, discovery probes, test log, live extraction
  report and `sample-plan-document.pdf` are also retained locally.

Evidence is local and is not part of the four source files. No shared source or
dependency changes, database access, deployment, publishing or git mutations
were performed.
