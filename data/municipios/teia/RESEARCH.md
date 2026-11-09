# Teià — INE 08281, Barcelona

Verified live 2026-11-09 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Official inventories reviewed

- https://teia.cat/serveis/urbanisme — official municipal urbanism directory,
  HTTP 200. Links to the project inventory, NPU and derived planning pages.
- https://teia.cat/serveis/urbanisme/projectes-urbanistics — HTTP 200. The
  `projectTable` HTML table contains 20 rows, dated 2022-09-28 through 2026-05-02.
  All rows are present in the response. Its JavaScript search merely filters
  existing rows; no server pagination was observed. The adapter rejects pager
  markup or pagination URLs if introduced, rather than silently truncating.
- https://teia.cat/serveis/urbanisme/npu — HTTP 200. Separate historical NPU
  instrument with nine attachments. Text distinguishes the 2023-07-31 commission
  agreement, 2023-10-03 edict and 2023-10-09 DOGC publication. It also states a
  maximum three-year validity from publication. This page alone does not establish
  current validity in November 2026. Not included in this adapter's coverage.
- https://teia.cat/serveis/urbanisme/planejament-derivat — HTTP 200, four linked
  PMU documents (7, 11, 12, 14). Separate inventory, not extracted. PMU numbers
  overlap across contexts: no merging based on number alone or assertion that
  these historical documents are currently operative.

## Implemented coverage and semantics

Exactly one adapter extracts the complete current **Projectes urbanístics** table.
Live output: **19 records**, comprising 5 planning instruments and 14 physical
works projects. The rental-home allocation process is excluded because it is not
construction or a planning instrument. No application forms, procurement notices
or general news are extracted. Unknown future categories fail for review.

Examples include PAU 17 Les Basses, PAU-18 Can Bruguera, the Can Mònac special
plan, the POUM advance, Sant Berger street pavement repairs, Els Galamons nursery
extension, water network renewal, and El Cim photovoltaic installation. Their
presence in the municipal inventory establishes a real project, not its approval,
completion, municipal ownership, or current legal status.

`Data del Projecte` is stored as `fecha_proyecto_fuente` with its literal source
label. Its meaning is not assumed to be publication or agreement. Generic date,
publication, agreement and approval date fields are null. File modification dates
and crawl time are not project approval dates. Titles retain the municipality's
wording, including its PMU numbering; no external correction is inferred.

One normalized full project title identifies one instrument, with all its links
retained in `documentos`. Repeated entries retain their source dates separately;
conflicting dates yield a null single project date. Identity is a stable title
hash, not an invented expediente number. Folder links stay grouped with their
instrument and are labelled as folders, not individual downloaded documents.

## Document provenance and limits

The municipality links predominantly to `ajuntamentteia.sharepoint.com` public
sharing URLs. The first PAU 17 link was checked anonymously: HTTP 200 but an
**Error / El vínculo ha expirado** page, captured locally. Thus HTTP success does
not establish document access. Other SharePoint targets and folder contents have
not been verified or enumerated. The adapter preserves the exact published URLs
(trimmed of whitespace) and marks document contents unverified. It extracts the
municipal inventory itself without requiring SharePoint access.

https://teia.cat/documents/arees/urbanisme/ProjecteUrbanitzaciPAU-2CarrerELCastell.pdf
was fetched independently: HTTP 200, `application/pdf`, 44,131,313 bytes; saved
locally as `evidence/pau2.pdf`. No PDF-derived dates or coordinates are asserted.

Coverage is partial across the municipality: this is neither all planning nor a
licence register. No verified project geometry exists in the parsed table; lat,
lon and geometry remain null. No municipal centroid or jitter is substituted.
`publication_ready=false`, `schedule.enabled=false`, `geocode.jitter_missing=false`
and `licencias.enabled=false`.

## Validation and local evidence

- `.../venv/bin/python -m unittest municipio.test_teia`: **8 tests pass**. They
  cover date semantics, document grouping and conflicting dates, exclusions,
  unknown categories, pagination refusal, missing/malformed sources, folder
  provenance, manifest loading and update integration.
- Live invocation through `load_portal_adapter(load_manifest('teia'))` and
  `backfill_proyectos(Path('evidence/proyectos.jsonl'))`: 19 actual records.
- The existing registry's entity policy classifies all 19 as `pendiente` with
  `insufficient_identity_evidence`, producing `adapter_incident / unknown_entity_spike`.
  The inventory provides no recognized expediente identity; none is fabricated to
  bypass that policy. Records need further identity evidence before downstream
  activity eligibility. This is a working extraction candidate, not publication
  acceptance. Shared classification rules are unchanged.
- `evidence/validation.json` records count, source URLs, results and limitations;
  `inventory.html`, `urbanisme.html`, `npu.html`, `planejament-derivat.html`,
  `sharepoint-response.html`, `pau2.pdf`, `proyectos.jsonl` and its entity report
  are local evidence, not source additions for commit.

No dependencies, shared source files, git internals, external publishing systems
or credentials were changed or used.
