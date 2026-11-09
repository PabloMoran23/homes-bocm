# Torrefarrera — INE 25228, Lleida, Catalunya

Research and live validation: 2026-11-09. This adapter covers the current
municipal planning and public-information inventories. It is a partial snapshot,
not a complete historical register or a granted-licence inventory. Scheduling,
licence extraction and coordinate jitter are disabled.

## Official sources inspected

- https://www.torrefarrera.cat/ajuntament/urbanisme-1 — municipal urbanism index.
- https://www.torrefarrera.cat/ajuntament/urbanisme-1/planejament — live Plone
  inventory: informative consolidated NNSS text, soil classification,
  non-developable-soil zoning and 2025 zoning maps. These four files belong to
  one planning instrument and are grouped. The RPUC navigation link is retained
  as a reference, not emitted as another instrument. The informative consolidation
  is not represented as a new approval or as independently authoritative law.
- https://www.torrefarrera.cat/ajuntament/informacio-publica-ajuntament — live
  mixed public-information inventory. Supported entries are the June 2026 NNSS
  commercial amendment folder, school La Creu photovoltaic project, rural
  classroom specific-action project, NNSS amendment replacing PMU3, PP15 parking
  amendment and NNSS amendment adjusting normative provisions.
- https://www.torrefarrera.cat/ajuntament/informacio-publica-ajuntament/modificacio-de-les-nnss-de-planejament-de-torrefarrera
  — one commercial NNSS amendment document, separate from the PMU3 and normative
  amendments. Its document title says June 2026; this is not an approval date.
- https://www.torrefarrera.cat/ajuntament/informacio-publica-ajuntament/projecte-d2019actuacio-especifica-per-a-la-implantacio-d2019una-aula-rural-al-sol-no-urbanitzable
  — one instrument with both BOP notice and technical project retained together.
- https://seu-e.cat/es/web/torrefarrera/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  — discovery corroboration: transparency page points to RPUC/MUC, not a separate
  inventory of records extracted by this adapter.

All extraction URLs are taken from municipal listings and file-view download
links. Exact per-record URLs and document titles are in `evidence/proyectos.jsonl`;
all fetched page URLs are listed in `evidence/validation.json`. Discovery results
from the official municipal sitemap corroborate these inventories.

## Document checks and semantics

Three actual linked PDFs were also downloaded into local evidence and inspected
using the preinstalled `pdftotext` for research only:

- `aprovacio-de-projecte-tecnic.pdf`: actual technical photovoltaic installation
  project, reference 5178/FTV/0325, municipal petitioner, 35.10 kWp at school La
  Creu, document dated April 2025. The listing label says approval, but the PDF
  starts with the technical project; no precise approval date is inferred.
- Rural classroom `anunci-bop-129-de-09-07-25.pdf`: expediente 445/2025,
  public-information notice published in BOP 129 on **2025-07-09**, signed
  **2025-06-27**. It concerns processing/legalisation of existing constructions,
  not proof of a granted licence. Neither signature nor publication establishes
  an approval date.
- `aprovacio_inicial_mnnss_ambit_pmu3.pdf`: expediente 796/2024; initial approval
  by the plenary on **2025-04-11**; secretary's diligence/signature **2025-04-15**.
  These dates are different events. This modification enables residential and
  healthcare uses in the former PMU3 area; it is not a granted building licence.

The runtime adapter parses HTML inventories and attachment provenance, not PDF
text. Consequently `fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob`
and `fase` remain null on all records. The manually observed dates above are
research evidence, not hardcoded runtime data. File timestamps, filenames,
drafting dates and crawl time are never substituted for administrative dates.
No approval, construction completion or current legal validity is asserted from
an inventory title alone.

Environmental-authorisation applications, music-bar licence consultation,
AGRONAC/REPSOL activity notices, machinery-rental activity documents, emergency
plans, procurement and unrelated subsidy/accounting/cultural material are excluded.
The classroom record is an actual specific-action planning project under public
consultation, not a licence record.

## Extraction, grouping and coverage

The adapter follows each supported folder and file view. It requires a unique
municipal download link per file, retains all folder attachments and groups the
NNSS base text with its mapping documents. Duplicate file-icon anchors are
removed. Stable IDs derive from the municipal instrument entry URL; new URL
identities or separately published folders may need future identity reconciliation.
There is no claim of deduplication against RPUC or unvisited historical archives.

Both reviewed inventories and project folders are currently single pages.
Pagination controls or pagination query links trigger an explicit failure rather
than a truncated snapshot. Unsupported nested project folders, missing content,
empty inventories and missing/ambiguous downloads also fail. A successful update
refreshes the full supported snapshot atomically and does not claim incremental
history. HTTP errors and oversized HTML responses fail before output replacement.

Document contents/availability are not comprehensively revalidated at runtime;
the links and their municipal file-view provenance are checked. New unsupported
title families require further review. No geometry is extracted from the PDF
maps and no centroid is substituted: lat/lon/geometry stay null and
publication_ready is false.

## Validation and local evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_torrefarrera -v`: eight parser/adapter tests covering
  grouping, date/geometry semantics, exclusion, pagination, changed/error markup,
  attachment failure preserving output, stable snapshot identity and manifest.
- Live extraction returned **7 instruments with 11 linked documents**.
- Real extraction uses `load_manifest`, `load_portal_adapter` and
  `backfill_proyectos`, including the shared entity-policy annotation wrapper.
- Local `evidence/proyectos.jsonl`, `evidence/validation.json`, HTML captures under
  `evidence/captures/`, and research PDF/text captures are intentionally uncommitted.
  Validation records the live count, fetched source URLs and limitations.

No dependencies or shared sources were changed. No credentials, databases,
production systems or publishing operations are used.
