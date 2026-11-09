# La Bisbal del Penedès — INE 43028, Tarragona

Verified live on 2026-11-09 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
The adapter extracts genuine planning instruments and a physical public-works
project from the municipal inventories. This is a partial inventory snapshot,
not a complete historical register or a statement of current legal validity.
Scheduling, granted-licence extraction and missing-coordinate jitter are disabled.

## Official inventories discovered

- https://bisbalpenedes.com/web/portfolio/urbanisme/ — HTTP 200, current
  public-exposure section. One instrument: modification of the subsidiary planning
  rules for sector SAU-2, expediente 544/2026, expanding school-equipment land.
  Agreement/initial approval: 2026-07-30. BOPT publication: 2026-09-10.
  Four linked documents are retained together: technical report, plenary
  certificate, BOPT notice and newspaper notice. All four returned actual PDFs
  (HTTP 200) and are captured locally. The agreement certificate explicitly
  confirms expediente 544/2026 and the plenary session date; its later signature
  date is not used as approval. The BOPT notice also repeats that agreement.
- https://bisbalpenedes.com/web/portfolio/urbanisme-actuacions-anteriors/ — HTTP
  200, previous proceedings, linked directly from the first inventory. Three
  instrument groups, all extracted:
  - Gymnasium and sports facilities public-works project: initial approval by the
    local government board on 2026-06-17; BOPT publication on 2026-07-13; three
    documents grouped. Includes the phased executive project and certificate.
  - Detailed modification of subsidiary rules for Les Planes del Vent,
    expediente 119/2025: initial approval on 2025-03-27; BOPT publication
    2025-04-22. Twenty distinct document URLs retained together, including
    studies, plans, certificates, DOGC, BOPT and newspaper notices. The DOGC
    2025-04-17 and newspaper 2025-04-16 dates remain attached to their respective
    documents. The record-level publication field explicitly identifies BOPT
    as its source; it does not pretend all publications occurred on that date.
  - Adaptation of NSS to general planning law and present needs: two distinct
    URLs, including the technical document and one certificate linked under
    **both** initial and provisional approval labels. These labels are preserved
    in `documentos[].etiquetas`, without treating them as two instruments.
    Phase, agreement and publication dates remain null because the inventory
    provides no unambiguous dated approval narrative. Dates and dossier numbers
    are not inferred from filenames. This scraper does not parse PDF contents
    for additional metadata.
- https://bisbalpenedes.eadministracio.cat/transparency/fa2b5ded-4328-48f3-9e38-3bda45f6d5a7/
  — HTTP 200, municipal urban-planning regulations transparency inventory. It
  links a consolidated NNSS document and an instruction for subdivision licence
  processing. Captured for source discovery, outside the two-page extraction
  scope. The instruction is not a granted licence or a physical project.
- https://bisbalpenedes.eadministracio.cat/transparency/eb4cc193-4f52-4e64-9d17-4831a88d55fb/
  and https://dtes.gencat.cat/rpucportal/#/inici are additional navigation links
  exposed by the municipal page, not extracted dossier inventories in this adapter.
- https://bisbalpenedes.com/web/category/noticies/urbanisme/ is a separate news
  inventory, excluded from extraction. In particular, the municipal news item
  https://bisbalpenedes.com/web/2026/09/24/el-ple-aprova-la-verificacio-del-text-refos-de-la-modificacio-puntual-de-les-normes-subsidiaries-de-planejament-de-la-bisbal-del-penedes/
  describes later processing of the NSS adaptation, rather than definitive
  approval. Archive location or an initial-approval notice must not be read as
  its latest legal status. No unrelated news or procurement announcements become
  records.

## Extraction contract and limitations

Both reviewed inventory pages are unpaginated. The adapter fetches both in full,
flattens WordPress groups in DOM order and uses coloured instrument headings as
boundaries. Every linked document in each supported instrument group is retained,
including links to official DOGC/BOPT notices. A repeated document URL retains
all its source labels. Unsupported instrument headings, missing documents,
missing archive navigation, ambiguous duplicate instruments or detected inventory
pagination fail explicitly before replacing the output. WordPress next-portfolio
navigation to Camins i Rutes is unrelated to inventory pagination and is excluded
from that check. There is no page-count cap or silent pagination truncation.

Identity uses the explicit expediente where present, otherwise the complete
instrument heading; no invented expediente is supplied. All rows identify
La Bisbal del Penedès, Tarragona, INE 43028. Dates are read only from explicit
full dates in approval narratives or labelled publication entries. Generic
`fecha` stays null. `fecha_acuerdo` and `fecha_aprob` share a date only when the
narrative explicitly says the agreement approved the instrument initially.

The source contains imperfect document links: HTTP URLs, unescaped spaces,
a `.pdff` annex suffix, and a second link labelled PDF in the E-tauler entry
pointing to the previously listed newspaper file. Links and their labels are
preserved as published, without guessing corrections. Documents are not all
redownloaded on each run; the scraper guarantees inventory-link retention, not
availability of every attachment. Representative agreement PDFs for all three
archived groups returned HTTP 200 and are captured in local evidence.

No project geometry was verified in these inventories. `lat`, `lon` and
`geometry` remain null and `publication_ready` is false. No municipal centroid,
parcel guess or invented location is substituted. Backfill and update both
refresh the full scoped snapshot. Licence methods explicitly report disabled.

## Validation and local evidence

- `python -m unittest municipio.test_la_bisbal_del_penedes -v`: seven tests passed
  under the required preinstalled runtime. Tests cover grouping and boundaries,
  distinct date semantics, duplicate link labels, uncertain metadata, pagination
  rejection, unrelated portfolio navigation, invalid sources, full refresh,
  preserving prior output on failure and manifest/registry integration.
- Real live extraction through `load_portal_adapter(load_manifest(...))`:
  **4 records, 29 grouped document URLs**. The shared entity policy wrapper
  returned status `ok`; its three unknown entity classifications remain explicit
  in the evidence. That policy result does not establish publication readiness.
- `evidence/proyectos.jsonl`: actual live extracted records.
- `evidence/validation.json`: live count, URLs, limitations, parser-test result,
  document-check results and source-capture list.
- `evidence/urbanisme.html`, `evidence/anteriors.html`,
  `evidence/transparency.html`, seven representative PDFs and two extracted
  source-text captures are local evidence, not source files for commit.

Only the municipality manifest, this research note, its adapter and its parser
unit-test module are added as source. No shared code or dependencies are changed.
