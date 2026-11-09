# Monesterio — INE 06085, Badajoz, Extremadura

Verified live on 2026-11-09 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
This adapter extracts the complete **published municipal Normativa inventory**,
not a comprehensive inventory of urban works or all regional planning proceedings.
It produces three genuine planning instruments, including historical documents.
Availability does not establish current legal validity. `publication_ready` is
false because no verified project geometry is extracted.

## Official source discovery

- Municipal site map: https://monesterio.es/sitemap.php (HTTP 200) links to
  Atención al Ciudadano → Normativa and Obras - Urbanismo.
- Inventory: https://monesterio.es/plantilla.php?enlace=normativa (HTTP 200).
  The main NORMATIVA panel contains three named planning documents and no
  pagination. Its navigation and news sidebars are excluded.
- Works service: https://monesterio.es/plantilla.php?enlace=obras (HTTP 200).
  Contains twenty application/certificate/self-assessment forms, including
  solicitud de licencia de obras and licencia primera ocupación. These are not
  granted licences or physical works projects. No licence register was verified;
  `licencias.enabled=false`.
- Regional planning detail:
  https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/37084 (HTTP 200).
  Names the Monesterio Plan General Municipal. Besides 2023 partial approval and
  2025 DOE publication, it lists partial CUOTEX approval on 2026-01-29 and appeal
  485/2025 with resolution date 2026-04-20, “Estimatorio firme”. The general-state
  label also says “Vigente”. These fields require legal interpretation; the scraper
  does not infer their effect or claim the PGM is wholly approved/current. This
  regional detail is research context, not an extracted second project or an
  inventory traversed by the adapter.

## Documents checked

All three municipal links returned HTTP 200 and actual PDF bytes; local captures
are retained in evidence. `pdftotext` was used only for manual research of the
first two pages, without adding a runtime dependency.

1. https://monesterio.es/documentos/20130928114240.pdf
   “APROBACION MODIFICACION PUNTUAL 11 DE LAS NORMAS SUBSIDIARIAS”. Portal upload
   2013-09-28. PDF is DOE 65, 2008-04-04, resolution of 2006-07-20 approving
   modification 11 (adaptation of part of the urban rules to LSOTEX).
2. https://monesterio.es/documentos/20130928114133.pdf
   “NORMAS SUBSIDIARIAS DE PLANEAMIENTO MUNICIPAL”. Portal upload 2013-09-28.
   PDF begins with resolution of 1996-05-29 approving the NNSS revision and its
   urban rules. It is retained as a historical instrument without asserting
   present applicability.
3. https://monesterio.es/documentos/20250729123030.pdf
   “Plan General Municipal de Monesterio”. Portal upload 2025-07-29. PDF is DOE
   119, 2025-06-23, agreement of 2023-06-27 for **partial** definitive approval.
   Its official regional counterpart is
   https://doe.juntaex.es/pdfs/doe/2025/1190o/25AC0049.pdf (also linked by SITEX).
   The municipal description identifies this DOE issue, not an agreement date.

The adapter parses inventory metadata, not PDF text. Therefore it leaves
`fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob`, generic `fecha` and `fase`
null. Actual portal upload dates are retained only as `documentos[].fecha_alta_portal`.
The researched dates above are not hardcoded into extracted records.

## Extraction behavior and limits

One live GET to the fixed official inventory, 30-second timeout, a 2 MB bound
that raises instead of truncating, HTTP error/redirect checks. The parser requires
one identified municipal NORMATIVA panel, named planning instruments and municipal
PDF paths. Empty results, changed panels, unexpected document hosts, malformed
dates and recognized new pagination controls fail explicitly. There is no page
limit or silent first-page cutoff: the verified source has one unpaginated page;
new pagination requires implementing traversal before extraction can continue.

Documents with the same normalized instrument title are grouped in one record,
retaining distinct links, descriptions, source URL and upload dates. Stable IDs
use the normalized instrument title. NNSS and their separately named modification
are distinct instruments. Unrecognized future title families need parser review;
this is not a general municipal-news extractor. PDF content is not downloaded on
every run. Update refreshes the full selected inventory snapshot, ignoring the
state path because this source exposes no reliable incremental cursor.

No document geometry, parcel geometry or coordinates have been verified. Null
`lat`, `lon`, `geometry`; no municipal centroid, geocoding or jitter substitution.
Schedule and missing-coordinate jitter are explicitly disabled. No database,
publishing or deployment operations are required.

## Validation and local evidence

- `python -m unittest municipio.test_monesterio`: **8 tests passed** covering date
  semantics, provenance, document grouping/stable IDs, parent/modification
  distinction, exclusion of forms/navigation, pagination rejection, unexpected
  URLs/invalid dates, missing dates, manifest loading and disabled licences.
- Real extraction through `load_manifest` → `load_portal_adapter` →
  `backfill_proyectos`: **3 records**, shared entity-policy annotation status ok.
  Entity-policy categories are unknown for these planning instruments; no shared
  classification policy has been changed.
- Local `evidence/proyectos.jsonl` contains the actual live records;
  `evidence/validation.json` records live count, source URLs, parser checks and
  limitations. HTML captures: normativa, obras, sitemap and sitex. All three PDF
  captures and the first-two-page research text extracts are also retained.
- Only the four requested source files are added. Evidence remains local and is
  not intended for commit.
