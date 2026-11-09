# Santa Margarida i els Monjos — INE 08251, Barcelona

Verified live 2026-11-08 with the preinstalled Python 3.12 virtual environment.
Exactly one adapter, with deliberately partial coverage: the POUM dossier explicitly
linked by the municipal electronic office. One instrument is emitted, with 30
public documents grouped beneath it. This is not a complete planning inventory,
works inventory or granted-licence register. No legal-validity claim is made.

## Official discovery

- https://www.santamargaridaielsmonjos.cat/ — HTTP 200. Current municipal homepage
  links Urbanisme to the municipal transparency office. Its news reports a website
  migration on 2026-10-22.
- https://www.santamargaridaielsmonjos.cat/pgou — direct live HTTP 404, although
  search/browser cached content still exposes the old PGOU index. Not used by the
  adapter. Its historical PDF at
  https://pgou.smmonjos.cat/fitxers/Llistat%20planejament%20RPUC.pdf remains HTTP 200;
  all three pages were inspected. It is a 2009 printout, includes a Vilafranca del
  Penedès record, and is unsuitable as a current municipal inventory. Not ingested.
- https://seu-e.cat/ca/web/santamargaridaielsmonjos/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  — HTTP 200. Current inventory entry points link RPUC with municipiSel=08251 and
  MUC with municipi=08251. The legacy RPUC search redirects to an Angular shell.
  Search pagination and municipal-wide enumeration are outside this adapter's
  explicitly limited scope; no first search page is presented as a full inventory.
- https://seu-e.cat/ca/web/santamargaridaielsmonjos/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/normativa-d-urbanisme
  — HTTP 200. Explicitly identifies the municipal POUM and links the RPUC dossier
  codintExp=251954. This is the live discovery source, parsed on every refresh.
  Its page-update date 26/01/2017 is not an instrument date.

## Extraction and provenance

The RPUC public application's JavaScript reveals its anonymous GET API. No account,
credentials or authentication bypass is used. The adapter follows the municipal
link's identifier and queries these current official resources:

- https://planejamenturbanisme.territori.gencat.cat/RPUC-portal/rest/consulta/detall?codiExpedient=251954&idioma=ca&cercaPublic=false
- https://planejamenturbanisme.territori.gencat.cat/RPUC-portal/rest/consulta/arbre?codiExpedient=251954&idioma=ca&cercaPublic=false

Both return HTTP 200 JSON. The detail verifies the exact municipality, instrument
class and dossier ID, and provides expediente `2010 / 040956 / B`.
`dataAprovacio=2018-05-08` becomes `fecha_aprob`; `dataPublicacio=2018-06-26`
becomes `fecha_publicacion`. No agreement date, generic date or phase is inferred.
The instrument has older agreements and judicial resolutions: these are retained
as attachments, without interpreting their legal effects. `vigencia` is null in
the source and remains null. Related dossier metadata is retained without
asserting these are separately extracted projects.

The entire returned public document tree is traversed recursively, including
nested agreements and judicial resolutions. Stable document IDs are deduplicated,
category paths and source flags are retained, and each document links to the
application's official `documents?documentId=...&downloadType=inline&idioma=ca`
endpoint. All 30 documents belong to a single stable POUM record, not 30 projects.
The detail response also lists historical/administrative document metadata; this
adapter intentionally uses the public `arbre` tree, not every historical
`assentament` version. No search pagination is used or silently truncated. Unexpected
identity, absent municipal narrative, ambiguous links, absent documents, HTTP
failure or oversized responses fail before replacing output. Updates refresh the
complete scoped snapshot. Requests have a 40-second timeout and a 5 MB size limit.

No coordinates or geometry are extracted. No centroid or jitter is substituted.
`publication_ready=false`, `schedule.enabled=false`, `geocode.jitter_missing=false`
and `licencias.enabled=false`. Forms, procurement announcements and news are not
converted into licences or planning records.

## Validation and local evidence

- `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_santa_margarida_i_els_monjos -v`
  — six tests pass: identity/date semantics, nested documents, deduplication,
  absent dates, invalid/ambiguous sources, complete refresh and disabled licences.
- Live `backfill_proyectos` loaded through the manifest and adapter registry:
  **1 record, 30 document links**, shared entity policy status `ok`, unknown 0.
- The 2018 CTUB agreement link (document 335066) was fetched independently:
  HTTP 200 with a genuine PDF response; capture retained locally.
- `evidence/proyectos.jsonl`, `evidence/validation.json`, municipal HTML, both JSON
  responses and the agreement PDF provide reproducible live evidence. Discovery
  captures also record the old source limitations. Evidence is local, not source.

No shared source files, dependencies, credentials, databases or deployment tools
were changed or used. Publication remains disabled pending independent review.
