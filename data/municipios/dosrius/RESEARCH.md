# Dosrius — INE 08075, Barcelona, Catalunya

Verified live on 2026-11-09. This adapter extracts a complete snapshot of **one
reviewed inventory**, not a complete municipal register: 43 grouped public-work
projects / planning instruments, with 117 source document links. It does not
extract granted licences. Scheduling and coordinate jitter are disabled.
`publication_ready` is false throughout.

## Official sources discovered

The municipal [urban-planning index](https://seu-e.cat/ca/web/dosrius/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme)
links the following inventories, all fetched anonymously with HTTP 200 and saved
under local `evidence/`:

- [Local works and planning instruments in public information](https://seu-e.cat/ca/web/dosrius/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/projectes-d-obres-locals-i-instruments-de-planejament-en-tramit-204).
  **Implemented source.** One HTML inventory with annual sections 2020–2026 and
  a page-update footer dated 05/10/2026. Includes resurfacing, water and sewer
  infrastructure, public buildings and NNSS modifications. Full inventory is
  parsed without a record cap. No pagination was present; pagination controls or
  next-page links cause extraction to fail instead of silently truncating it.
- [Urban planning](https://seu-e.cat/ca/web/dosrius/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic).
  Links the Can Massuet green-zone modification and plans, already represented
  in the implemented inventory. The forest-settlement delimitation is also named.
  Not a comprehensive machine-readable current planning register.
- [Environmental projects](https://seu-e.cat/ca/web/dosrius/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/projectes-medi-ambient-209).
  Contains climate shelters, forest-settlement delimitation and fire-prevention
  plans / infrastructure maps. Discovered and captured, outside extraction scope.
- [Projects pending processing](https://seu-e.cat/ca/web/dosrius/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/projectes-pendents-de-tramitar-220).
  Contains the February 2023 Torre de les Aigües consolidation project. Captured,
  outside extraction scope; not promoted to an approved project.
- [Works, uses and activities in public information](https://seu-e.cat/ca/web/dosrius/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/projectes-d-obres-usos-i-activitats-en-tramit-d-informacio-publica-225).
  Contains specific-action projects, masia rehabilitation, a water-supply master
  plan and also provisional uses / event safety documents. Captured, outside
  extraction scope. Publication in this inventory does not establish a licence.

The [municipal urban-planning service page](https://www.dosrius.cat/arees/urbanisme)
also describes historical general planning and links to RPUC and application
procedures. Those procedure links are not granted-licence records and are not
scraped as such. No comprehensive granted-licence inventory was verified.

## Extraction, grouping and source quality

The parser requires the actual public-information inventory and its municipal
document links. It recognizes explicit project / planning titles, preserves the
original titles and section years, associates following documents with each
instrument, and excludes the BCIL heritage declaration. Standalone procurement
announcements, forms and unrelated news do not qualify.

All volumes, certificates, amendments and announcement links in a project block
are retained with their source URL, original label and list-item context. Relative
links are resolved. Identical titles across years and shared supporting-document
identifiers are grouped; different names of the municipal Can Batlle library are
also grouped. The repeated La Tortuga roof instrument spans 2021/2022; the 2023
roof/garage project has two titles sharing its actual project PDF. Similar annual
road works and NNSS changes without proven common document identity remain
separate; a common facility alone does not establish that they are one instrument.
The explicit Can Batlle library alias is the narrowly reviewed exception.

Source anomalies are retained, not repaired by inventing URLs:

- UA XVI volume 2 labels **41–60** and **61–80** point to the same 61–80 PDF.
  Both labels/links remain. The inventory contains 26 links in this instrument;
  this does not establish that all source pages are available.
- A 2023 La Tortuga project title is incorrectly wrapped in the preceding
  library PDF hyperlink. It remains in `documentos` with
  `enlace_en_titulo: true`; title hyperlinks are excluded from identity grouping,
  so this source error cannot merge the roof and library projects.
- Some document descriptions have no hyperlink (including some certificates and
  announcements). They cannot be treated as downloadable documents.

Dates are extracted only from explicit session narratives in titles / document
labels. Three records expose agreement dates: the two NNSS changes agreed on
2022-09-29 and the pavement project initially approved on 2023-10-17.
`fecha_acuerdo` and, where initial approval is explicit, `fecha_aprob` retain these
values. Page updates, annual sections and dates in filenames do not become
approval/publication dates. `fecha` and `fecha_publicacion` remain null.
Initial approval labels do not establish definitive approval or current execution.
PDF text is not parsed for additional dates.

No project coordinates or geometry were verified. `lat`, `lon`, and `geometry`
remain null. No municipal centroid or invented location is substituted.

## Validation and limits

Runtime used:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_dosrius -v`: 10 tests passed, covering grouping,
  dates, source-link errors, exclusions, pagination rejection, manifest flags,
  disabled licences and preservation of an existing snapshot on parse failure.
- Real extraction through `load_manifest`, `load_portal_adapter` and
  `backfill_proyectos`: **43 records**, **117 links**, unique record IDs.
- A linked approval certificate was fetched successfully and checked for a PDF
  signature (204745 bytes). The exact URL, content hash and HTTP metadata are
  in `evidence/validation.json`; the PDF is `evidence/sample-certificate.pdf`.
  Remaining attachments are retained as links but not individually downloaded
  or validated for availability or content.
- Local evidence includes `proyectos.jsonl`, `validation.json`, the inventory
  HTML, discovery captures and `discovery.json`. These are not source files and
  are not to be committed. Updates refresh the complete inventory; no date
  watermark hides edits to old sections. Output replacement is atomic after
  successful parsing. Network/HTTP/parser failures propagate rather than emit
  empty success records.

The shared registry entity policy reports **adapter_incident /
unknown_entity_spike**: 41/43 genuine source records lack the expediente evidence
recognized by its current rules, which also do not recognize most Catalan titles.
This report is retained in evidence; no expediente or identity was fabricated to
bypass the guard and no shared policy was changed. Extraction readiness is not
publication approval: these records still require independent semantic review
and verified geometry before any publication. Coverage is partial as detailed
above, and schedule.enabled=false remains mandatory.
