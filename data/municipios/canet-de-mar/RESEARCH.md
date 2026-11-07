# Canet de Mar — INE 08040, Barcelona

Verified live on 2026-11-07 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Official inventories and chosen coverage

- Municipal Urbanisme directory: https://www.canetdemar.cat/regidoria.php?id=14
  (HTTP 200). Links planning and application procedures. The latter do not
  constitute granted licences and are excluded.
- Transparency planning directory:
  https://seu-e.cat/es/web/canetdemar/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  (HTTP 200). Refers users to the municipal planning section.
- Selected live inventory: https://www.canetdemar.cat/document.php?id=19781
  (HTTP 200, ISO-8859-1 HTML). Its “Normativa aplicable i enllaços de consulta”
  section contains four named instruments, each with its own DOGC edict:

| Instrument | DOGC publication cited by municipality | Official document |
| --- | --- | --- |
| Architectural/historic heritage special plan | 2007-09-25 | https://dogc.gencat.cat/ca/document-del-dogc/?documentId=395790 |
| Consolidated urban fabric delimitation (TUC) | 2011-02-14 | https://dogc.gencat.cat/ca/document-del-dogc/?documentId=572710 |
| Urban improvement plan for volumes of protected heritage elements | 2011-07-18 | https://dogc.gencat.cat/ca/document-del-dogc/?documentId=584694 |
| Farmhouses/rural houses catalogue special plan | 2013-05-21 | https://dogc.gencat.cat/ca/document-del-dogc/?documentId=636228 |

All four DOGC links returned HTTP 200 but identical generic application HTML,
not the edict contents. Records therefore explicitly derive from the municipal
inventory citations, not independently extracted DOGC text. The dates of the
edicts (2007-08-27, 2011-02-04, 2011-07-06 and 2013-05-13) are retained in
document titles, never used as agreement or approval dates.

## Current planning context and exclusions

The inventory explicitly reports annulment of the previous POUM. It also links
https://portaldogc.gencat.cat/utilsEADOP/PDF/9719/2164818.pdf
(HTTP 200; captured PDF and `pdftotext` output). That actual official PDF is
Acord GOV/199/2026 **of 2026-07-28**, **published 2026-07-30**, concerning
suspension of the general planning framework and urgent replacement rules.
These dates are context, not the approval dates of the four listed instruments.
The adapter preserves the municipal annulment/suspension narrative and links
on each record, sets `vigencia_verificada=false`, and leaves `fase` null. It
makes no legal determination about which provisions of each instrument apply.

The page also describes the municipal agreement of 2026-01-29 to start studies
for a new POUM and suspend certain permissions. Its linked notice is
https://tauler.seu-e.cat/detall?idEns=804030008&idEdicte=ANU20260202075828
(HTTP 200, JavaScript application shell only). This is not treated as an
approved new POUM or as granted licences. Its municipal narrative and links
remain in the planning context, but it does not produce another record.

A general RPUC dossier link is present:
https://planejamenturbanisme.territori.gencat.cat/rpucportal/#/consulta/fitxaExpedient/259589
It is not demonstrably tied to one of the four items. It is not assigned to the
last item by proximity, and this adapter does not claim full RPUC coverage.
Related news, procurement announcements, licence forms and the annulled older
POUM are not additional projects. Physical public works are outside this
adapter's deliberately partial planning-inventory coverage.

## Extraction contract

The parser reads the actual `#cos` body and named inventory section, groups
repeated instrument titles, and retains distinct linked DOGC documents within
each instrument. Identity derives from the instrument title, not individual
attachments. Publication provenance retains the exact municipal citation;
`fecha`, `fecha_acuerdo` and `fecha_aprob` stay null. The reviewed inventory is
one unpaginated page; no result limit or date cutoff is applied. Next-page links
cause failure rather than silent truncation. Empty content, missing documents,
unreviewed instrument types, invalid dates, unexpected host redirects and
oversize responses fail before replacing output. Update refreshes this complete
inventory snapshot. No geometry or municipal centroid is substituted.

`schedule.enabled=false`, `geocode.jitter_missing=false` and
`licencias.enabled=false`. `publication_ready=false` because geometry and
current legal validity remain unverified. The shared registry's entity policy
classifies all four records as unknown (no municipal expediente references
were supplied by this inventory); that annotation is preserved and no invented
expediente number is added to bypass it.

## Verification and local evidence

- `.../venv/bin/python -m unittest municipio.test_canet_de_mar -v`: **8 passed**.
  Tests cover grouping multiple documents, source encoding, date semantics,
  context/exclusions, pagination, malformed/empty sources, null dates and the
  manifest/registry/update contract.
- Live extraction through `load_manifest` / `load_portal_adapter` /
  `backfill_proyectos`: **4 genuine planning records**, four distinct IDs,
  four linked edicts, no invented approval dates or coordinates.
- Local, uncommitted evidence: `evidence/proyectos.jsonl`,
  `evidence/validation.json`, `evidence/planejament.html`, directory/DOGC/e-Tauler
  HTML captures, `evidence/acord.pdf`, `evidence/acord.txt` and
  `evidence/discovery.json` (request statuses and sizes).
- No shared source or dependencies changed. No deployment, publishing,
  credentials, databases, repository mutation or remote code-host tools used.
