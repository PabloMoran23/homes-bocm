# Polinyà — Barcelona — INE 08167

Verified 2026-11-08 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Official source discovery

- Current municipal inventory (HTTP 200):
  https://www.polinya.cat/ajuntament/1644-informacio-oficial/normativa/normativa-durbanisme
  This is linked from the municipal navigation, including
  https://www.polinya.cat/temes/urbanisme-i-llicencies .
  It identifies the PGOU and provides a working compilation, with a separate
  reference to RPUC for authoritative documents. It is a single-instrument page,
  without pagination. The two PDF anchors resolve to the same document.
- Actual linked document (HTTP 200, 45,721,855 bytes, PDF signature verified):
  https://www.polinya.cat/media/repository/documents_oficials/normativa_urbanistica/PGOU_Polinya_REFOS_gener_2022.pdf
  Captured locally; contents are not parsed. Text extraction from its first three
  pages returned no text. The record comes from the named municipal inventory,
  not OCR, guessed PDF contents or procurement metadata.
- Register reference provided by that inventory:
  https://dtes.gencat.cat/rpucportal/#/consulta/cerca
  This is a general search link, not a specific dossier identifier. It is retained
  as a register reference and does not become a separate project. No RPUC records
  or geometry are claimed as extracted.
- Transparency inventory:
  https://seu-e.cat/ca/web/polinya/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  Refers users to RPUC with municipality/comarca filters; it provides no individual
  instrument rows in the inspected page.
- Transparency urbanism regulations:
  https://seu-e.cat/ca/web/polinya/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/normativa-d-urbanisme
  Its old municipal link, https://www.polinya.cat/ajuntament/normativa/normativa-durbanisme/ ,
  returned 404. The adapter uses the current municipal navigation destination above.
- General municipal plans inventory:
  https://seu-e.cat/ca/web/polinya/govern-obert-i-transparencia/accio-de-govern-i-normativa/normativa-plans-i-programes/plans-i-programes-209
  Contains strategic/policy programmes across departments; not consumed as a
  physical-project inventory. Departmental licence application links are not
  evidence of granted licences. Procurement notices are excluded.

## Implemented scope and semantics

One genuine planning instrument, with its linked working compilation. This does
not claim an authoritative consolidated legal version, individual amendment
coverage, all planning history, a public-works register or granted licences.
Duplicate document anchors are grouped. Additional PGOU package PDFs in the same
content area are retained in `documentos`; unexpected PDF families fail extraction
until their grouping is reviewed. The stable instrument ID survives PDF updates.

All approval, agreement and publication dates remain null. The page-update date
and the document filename's month/year are not assigned those meanings. No phase
is inferred from the instrument type or compilation. There are no coordinates,
geometry or substituted municipal centroids; `publication_ready` is false.
Scheduling, licence ingestion and missing-coordinate jitter are disabled.

The adapter fetches live HTML with HTTP checks, a timeout and a 4 MB response
limit. It verifies the content heading, instrument identity, working-document
provenance and official-register reference. Missing records, changed document
families or pagination raise errors before output is written. Updates refresh the
whole single-instrument snapshot; no date filter or pagination cap truncates it.

## Validation and local evidence

- `.../venv/bin/python -m unittest municipio.test_polinya -v`: 6 tests passed.
  Checks document grouping and stable identity, unknown date/geometry semantics,
  unrelated/login/form and foreign-document rejection, unexpected pagination,
  manifest/registry loading, disabled licences and snapshot update behavior.
- Live `load_portal_adapter(load_manifest('polinya')).backfill_proyectos(...)`:
  status `ok`, **1 actual record**. Shared entity-policy annotation reports
  `unknown` classification for that record; no stronger classification is claimed.
- Local `evidence/proyectos.jsonl`, `evidence/validation.json`,
  `evidence/normativa.html` and `evidence/pgou.pdf` contain the output, limitations,
  source URLs and captures. Validation includes SHA-256 capture hashes. Captured
  HTML and live output document lists were compared successfully.
- Evidence stays local. Only the manifest, this research note, municipality
  adapter and municipality tests are source additions. No dependencies or shared
  source files changed.
