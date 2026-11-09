# Olivella — INE 08148, Barcelona

Verified live on 2026-11-09 using the preinstalled batch virtual environment.
The manifest follows `municipio/manifest.py`, the adapter contract in
`municipio/adapters/portal.py`, and the existing Manlleu/Hernani examples.
Only this municipality's adapter, tests, manifest and this research file are added.

## Official source discovery and scope

The municipal transparency portal's current [Urbanisme inventory](https://seu-e.cat/ca/web/olivella/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme)
is the entry point. It exposes actual municipal project documents, rather than
procurement announcements or application forms. The adapter verifies that all
nine reviewed project/plan approval categories remain linked, then reads each
category completely. These are unpaginated HTML document inventories, with no
observed result count, next link or server-side page parameter. Pagination links
cause an explicit error; there is no record/page limit or silent slicing.

All paths below are relative to that inventory URL:

| Category path | Live instruments | Interpretation |
| --- | ---: | --- |
| `projectes-d-obres-aprovacio-inicial-205` | 2 | El Querol car park improvement; healthy/cyclable itineraries. Each complete project document is a separate instrument. |
| `projectes-d-obres-aprovacio-definitiva-206` | 1 | Water supply network renewal, carrer Balança; expediente 2378-1641/2025. |
| `projectes-de-reparcel-lacio-aprovacio-inicial-214` | 1 | Plana Novella reparcel·lació; expediente 2301-0909/2023. |
| `projectes-de-reparcel-lacio-aprovacio-definitiva-215` | 0 | Empty official content article; no inferred records. |
| `pla-especial-urbanistic-aprovacio-inicial-216` | 1 | Càmping del torrent de la Romeguera; expediente 2266-0932/2022. Main PEU, five annexes and clarification are one instrument, with seven retained document links. |
| `pla-especial-urbanistic-aprovacio-definitiva-217` | 0 | Empty official content article. |
| `projecte-d-obres-actualitzacio-preus-218` | 1 | Price update for rehabilitation works at El Vinyet. Phase explicitly describes approval of the price update, not execution of the works. |
| `plans-urbanistics-aprovacio-inicial-221` | 1 | Municipal pavement renewal plan, retained as generic `plan`, not assumed to regulate land use. |
| `plans-urbanistics-aprovacio-definitiva-222` | 0 | Empty official content article. |

Other inventories were inspected and captured locally: Normativa d'urbanisme,
Planejament urbanístic (links to RPUC/MUC), the POUM definitive-approval page,
Pla Director d'Equipaments (2016), urban audit (2018), mobility study and technical
memoranda. These sources are outside the nine-category extraction. In particular,
the technical-memoranda page was updated 05/11/2026 and includes further road and
mobility studies; this scraper does not claim to exhaust all physical works or
all recent municipal technical documents. No exhaustive RPUC, BOPB, DOGC, news or
procurement crawl is implemented.

The [municipal Urbanisme page](https://www.olivella.cat/ajuntament/informacio-oficial/urbanisme)
and the transparency portal identify the POUM and explain licence applications.
The [POUM definitive-approval page](https://seu-e.cat/ca/web/olivella/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/poum-pla-d-ordenacio-urbanistica-municipal-aprovacio-definitiva-195)
links RPUC expediente 2012/47907/B and explicitly describes DOGC publication on
04/01/2022. The [urban regulations inventory](https://seu-e.cat/ca/web/olivella/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/normativa-d-urbanisme)
also links the masies/cases rurals plan and repealed subsidiary regulations.
These are useful discovery sources, not additional extracted records here.
The municipal urban licence PDF is an application form: it is not a granted
licence. No verified public granted-licence register is used; licences are disabled.

## Record semantics and provenance

Titles come from municipal download labels. Descriptions retain the municipal
article text. `url` identifies the category article; `documentos` retains each
absolute official document URL, its label and source page. `url_documento` is the
principal document. Navigation/help widgets do not become projects.

Phase comes from the explicitly labelled municipal approval category. It does
not imply construction has started or ended, or a licence has been granted.
`fecha`, `fecha_publicacion`, `fecha_acuerdo` and `fecha_aprob` remain null:
category footers say **Actualització**, not publication or approval date.
`fecha_actualizacion_fuente` records only that source-page update. Even filenames
containing dates are not interpreted as agreement dates. No PDF text date is
inferred from a title, page update, signature or file metadata.

Plana Novella's article explicitly states annex 2 and tables 1–5 of annex 5 are
withheld for personal-data protection; the scraper retains this disclosure in
its description and does not recover omitted material. PDF links establish
document provenance; their contents are not parsed for approvals or geometry.
All 13 document links returned HTTP 200, `application/pdf` and a PDF signature
in a separate live streaming check, recorded in `evidence/document_checks.json`.
Only their initial bytes were inspected; this is not full PDF-content validation.

Stable IDs use expediente where explicitly given, otherwise the primary document
UUID. A repeated instrument across categories causes failure pending grouping
review, rather than duplicate output. Ambiguous principal/annex groupings and
nonempty articles without supporting documents fail closed. Updates re-fetch the
whole scoped inventory; no incremental watermark or historical completeness is
claimed. All coordinates and geometry are null, `publication_ready=false`;
no municipality-centre substitution or geocoding jitter is used. Automatic
scheduling is disabled.

## Validation and local evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_olivella -v
```

Eight offline tests passed: document grouping, separate complete projects,
source-date semantics, empty sections, invalid content, pagination rejection,
inventory completeness, ambiguous grouping, manifest/adapter loading, disabled
licences and full-snapshot updates (some tests cover several related assertions).
Fixtures are embedded and independent of local evidence files.

Live extraction used `load_manifest('olivella')`, `load_portal_adapter(manifest)`
and `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, with the optional
`evidence_dir` runtime config set locally. This exercised the shared registry's
entity-policy annotation as well as the new adapter. Result: **7 records with
13 document links across 9 categories**. The policy reported six unknown entity
categories; source record semantics and the null geometry remain explicit.

`evidence/validation.json` records live count, source URLs, limitations, timestamp,
test result and document checks. Source HTML captures and document check metadata
are under `evidence/`. Evidence is local, ignored by git and is not a source change.
No shared code, dependencies, credentials, publishing or deployment tools were used.
