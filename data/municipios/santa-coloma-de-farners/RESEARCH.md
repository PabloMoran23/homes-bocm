# Santa Coloma de Farners — INE 17180, Girona

Verified anonymously on 2026-11-07 using the preinstalled batch Python runtime.
The implemented scope is the municipal planning inventory in the Generalitat's
RPUC, explicitly linked from the municipality's official transparency portal.
This is partial municipal coverage, not a granted-licence register or a complete
inventory of public works. Scheduling, licence extraction and coordinate jitter
are disabled. All records have `publication_ready: false`: no verified project
geometry was obtained.

## Official source discovery

- https://www.scf.cat/ — HTTP 200. Identifies the municipality, links its official
  transparency portal and labels https://farners.enmapa.com/visor/geoportal as
  “Urbanisme Geoportal Urbanístic”. The geoportal returns an application shell;
  no project geometry is inferred from that shell.
- https://seu-e.cat/ca/web/santacolomadefarners/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  — HTTP 200. Links RPUC with the exact municipality parameter `municipiSel=17180`,
  MUC with `municipi=17180`, and the older Nexus geoportal. Its 06/07/2021 update
  date is a page metadata timestamp, never an instrument approval date.
- https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=17180
  redirects to
  https://planejamenturbanisme.territori.gencat.cat/rpucportal/index.html#/consulta/cercaPublic?reqCode=cerca&municipiSel=17180
  — HTTP 200, Angular application. Its public JavaScript specifies the REST
  endpoints, municipality filter, pagination and document-download parameters.
- Live inventory:
  https://planejamenturbanisme.territori.gencat.cat/RPUC-portal/rest/consulta/basica?municipi=17180&idioma=ca&firstRecord=1&rpp=20&sortDirection=asc
  — HTTP 200 JSON; `totals=65`. Despite its name, `firstRecord` is a **one-based
  page number**, matching the site's `e.first/e.rows+1` transformation. Pages
  1, 2, 3, 4 return 20, 20, 20, 5 dossiers. An initial offset-style probe returned
  no rows at 20; the implementation rejects that incomplete result. The final
  run consumed all four pages and verified unique dossier IDs and stable totals.
- Detail example:
  https://planejamenturbanisme.territori.gencat.cat/RPUC-portal/rest/consulta/detall?codiExpedient=42932&idioma=ca&cercaPublic=false
  — real dossier `1993 / 000915 / G`, “Pla general d'ordenació del municipi”,
  type “Pla general d'ordenació urbana”. The source explicitly gives approval
  **1995-05-03** and publication **1995-06-23**, with 24 attached documents.
- Document example:
  https://planejamenturbanisme.territori.gencat.cat/RPUC-portal/rest/consulta/documents?documentId=137970&downloadType=attachment&idioma=ca
  — HTTP 200, `application/pdf`, `%PDF-` signature confirmed for “Memòria.pdf”.
  Other document URLs are generated from the public application's download
  contract and actual `idDocument` values; they were not all individually fetched.

## Records and exclusions

Final live extraction through `load_manifest` and `load_portal_adapter`: **57
records, 531 document links**. Each RPUC dossier is one instrument record, with
all its documents grouped in `documentos` and deduplicated by document ID.
Distinct modification dossiers retain their own official expediente identity;
attachments never become standalone projects. Stable record IDs use RPUC IDs,
not crawl positions or titles. Source titles and Catalan types are retained;
the explicit category describes planning or urban-management dossiers in terms
understood by the existing common entity policy. That policy reports 57 records,
zero unknown entities, status `ok`; no common classifier was changed.

Seven query results have a different primary municipality (regional or
supramunicipal plans); they are excluded even though the RPUC municipality search
returns them. Of 58 municipality-specific dossiers, one is the municipal
land/housing inventory (`305399`), not a project/instrument, and is excluded
separately in extraction statistics. The output includes general and partial
plans, modifications, special plans, consolidated planning rules, TUC delimitation
and urban agreements explicitly concerning water infrastructure, river restoration,
a buried parking facility and municipal equipment. It does not turn licence
forms, procurement announcements or unrelated news into projects. The newer
POUM participation news does not establish definitive approval and is not used
as an inventory record.

`fecha_aprob` and `fecha_publicacion` come only from the detail fields
`dataAprovacio` and `dataPublicacio`. `fecha_acuerdo`, generic `fecha` and `fase`
remain null: the register's approval date is not independently interpreted as a
particular procedural phase or a separate agreement date. The ambiguous listing
`data` is retained under `registro.data_listado_sin_semantica`, never used as a
fallback date. Register validity, registration and assentament metadata are
retained independently; a dated registration entry is not an approval.

## Limits and operation

The public basic search is a snapshot of registered planning and may omit pending,
unregistered, historical or withdrawn dossiers. New approvals cannot be inferred
from news dates. The regional plans intentionally excluded may also affect this
municipality. Licence coverage and comprehensive physical-works coverage remain
unverified. PDF contents are not parsed, and their maps are not vector geometry.
Latitude, longitude and geometry are null; no municipal centroid is substituted.

Requests have connect/read timeouts and bounded 8 MB responses. Missing identity,
invalid dates, changed totals, repeated dossiers and premature empty pages fail
before replacing output. Backfill and update both refresh the complete inventory;
there is no incremental date cutoff that would hide revised historical plans.
Source failures propagate instead of generating placeholder records. Optional
`capture_dir` records compressed raw JSON for reproducibility.

## Validation and local evidence

- `PYTHONDONTWRITEBYTECODE=1 /home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_santa_coloma_de_farners -v`
  — **8 tests passed**. Covers distinct/missing dates, document grouping,
  municipality/identity checks, complete one-based pagination, truncation,
  repeated/changed pages, preservation of existing output on failure, resource
  exclusion, manifest resolution and disabled licences.
- Real live adapter extraction: 65 inventory entries across all four pages;
  7 supramunicipal and 1 inventory-resource exclusions; **57 actual records**.
- Local `evidence/proyectos.jsonl` contains the final annotated records;
  `evidence/validation.json` contains counts, requested source URLs, limitations,
  parser-test result and sampled PDF check. `evidence/rpuc/*.json.gz` contains
  final inventory/detail responses, including the excluded inventory dossier
  captured during the first successful run. Compressed homepage, transparency
  and geoportal shell captures are also under `evidence/`.
- Evidence is local and uncommitted. Only the four requested source files were
  added. No shared modules, dependencies, credentials or deployment services
  were changed or used.
