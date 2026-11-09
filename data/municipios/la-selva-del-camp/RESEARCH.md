# La Selva del Camp — Tarragona — INE 43145

Verified anonymously on 2026-11-09. This adapter extracts the municipal planning
catalogue as a complete single-page snapshot. Municipal coverage is partial:
public-works notices, granted licences and the full regional register are outside
this adapter's scope. Scheduling and missing-coordinate jitter are disabled.
`publication_ready` is false: no verified project geometry was extracted.

## Official sources discovered

- Municipal website: https://laselvadelcamp.cat/ — HTTP 200; captured locally.
- Urbanism inventory: https://seu-e.cat/ca/web/laselvadelcamp/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme
  — HTTP 200. Links to planning, urban regulations, territorial plans, named
  public-information projects and environmental licence notices. This is the
  municipal transparency portal hosted by AOC, not a procurement aggregator.
  Environmental application notices are not evidence of granted licences.
- Extracted catalogue: https://seu-e.cat/ca/web/laselvadelcamp/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  — HTTP 200, full HTML contains 43 dossier links in catalogue list items.
  Extracted 41 municipal instruments; excluded the Camp de Tarragona territorial
  plan (RPUC 236793) and Catalonia waste-infrastructure territorial plan
  (RPUC 281501), since they are supramunicipal contextual references.
- Example linked official dossier:
  https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/221130
  — HTTP 200, redirects to
  https://planejamenturbanisme.territori.gencat.cat/rpucportal/index.html#/consulta/detallExpedient/221130
  and returns an Angular application shell. The municipality provides the dossier
  identity; the adapter retains this actual link without pretending to extract
  the register's underlying document inventory or geometry.
- Example general-plan drawing:
  https://seu-e.cat/documents/8571803/10874746/PLANOL-1+-+Situaci%C3%B3+i+empla%C3%A7ament.pdf/699433f2-046e-4e8b-93d6-61a5dd1f00bf
  — HTTP 200, application/pdf, 1,836,386 bytes, captured as `planol-1.pdf`.
  Other linked drawings are retained as source links; not all attachments were
  downloaded or independently checked for availability.

The older register-search link embedded in the introduction contains
`municipiSel=43145` and `pagingPage=2`. It is a link to a separate external
inventory, not a next page of this catalogue. We do not crawl that search or
claim complete RPUC coverage. No pagination controls were present in the
extracted catalogue. A new active next-page or pagination link causes an error;
it never silently produces a truncated success.

## Record semantics and grouping

The 41 records include the consolidated general planning text, modifications of
subsidiary rules, partial plans, special plans, a partial-plan modification and
the consolidated urban-boundary instrument. These are actual named planning
instruments with official dossier links, not navigation pages or licence forms.
All catalogue list entries are inspected; unknown entries or changed dossier
hosts cause failure. Regional plans are explicitly excluded.

Stable IDs use the linked RPUC numeric dossier identity. `rpuc_id` retains that
identity and `expediente_grupo` namespaces it as `RPUC <id>` for grouping. This is
not asserted to be the municipality's own expediente number. `categoria`
identifies the factual planning domain. No shared classification rules changed.
The title and description preserve each list item's complete source text,
including the specific location or purpose after generic anchor labels.

The seven general-plan drawings belong to the consolidated text's instrument
(RPUC 221130); that one record has eight provenance links, including the dossier.
Other instruments have their own dossier links. Repeated dossier anchors are
grouped by their actual register identity and document links are deduplicated.
Every retained document has the municipal catalogue as `source_url`.

The introductory narrative says the original norms were definitively approved
in 1998 but also says this inventory contains approved and provisional
modifications. That narrative does not establish individual current phases.
The consolidated-text label contains “19 de juliol 2005” without an explicit
event type. The catalogue footer says “Actualització: 28/02/2025”. Both labels
remain source evidence; neither is converted to an approval or publication date.
`fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` and `fase` stay null.
Coordinates and geometry stay null; no municipal centroid or jitter is used.

## Implementation and verification

Read `municipio/manifest.py`, `municipio/adapters/portal.py`, registry and the
Manlleu/Hernani examples first. Only the four requested source files were added;
no shared sources or dependencies were modified.

The live adapter requests the catalogue with HTTP error checking, connection and
read timeouts and a 5 MB streamed response limit. It validates the catalogue
heading, item links and general-plan drawings before atomically replacing the
output. Updates refresh the full snapshot, without a date cutoff. Empty/login
responses, unexpected inventory entries, missing sheets and active pagination
raise errors before replacing output. Disabled licence methods emit zero rows.

Executed using the preinstalled runtime:

```
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_la_selva_del_camp -v
```

Eight tests passed: grouping and provenance, no inferred dates/geometry,
deduplication, missing-content failure, pagination rejection, unknown-content
failure, snapshot-update/disabled-licence behavior, and manifest/registry wiring.
Live extraction used `load_portal_adapter(load_manifest('la-selva-del-camp'))`
and `backfill_proyectos`, exercising the shared entity annotation as well.
Result: 41 actual records, 43 catalogue dossier links minus two regional plans;
zero unknown entities after explicit RPUC grouping metadata.

Local uncommitted evidence under `evidence/` includes `proyectos.jsonl`,
`validation.json`, `proyectos.entities.json`, full `planejament-live.html`,
discovery captures `urbanisme.html` and `planejament.html`, the RPUC application
shell and the example PDF. Validation records retrieval time, source hash,
source URLs, live count, parser-test result and coverage limitations. No
credentials, other workspaces, database, deployment or publishing tools were used.
