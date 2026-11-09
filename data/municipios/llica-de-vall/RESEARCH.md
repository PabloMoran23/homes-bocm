# Lliçà de Vall — INE 08108, Barcelona, Catalunya

Verified 2026-11-09 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
The municipal domain spells the name `llissadevall.cat`; this is Lliçà de Vall,
not neighbouring Lliçà d'Amunt. The municipal pages identify the town hall at
Plaça de la Vila, 08185 Lliçà de Vall, Barcelona.

## Official inventories discovered

- https://www.llissadevall.cat/ajuntament-seu/informacio-oficial/urbanisme
  is the official Urbanisme document inventory. Live HTTP 200, six pages:
  the unparameterized page and `?pag=2` through `?pag=6`. These expose 45
  distinct article URLs: eight on each of pages 1–5, five on page 6.
  The adapter follows pagination links recursively, checks for page-number gaps,
  rejects repeated content and fails at its 100-page safety limit rather than
  silently emitting a partial inventory. Details and documents are extracted
  only from article content, excluding navigation, sharing links and footer.
- https://www.llissadevall.cat/ajuntament-seu/informacio-oficial/urbanisme/poum
  is a POUM revision/participation page (HTTP 200), with preliminary diagnosis,
  workshops and questionnaires. It does not establish a definitively approved
  new POUM and is not emitted as such. Captured locally as `evidence/poum.html`.
- https://www.llissadevall.cat/ambits/urbanisme-i-obres is a thematic page
  combining news and an official-document link, rather than the paginated
  official inventory. It was discovered via web search; the scraper uses the
  dedicated inventory instead of treating news as dossiers.
- https://seu-e.cat/ca/web/llicadevall/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme
  is the transparency navigation discovered via search. It is not used as a
  granted-licence dataset. No such register was verified in this work.

## Selected records and grouping

40 detail pages pass the explicit instrument/project title filter and have
municipal repository document links. They yield **39 records with 78 document
links**, after grouping the initial and definitive versions of the same water
sectorization/pressure-optimization project:

- https://www.llissadevall.cat/ajuntament-seu/informacio-oficial/urbanisme/projecte-sectoritzacio-xarxa-aigua-potable.html
- https://www.llissadevall.cat/ajuntament-seu/informacio-oficial/urbanisme/projecte-executiu-per-la-sectoritzacio-i-loptimitzacio-de-pressions-a-la-xarxa-dabastament-daigua-potable-de-llica-de-vall.html

Both link the corresponding initially/definitively diligenced
`PC_Millora_xarxa_aigua_Llicavall` document versions (83.4 MB each). All links,
page titles, narratives and event provenance remain in the grouped record.
The canonical URL, not the current sort position or title, supplies its stable ID.
All volumes/annexes attached to each remaining instrument stay together, e.g.
five volumes for El Pla urbanization and nine attachments for Tèxtil Torres.

Specific-action planning instruments (PAE) and executive construction projects
for Ca l'Estapé and Cavallerissa 2 are separate instruments even when they
concern the same physical intervention. The 2023 repair/urbanization and 2024
replacement/landscaping projects for the south wall of Can Coll are also retained
as separately named and approved projects. These are instrument counts, not
unique physical-site counts. The C-17 road project spans municipalities; no
whole-alignment containment within Lliçà de Vall is asserted.

Five inventory entries are intentionally excluded and listed in validation:
compensation-board statutes, the ORPIME procedural ordinance, forestry management
plan (outside selected urban-project scope), consolidated PGOM norms (a
compilation also linking the separately listed commercial-use plan), and
preliminary POUM revision studies without project attachments. No licence forms,
procurement announcements or unrelated news become projects or granted licences.

## Date and provenance semantics

Descriptions and `eventos_fuente` preserve the municipal text. Simple explicit
initial/provisional/definitive event dates are parsed separately from phase.
`fecha_aprob` is populated only for an unambiguous simple definitive-approval
statement: 14 records in this snapshot. For example, the Les Llisses kitchen
project has initial approval 2026-04-29 and definitive approval 2026-07-13.
The article's 2026-07-14 update is only `actualizacion_pagina_texto`.

Blank definitive-approval labels do not establish approval. Certificate dates,
automatic finality following an earlier conditional agreement, conditional CTUB
approvals and complex multi-event narratives remain raw rather than selecting
an arbitrary date. The agreement to publish at DOGC on the PGOM-modification
page is not asserted to be the actual publication date. `fecha_publicacion` and
generic `fecha` remain null even where narrative publication references exist;
the source description retains them for later document-level verification.
There is no invented expediente number, approval date or geometry.

Documents are retained by absolute URL, source label and originating detail URL.
`source_entity_type: documento` describes the available identity: a municipal
project-document collection, not a verified administrative expediente number.
The shared policy classifies these as documents with `activity_eligible=false`;
the scraper does not bypass that policy or claim publication readiness.

## Extraction limits and verification

Coverage is the complete *selected subset* of the current public Urbanisme
inventory, not every municipal work, historical planning dossier or licence.
HTML requests use a 35-second timeout and a 4 MB size limit; attachment files
are linked, not downloaded or independently validated. Some advertised PDFs
exceed 900 MB. The extraction does not parse their contents or assert that every
attachment remains downloadable. No project coordinates or vector geometries
were extracted: `lat`, `lon`, `geometry` are null and `publication_ready=false`.
Scheduling, licence extraction and missing-coordinate jitter are disabled.
Update re-crawls the complete inventory rather than using publication cutoffs.
All rows are parsed before atomic replacement of output, preserving an existing
snapshot on fetch/parse errors. Concurrent edits during a crawl remain possible.

- `python -m unittest municipio.test_llica_de_vall -v`: eight tests passed.
  Covers manifest loading, phase/date separation, certificates, missing dates,
  attached-document grouping, source changes, exclusions, pagination traversal,
  repeated-page failure and preservation of previous output on failure.
- Live extraction through `load_portal_adapter(load_manifest('llica-de-vall'))`
  and `backfill_proyectos`: 39 records, six inventory pages, 78 document links,
  14 simple definitive-approval dates, zero coordinates. Shared policy applied.
- Local evidence: `evidence/proyectos.jsonl`, `evidence/validation.json`,
  `evidence/proyectos.entities.json`, and `evidence/live-captures/`. Validation
  maps every crawled URL to its SHA-256-named HTML capture and lists excluded
  entries and limitations. Discovery captures are also retained under evidence.
  Evidence is ignored by git and is not part of the four source files.
