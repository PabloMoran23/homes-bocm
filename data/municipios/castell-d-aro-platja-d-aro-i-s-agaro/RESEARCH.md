# Castell d'Aro, Platja d'Aro i s'Agaró — Girona — INE 17048

Verified live on 2026-11-07 with the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Official source discovery and selected coverage

The official [planning inventory](https://ciutada.platjadaro.com/seu_electronica/informacio-urbanistica/planejament-urbanistic/)
identifies instruments in force and in progress. The adapter extracts the **entire
current “En tràmit” list**, not the separately linked in-force collections. On the
verification date this was seven real instruments, each with a municipal detail
page, dated agreement stages and linked project/certificate/public-notice documents.
The repeated in-progress lists on other category pages are not additional projects.

Other official inventories inspected (HTTP 200, captures under `evidence/`):

- [POUM](https://ciutada.platjadaro.com/seu_electronica/informacio-urbanistica/poum/):
  in-force POUM link and the same in-progress list. The actual
  [POUM detail](https://ciutada.platjadaro.com/seu_electronica/informacio-urbanistica/planejament-urbanistic/poum/)
  links the regional planning register and describes 2017 definitive agreements
  and a separate DOGC publication. Outside this adapter's in-progress scope.
- [Modifications in force](https://ciutada.platjadaro.com/seu_electronica/informacio-urbanistica/modificacions-del-poum/)
  and [derived planning](https://ciutada.platjadaro.com/seu_electronica/informacio-urbanistica/planejament-derivat/):
  separate inventories of actual instruments; deliberately outside selected scope.
- [Other planning](https://ciutada.platjadaro.com/seu_electronica/informacio-urbanistica/planejament_urbanistic_altres/):
  accessibility plan and SUD-3 material; outside selected scope.
- [Licences](https://ciutada.platjadaro.com/seu_electronica/informacio-urbanistica/llicencies-urbanistiques/):
  heading “Llicències subjectes a informació pública” but no visible records in
  the fetched main content. This is not a verified register of granted licences.
  Licence extraction remains disabled; no application form is treated as a grant.

## Live extracted instruments

| Instrument | Latest explicit agreement stage | Agreement date | Document links |
| --- | --- | --- | --- |
| MPPOUM 15, Zona Industrial Avinguda Castell D'Aro | Provisional | 2026-06-29 | 6 |
| MPPOUM 17, Caleta Palace | Initial | 2025-02-24 | 6 |
| MPPOUM 16, Carrer Miramar | Provisional | 2026-02-23 | 3 |
| MPPOUM 18, Ampliació depuradora (EDAR) | Provisional | 2026-10-26 | 7 |
| Pla Especial Urbanístic Mas Maig | Provisional | 2026-09-21 | 5 |
| MPPOUM 24, Roquissar | Initial | 2026-07-27 | 6 |
| MPPOUM 21, Av. Politur | Initial | 2026-09-21 | 5 |

All eight source URLs (index plus seven detail pages) are recorded in
`evidence/validation.json`. `evidence/proyectos.jsonl` contains the seven records
and 38 linked documents. Fresh HTML fetched by the adapter is saved as
`evidence/live/<sha256(source_url)>.html`. Earlier discovery captures are also
local evidence. Evidence is not a source file to commit.

## Semantics and extraction behavior

Identity is a deterministic hash of the real detail URL. The parser requires a
planning card and matching municipal planning detail title/status. It emits one
record per instrument, retains all explicitly dated agreement stages in `hitos`,
and all document references with their municipal label, stage and source-page URL.
Recognized attachments are municipal uploads and municipal BPM `OAC/download`
or `download4j/download` links. Documents are linked, not parsed; their availability
and contents are not certified by this extraction.

`fecha_acuerdo` and `fecha_aprob` mean the most recent **explicit agreement stage**,
not definitive approval unless that is the actual stage. Generic `fecha` and
`fecha_publicacion` remain null. Multiple bulletin publication dates are retained
in source descriptions/document labels without choosing one as the instrument's
publication date. For example MPPOUM 15's provisional agreement is 29 June 2026,
while the linked certificate's label refers to 30 June; the upload directory even
contains 2024. Neither filename nor upload path determines the agreement date.

The reviewed inventory has no pagination or load-more control and all seven cards
are processed. The parser rejects detected pagination/load-more controls, empty
inventories, unknown instrument types, mismatched detail pages, malformed milestone
dates and missing documents. It never caps the result count. Each HTTP response
has a timeout and a size bound that raises on overflow. The complete output is
replaced only after every source has fetched and parsed successfully. Updates
refresh the full current snapshot; removed notices are not a historical archive.

Coverage is partial municipal planning coverage, not all municipal projects or
physical works and not an archive of licences. No project geometry has been
verified; latitude, longitude and geometry stay null. `publication_ready=false`,
`schedule.enabled=false`, `geocode.jitter_missing=false`, `licencias.enabled=false`.
The shared entity-policy annotation reports seven unknown entities; no owner or
housing classification is inferred from plan titles.

## Validation

- `.../venv/bin/python -m unittest municipio.test_castell_d_aro_platja_d_aro_i_s_agaro -v`:
  six tests passed: inventory scope/deduplication, grouped documents and distinct
  date semantics, pagination and invalid-page rejection, invalid details, atomic
  snapshot behavior and disabled licences, manifest identity.
- Live extraction through `load_manifest` and `load_portal_adapter`, calling only
  `backfill_proyectos(Path('evidence/proyectos.jsonl'))`: seven records, 38
  document links, eight captured source pages; status `ok`.
- No shared files, dependencies, credentials, database, deployment or git metadata
  were changed. No publish, pipeline-all, sync or post-merge command was run.
