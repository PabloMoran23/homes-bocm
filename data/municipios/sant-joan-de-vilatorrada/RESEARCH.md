# Sant Joan de Vilatorrada — Barcelona — INE 08218

Verified on 2026-11-07 using the preinstalled batch virtual environment.
This adapter extracts a **partial municipal planning inventory**, not granted
licences, procurement notices or a comprehensive register of current works.
Scheduling and missing-coordinate jitter are disabled. All rows have
`publication_ready: false` and null coordinates/geometry.

## Sources inspected

- Municipal council index: https://www.santjoanvilatorrada.cat/ca/ajuntament-nou
  (HTTP 200). Links to the dedicated POUM page used below.
- Extracted inventory: https://www.santjoanvilatorrada.cat/ca/ajuntament-nou/normativa-municipal/pla-dordenacio-urbanistica-municipal-poum
  (HTTP 200). Identifies the POUM approved definitively on 2003-06-11 and an
  ordered list of 29 amendments, special plans and polygon modifications.
  The latest dated entry in this inventory is 2021-01-27. It does not establish
  that this list includes every subsequent instrument or that every historical
  provision remains in force. All 29 entries are consumed, including four PA
  modifications without dates. The source is one page, with no pagination.
- Municipal transparency planning index:
  https://seu-e.cat/ca/web/santjoandevilatorrada/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  (HTTP 200). Links to RPUC with municipality selector `08218` and to MUC.
  This is a directory of sources, not itself a project record.
- RPUC link discovered there:
  https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=08218
  redirects to
  https://planejamenturbanisme.territori.gencat.cat/rpucportal/index.html#/consulta/cercaPublic?reqCode=cerca&municipiSel=08218
  (HTTP 200). Response is a JavaScript application shell with no dossier rows.
  No RPUC API inventory or geometry is claimed. The municipal page also links
  to the general RPUC search; that search URL is not an instrument identifier.
- Urbanism procedures:
  https://www.santjoanvilatorrada.cat/ca/seu-nova/prova-urbanisme/obres
  (HTTP 200). Contains licence applications and prior communications, not a
  register of issued licences. Excluded from records.
- Candidate transparency technical-project endpoint
  https://seu-e.cat/ca/web/santjoandevilatorrada/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/projectes-tecnics-221
  returned HTTP 404. It is a failed discovery attempt, not an inventory.

## Record and document semantics

30 instruments are emitted: the parent POUM and all 29 individually named
entries. This includes genuine planning instruments, not one record per PDF.
22 published document links are retained: 19 consolidated POUM norms, maps
and protected-assets catalogue documents belong to the POUM; three masies
norms/maps, individual sheets and environmental documents belong to the named
2018 masies special plan. Duplicate links are collapsed within the snapshot.
Other amendments have their municipal inventory narrative as provenance, without
invented document URLs or expediente numbers.

The municipality expressly says its download copies are offered for consultation
and have **no official legal character**, referring readers to RPUC for official
documents. Each document retains this caveat and the source page URL. The
adapter retains links; it does not download/interpret each PDF or verify its
currency. PDF maps are not interpreted as verified vector geometry.

26 rows have explicit approval dates; four remain null. `fecha_aprob` comes
from each individual narrative. `fase` says definitive approval only where the
entry explicitly says `definitivament`; other dated approvals retain the less
specific approval phase. The four undated entries have null phase. Page update
or crawl timestamps are never publication or agreement dates. `fecha`,
`fecha_publicacion` and `fecha_acuerdo` remain null. No coordinates, centroids,
parcel locations or geometries are inferred.

Identity hashes the normalized instrument title, excluding the approval clause,
so document ordering, inventory ordering and changed approval dates do not create
new identities. A title correction can change an identity; no official stable
municipal dossier IDs are exposed on this inventory page. Missing content,
unrecognized inventory entries, ambiguous/invalid dates, missing document groups,
duplicate identities, unexpected pagination and oversized responses fail visibly.
Updates re-fetch the entire unpaginated snapshot; no incremental cursor or
historical completeness is claimed.

## Validation and downstream limitation

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_sant_joan_de_vilatorrada -v`: four tests passed.
  Covers date/phase semantics, document grouping, stable identity, negative
  source and pagination cases, disabled licences, and manifest/registry resolution.
- Real extraction through `load_portal_adapter(load_manifest(...))` and
  `backfill_proyectos`: 30 live rows, 22 document links, 26 explicit approval dates.
- The unchanged shared entity classifier marks all 30 rows `pendiente` because
  this inventory supplies no official dossier identifiers; its report is
  `adapter_incident` / `unknown_entity_spike`. Those annotations are preserved
  in evidence. This scraper is reviewable code with real records, but does not
  establish downstream activity eligibility or publication readiness. No fake
  expediente numbers are added to bypass the classifier.
- Local evidence in `evidence/`: `proyectos.jsonl`, `validation.json`,
  `proyectos.entities.json`, original HTML captures and POUM response metadata
  with body SHA-256. Validation includes source URLs, HTTP results and limitations.
  Evidence is local and excluded from the four source deliverables.

No shared source, dependency, database, credential, deployment or git metadata
changes are required.
