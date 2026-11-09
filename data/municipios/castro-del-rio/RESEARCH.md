# Castro del Río (Córdoba), INE 14019

Verified live on 2026-11-08 using the preinstalled batch virtualenv. This adapter
extracts a deliberately partial **municipal planning-document inventory**. It does
not establish that the documents represent the latest legally effective version
of planning. Scheduling, licence extraction and missing-coordinate jitter are
disabled. No shared source files or dependencies were changed.

## Official source inventory

The municipal website exposes its urban-planning inventory at
https://castrodelrio.es/urbanismo-y-obras-publicas/ (HTTP 200).
https://castrodelrio.es/portal-de-transparencia/urbanismo-y-obras-publicas/
redirects to that inventory. The currently served page has six entries and no
pagination links or controls. Four are document-bearing urban-planning dossiers:

| Municipal detail URL | Page publication | Documents |
| --- | --- | --- |
| https://castrodelrio.es/plan-parcial-para-el-desarrollo-del-sector-pp-4/ | 2022-04-28 | 4 |
| https://castrodelrio.es/modificacion-de-las-normas-subsidiarias-de-planeamiento-de-castro-del-rio-para-la-clasificacion-y-ordenacion-de-un-nuevo-sector-de-suelo-urbanizable-pp-12-y-la-ampliacion-del-sistema-general-de-espaci/ | 2021-05-15 | 8 |
| https://castrodelrio.es/tramitacion-de-innovacion-de-planeamiento-general/ | 2021-01-28 | 5 |
| https://castrodelrio.es/p-g-o-u-memoria-de-subsanacion/ | 2016-05-25 | 13 |

All four detail pages returned HTTP 200 in the live adapter extraction. These
are named planning instruments with technical, environmental, summary or plan
attachments, rather than procurement announcements or generic news. The innovation
page includes an agreement certificate labelled PP2 and environmental filenames
referencing PP2; its generic municipal heading is preserved verbatim rather than
inventing a more specific legal title. The PGOU page groups one memorandum and
12 drawing links. PP-12/PE-2 is one modification dossier, not separate records
for the two sectors, environmental documents and agreement. No agreement dates
or approval stages are inferred from document labels or upload paths.

The other entries are the inventory self-link and a mobility guide:
https://castrodelrio.es/guia-de-movilidad/ (HTTP 200). They are excluded from this
urban-planning extraction. The guide links an annex to a sustainable mobility
plan, but this adapter does not cover transport planning. Other kinds of public
works and the municipality's full historic planning corpus are outside coverage.

The separate transparency host https://transparencia.castrodelrio.es/ returned
HTTP 403. It was not bypassed. Search discovery also exposed regional BOJA
planning publications, for example
https://www.juntadeandalucia.es/boja/2020/229/70 and
https://www.juntadeandalucia.es/boja/2022/123/64. These show additional legal
history; this adapter does not crawl BOJA or infer current legal status from old
municipal pages. Neither a granted-licence inventory nor a complete current
planning register has been verified.

## Document provenance and date semantics

Each output record retains every attachment URL from the main detail content in
`documentos`, together with its source page and a label. Links in menus and social
sharing controls are excluded. Older table-layout labels are read from the
surrounding document row. Legacy links mostly point to
`http://afosoftservices.com/wordpress/wp-content/uploads/...`; they remain exactly
as the municipality publishes them. They are **not** silently rewritten to the
municipal host or treated as independently verified official document contents.

A probe of
http://afosoftservices.com/wordpress/wp-content/uploads/2022/04/RESUMEN-EJECUTIVO.pdf
failed certificate verification after HTTPS redirection (hostname mismatch).
The equivalent HTTPS URL also failed. No TLS verification bypass was used. Thus
usable municipal HTML establishes the four real document-bearing instruments,
but attachment availability and substantive PDF text are unverified. Another
published link points to the Eprinsa municipal edict verification service; it is
retained with the same provenance limitation. There are 30 links in total.

`fecha_publicacion` is the detail page's explicit `datePublished` value. It is
not an agreement date, PDF signature date, or crawl time. Some attachments have
later upload paths than the page publication date; this field does not date those
attachments. `fecha`, `fecha_acuerdo`, `fecha_aprob` and `fase` remain null.
Dates of unknown meaning and approval levels are not synthesized. No source
coordinates or machine-readable geometry are verified; `lat`, `lon`, `geometry`
are null and `publication_ready` is false. No municipal centroid is substituted.

## Adapter behavior and verification

The manifest loads through `municipio.manifest.load_manifest`; the adapter follows
`AyuntamientoAdapter` and can be loaded by the existing dynamic registry. Stable
IDs derive from municipal detail URLs. Updates refresh the complete supported
inventory snapshot, not only new links. All pages must validate before the JSONL
is replaced, so a failed fetch or changed markup cannot leave a partial snapshot.
HTML requests have timeouts, verified certificates and a 3 MB response bound
whose violation raises an error. Empty or unrecognized inventories, unsupported
new entry types and documentless detail pages fail explicitly. Pagination is
currently absent; if links or controls appear, extraction fails for review rather
than silently stopping at page one. There is no page-count or record-count cutoff.

Validation commands, executed with
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`:

- `-m unittest municipio.test_castro_del_rio -v`: **8 tests passed**. Covers
  grouping/deduplication, date separation and missing dates, stable IDs, rejected
  forms/navigation, changed markup, external detail URLs, pagination rejection,
  snapshot replacement and preservation on failure, manifest and disabled licences.
- Live `load_portal_adapter(load_manifest('castro-del-rio')).backfill_proyectos(...)`:
  **4 actual records and 30 document links**, through the shared entity-policy
  wrapper. The policy reports all four as unknown entity category; the adapter
  makes no unsupported residential classification.
- Local evidence: `evidence/proyectos.jsonl`, `evidence/validation.json` and
  `evidence/captures/*.html` from live adapter requests, plus discovery captures.
  Evidence is for local review and is not part of the four source additions.

No authentication, credentials, databases, publication or deployment tools were
used. Readiness here means the narrow documented extraction works; independent
review must decide acceptance and any later publication requirements.
