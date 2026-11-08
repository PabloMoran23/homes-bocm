# Alcanar — INE 43004, Tarragona, Catalunya

Verified live on 2026-11-07 using the preinstalled Python 3.12 virtual environment.
This adapter extracts a deliberately partial **current public notice board**
snapshot: three actual planning instruments, not granted licences. Scheduling is
disabled and `publication_ready` is false because project geometry is unavailable.

## Official inventories investigated

- https://alcanar.eadministracio.cat/info.0 — HTTP 200. Municipal electronic
  headquarters links to its public notice board and previews of published acts.
- https://alcanar.eadministracio.cat/board — HTTP 200. The actual inventory used.
  Six explicit columns: Document, Expedient, Procediment, Categoria, Descripció,
  Data de Publicació. Anonymous Wicket pagination exposes ten rows per request,
  ending with two rows and an explicitly hidden more-results container. The live
  extraction traversed **10 pages / 92 notices**, selecting three planning acts.
- https://seu-e.cat/ca/web/alcanar/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  — HTTP 200. Provides RPUC/MUC links filtered to municipality 43004, rather than
  local project rows. The linked RPUC search
  https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=43004
  redirects to the Generalitat's `planejamenturbanisme.territori.gencat.cat`
  application shell (HTTP 200). This adapter does not claim extraction of that
  register or its full historical planning inventory.
- https://seu-e.cat/ca/web/alcanar/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/normativa-d-urbanisme
  — HTTP 200. Two older normative entries, dated 2016 and 2015, with document
  links; includes a regional agricultural-construction plan affecting many towns.
  Not combined with the current-board inventory or represented as new local works.
- https://www.alcanar.cat/urbanisme-i-brigada-municipal — indexed by search, but
  direct live HTTP returned **404**. Not used as a project source. Search snippets
  were treated only as discovery leads.

## Actual instruments and documentary provenance

| Expedient | Instrument | Published on board | Notice phase |
| --- | --- | --- | --- |
| 1011/2026 | PGOU modification, urban keys 17 and 19 | 2026-11-03 | provisional approval |
| 1584/2018 | Special urban plan for expansion of Reverter Indústries | 2026-11-03 | provisional approval |
| 4353/2024 | PGOU modification for Biblioteca Trinitari Fabregat / adjoining garden | 2026-10-29 | initial approval |

Each row links to an actual official document preview, respectively:

- https://alcanar.eadministracio.cat/preview-document/542ca4ff-4f32-45ea-80fe-5eae49e7d24c
  — CSV `7KK9H6TZG7SLJL75NC5FLCEH7`.
- https://alcanar.eadministracio.cat/preview-document/a555b8e2-7611-452d-b6ff-1681aab0cbbc
  — CSV `9S52HJLWAFKPMEXQ537FZFW25`.
- https://alcanar.eadministracio.cat/preview-document/bf327abe-b34b-44f3-9f99-0ce2608175e7
  — CSV `9WEP7NR3WKRHC49L4Q5YJCJ9S`.

The adapter fetches all three previews and embedded PDFs, checks the PDF magic
bytes, and retains document titles, stable preview links, observed viewer URLs,
CSV identifiers, original creation timestamps and SHA-256 hashes. Observed PDF
viewer URLs may expire; the stable preview is the document's canonical reference.
The source column `Descripció` is preserved as `descripcion`.

PDFs were also inspected locally using the existing `pdftotext` executable during
research. Both provisional notices explicitly refer to the plenary agreement of
2026-10-29, whereas their signature/publication is 2026-11-03. The library notice
is a correction republished on 2026-10-29 and refers to an initial agreement of
**2025-02-27**, not 2026-10-29. It concerns planning keys; it is not an assertion
that library construction was awarded or completed. The adapter does not parse
PDF body dates, so `fecha_acuerdo` and `fecha_aprob` remain null. The board's
publication date goes only in `fecha_publicacion`; generic `fecha` stays null.
Document creation timestamps are kept under their explicitly named original
field and never substituted for agreement dates. `fase` describes the latest
published notice in the group, without asserting the instrument's current legal
status outside the board.

## Coverage, pagination and failure behavior

Only `Planejament General` and `Aprovació de Pla Especial Urbanístic` procedures
with a named plan act are supported. Licence forms, procurement announcements,
elections, tax measures, staffing and meeting convocations do not become projects.
This is not a full public-works, historical planning or granted-licence inventory.
There is no time-window cutoff or silent first-page limit.

An anonymous HTTP session follows the server-provided Wicket next actions,
extracting XML component content without executing website JavaScript. Missing
tables, changed controls, absent pagination state, repeated notice identities,
invalid dates/references, missing document provenance, non-PDF attachments, HTTP
errors, responses over 10 MB or exhaustion of the 100-page safety bound raise
errors. The output is replaced only after the entire inventory and every selected
document have been fetched successfully. Updates perform the same full active
snapshot; withdrawn notices are outside its coverage.

Identity is the actual municipal expediente, so notices and corrections belonging
to one instrument are grouped and all distinct document links are retained.
Currently each of the three instruments has one visible document. Navigation
links, CSVs and PDF hashes are not invented expediente numbers.

No source supplies verified project coordinates or vector geometry here. `lat`,
`lon` and `geometry` remain null; no centroid, cadastral inference or random point
is substituted. `geocode.jitter_missing=false`, `licencias.enabled=false` and
`schedule.enabled=false` are explicit in the manifest.

## Reproduction and local evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_alcanar -v`: eight offline tests passed, covering
  date semantics, document grouping across pagination, exclusions, special plans,
  malformed sources, changed pagination, official-host checks and manifest identity.
- Live run loaded `load_manifest('alcanar')` and `load_portal_adapter`, set
  `portal.config['capture_dir']` to the local evidence directory and called
  `backfill_proyectos(Path('evidence/proyectos.jsonl'))`. It returned 3 records,
  92 inventory rows, 10 pages and shared entity-policy status `ok` (3 eligible
  expediente records; zero unknowns).
- Local, uncommitted `evidence/proyectos.jsonl` contains the actual records;
  `evidence/validation.json` contains `live_records`, source URLs, limitations,
  UTC extraction time and test result. The evidence directory also contains all
  board pages, Wicket XML responses, the three previews/PDFs, and discovery
  captures/statuses. `pdftotext` is only a research tool, not an adapter dependency.

No shared modules or dependencies were changed. No database, credential,
deployment, publishing, PR or git-mutating operation was used.
