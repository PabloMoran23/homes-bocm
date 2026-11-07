# Manlleu — INE 08112

Verified live on 2026-11-07. Code candidate accepted for a deliberately narrow
current-POUM snapshot; **publication_ready: false** because no verified project
geometry is available. Scheduled ingestion is disabled. This is not full municipal
coverage and does not claim a granted-licence register.

## Official sources and results

- https://www.manlleu.cat/urbanisme/ — HTTP 200. Municipal index links to the
  current POUM, public SEGEX urban-management search and technical-project page.
- https://www.manlleu.cat/urbanisme/poum — HTTP 200; named current municipal
  planning instrument, explicit definitive approval 2023-01-18 and DOGC publication
  2023-06-27. These are parsed separately, not synthesized from crawl time.
- https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/277273 — direct
  official register dossier linked by the municipality. HTTP 200 returns the
  Angular application shell, not feature geometry. Its numeric identifier is
  recorded as `rpuc_id`, not invented as a municipal expediente number.
- https://tramits.manlleu.cat/segex/buscar_expedientes.aspx?sp=10809&tipo=PUBLICOS
  — HTTP 200 but the session resolves to an anonymous/login shell without public
  dossier rows. Not scraped as records; no authentication bypass attempted.
- https://www.seu-e.cat/ca/web/manlleu/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/projectes-tecnics-221
  — HTTP 200, explanatory text only in the response, not actual projects. Its
  2024-06-04 page-update timestamp is not treated as a project approval date.

## Extraction and quality

One live HTTP request to the specific POUM page, 30-second timeout, bounded
2 MB response. Requires the planning heading, explicit approval narrative and
one unambiguous official RPUC detail URL. Missing content, login markup and
multiple conflicting dossiers raise an error rather than emit fake records.
Stable identity comes from the actual RPUC URL. Update refreshes the complete
single-page current-plan snapshot. No licence forms, navigation links or general
service descriptions become project/licence records.

The municipal planning page provides no project coordinates or vector geometry.
The linked RPUC viewer requires further API/geometry investigation; no parcel,
sector or municipal centroid is substituted. `lat`, `lon`, and `geometry` remain
null; `geocode.jitter_missing` and `schedule.enabled` are false. Map/publication
parity remains incomplete, even though the real planning record is extractable.

## Validation

- `python3 -m unittest municipio.test_manlleu`: 4 tests passed (distinct date
  semantics, missing dates, rejection of login/navigation-only content, rejection
  of ambiguous dossier links).
- Direct `ManlleuAyuntamientoAdapter.backfill_proyectos` live extraction: status
  `ok`, 1 project, 0 fabricated coordinates, publication_ready false.
- Local evidence: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/manlleu/`
  contains `proyectos.jsonl` and `validation.json`.
- No database credentials, publish operations, pipeline `all`, PR or git mutation
  were used for extraction.
