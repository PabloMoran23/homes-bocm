# Agramunt — INE 25003, Lleida

Verified live on 2026-11-09 using the preinstalled Python runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
The manifest identifies Agramunt, Lleida, Catalunya, INE `25003`.
Scheduling, missing-coordinate jitter and licence ingestion are disabled.

## Official inventory and scope

The municipal [Informació Urbanística inventory](https://www.agramunt.cat/ajuntament/reglaments-i-normatives/urbanisme)
is a public Plone listing of actual planning instruments, with substantive
summaries and linked document collections. Live HTTP extraction found seven
instruments and 80 distinct document links, grouped into seven records. This
is the current contents of this municipal inventory, not a claim of complete
historical planning, physical works or licence coverage. No unrelated news,
procurement advertisements or application forms are used as records.

| Municipal detail page | Documents | Agreement semantics in HTML |
| --- | ---: | --- |
| [POUM](https://www.agramunt.cat/ajuntament/reglaments-i-normatives/urbanisme/poum) | 63 | Narrative: definitive approval 2023-09-20; executive-publication agreement 2024-01-31; DOGC 9119 publication 2024-03-11 |
| [Modificació del POUM, Donzell](https://www.agramunt.cat/ajuntament/reglaments-i-normatives/urbanisme/modificacio-del-poum) | 2 | Initial approval 2025-01-30; expediente 151/2025 |
| [TUC](https://www.agramunt.cat/ajuntament/reglaments-i-normatives/urbanisme/tuc-trama-urbana-consolidada) | 4 | Provisional approval 2025-04-30; definitive approval 2025-07-23; expediente 4/2025 |
| [PEUCH Mercadal](https://www.agramunt.cat/ajuntament/reglaments-i-normatives/urbanisme/peuch-mercadal-agramunt-16-12-2024.pdf/view) | 1 | No explicit agreement/publication date or phase; null |
| [PMU Complex Llurba](https://www.agramunt.cat/ajuntament/reglaments-i-normatives/urbanisme/aprovacio-inicial-pla-de-millora-urbana-per-possibilitar-lincrement-de-lalcada-de-les-naus-expedient-1909-2024) | 5 | Text-refundido approval 2025-07-03; CTU approval 2025-07-23; expediente 1909/2024 |
| [PMU Carretera Tàrrega 9](https://www.agramunt.cat/ajuntament/reglaments-i-normatives/urbanisme/pla-de-millora-urbana-per-regular-la-composicio-volumetrica-del-pati-interior-dilla-carretera-tarrega-9-exp-1291-2025) | 2 | Provisional approval 2025-10-30; expediente 1291/2025 |
| [Modificació POUM, densitat clau 1a/1b](https://www.agramunt.cat/ajuntament/reglaments-i-normatives/urbanisme/modificacio-del-text-refos-del-pla-dordenacio-urbanistica-municipal-poum-per-regular-la-densitat-de-la-zona-del-centre-historic-clau-1a-i-de-la-zona-ravals-clau-1b-exp-num-2160-2025) | 3 | Human-readable certificate label: initial approval 2025-11-27; expediente 2160/2025 |

The official [electronic-office catalogue](https://agramunt.eadministracio.cat/info.0)
also surfaced during source discovery. It advertises works/urbanism application
procedures, including prior works communications; it is not evidence of granted
licences. No granted-licence register was verified. This adapter therefore uses
only the public municipal planning inventory above.

## Extraction and provenance

The adapter implements the existing `AyuntamientoAdapter` backfill/update
contract and loads through the manifest's import specification without registry
or shared-source changes. It discovers instrument detail URLs from the inventory;
no seven-row list is hardcoded. Stable IDs hash each municipal instrument URL.
The update method refreshes the complete current snapshot without a date cutoff.

Document links come from each detail page's content area: POUM accordion contents,
Plone file entries, or the Mercadal file viewer. Each document retains its visible
title, exact municipal link and the HTML page on which it was found. PDFs, maps,
certificates, assessments and annexes remain attached to the parent instrument;
they are not emitted as separate projects. Duplicate URLs within an instrument
are removed; distinct documents with identical titles retain their distinct URLs.
PDF contents are not downloaded or parsed by the adapter, and document existence
is established from the official HTML inventory rather than a binary audit of
all 80 files. Geometry embedded in PDF maps is not converted into vector data.

Agreement extraction is limited to explicit dated approval clauses; cited laws
and their dates are ignored. `acuerdos` preserves the dated clauses, including
prior stages. `fecha_aprob` and `fecha_acuerdo` describe the latest stated approval
stage, not necessarily definitive approval. The POUM's 2024 executive-publication
agreement is separately retained and does not replace its narrative's 2023
approval date. Administrative document titles distinguish conditional approval
and the later text-refundido resolution; their exact labels and links are retained
without silently rewriting the municipal narrative. Only an explicit DOGC
publication statement populates `fecha_publicacion`. Generic `fecha` stays null.
The densitat modification uses its explicit human-readable approval certificate
label, not a date inferred from its filename. Mercadal's filename date does not
become an approval or publication date. No crawl or page-modification date is
used as an agreement date.

The current live pages have no next-page links. The crawler nevertheless follows
recognised next links on both the inventory and document collections. Cycles,
conflicting pagination, unknown pagination markup, unexpected inventory entries,
unreviewed nested document folders, missing documents, redirects, non-HTML pages
and oversized responses fail before replacing output. A 100-page per-collection
safety limit raises an error; it never silently truncates output. Network requests
have a 35-second timeout and a 4 MB HTML response limit. Only official municipal
URLs under the urbanism path are accepted.

## Limits and validation

No coordinates or verified vector geometries are supplied by this extraction;
`lat`, `lon`, `geometry` are null and `publication_ready` is false for every row.
No municipal centroid, inferred parcel position or jitter is substituted.
The existing shared entity policy annotated all seven rows successfully, with
three unknown categories. This is recorded in local validation; no shared
classification policy was changed.

- Parser/contract tests: `python -m unittest municipio.test_agramunt -v` using the
  runtime above: **7 passed**. Tests cover date semantics, legislation exclusion,
  unknown dates, forms/error-page rejection, document deduplication, multi-page
  inventory/document extraction, loop detection, stable IDs, unchanged prior
  output on failure, manifest loading and disabled licences.
- Real extraction: `load_manifest('agramunt')`, `load_portal_adapter(manifest)`,
  then `backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **7 live records,
  80 linked documents, 8 municipal HTML pages**, status `ok`.
- Local evidence: `evidence/proyectos.jsonl`, `evidence/validation.json`, and
  `evidence/captures/<sha256-of-source-url>.html`. Validation maps captures to
  exact URLs and records UTC extraction time, limitations, live counts and the
  shared entity-policy result. Initial discovery captures also remain under
  `evidence/`. These are local artifacts, not source files to commit.

No credentials, other workspaces, databases, deployment, publishing or remote git
operations were used.
