# Corella — Navarra — INE 31077

Verified live on 2026-11-08. This adapter extracts the municipal Plan General
Municipal (PGM) document inventory as **one instrument with 76 document links**.
Coverage is deliberately partial. It does not claim a complete municipal planning
register, a public-works inventory or granted licences. Scheduling is disabled.

## Official sources investigated

- https://www.corella.es/urbanismo/ — HTTP 200. Current municipal Urbanismo page
  with a `PLAN GENERAL MUNICIPAL` section, subdivided into Estrategia y Modelo de
  Ocupación del Territorio (EMOT) and Plan Urbanístico Municipal (PUM). Contains
  substantive memoranda, development programme, environmental assessment,
  participation material, regulations, catalogue and planning drawings. All 76
  unique PDF links within this section are retained, including their source
  labels and section. These documents belong to the PGM, not 76 projects.
- https://www.corella.es/wp-content/uploads/2021/12/01_Normativa.pdf — HTTP 200,
  application/pdf, 3,885,489 bytes. Manually inspected first pages with the
  preinstalled `pdftotext`. Identifies the PGM of Corella and its municipality.
- https://www.corella.es/wp-content/uploads/2021/12/01_MEMORIA-INFORMATIVA-DESCRIPTIVA-Y-JUSTIFICATIVA.pdf
  — HTTP 200, application/pdf, 3,241,437 bytes. First pages independently confirm
  the same PGM. The adapter retains links; it does not download or parse PDFs.
  Other attachment contents and continuing availability have not been checked
  individually.
- https://www.corella.es/proceso-de-participacion-peau-09/ — HTTP 200. Official
  participation page published 12 February 2025, with an actual participation PDF
  for the PEAU-09 planning instrument. Identified as an additional genuine source,
  outside this narrow PGM inventory adapter. A participation meeting is not an
  approval, and no separate PEAU-09 record is emitted by this implementation.
- https://corella.animsa.es/transparencia/informacion-sobre-ordenacion-territorial-urbanismo-medio-ambiente-y-vivienda/
  — HTTP 200. Describes transparency requirements but supplies no concrete
  instrument inventory in the retrieved HTML. Not turned into a project.
- https://sedeelectronica.corella.es/catalogoservicios.aspx and
  https://sedeelectronica.corella.es/carpetaciudadana/tramite.aspx?idtramite=5672
  — official service catalogue and declaration/application procedure discovered
  through web search. They describe submitting applications, not granted licences.
  Likewise the licence, declaration, tax self-assessment and completion forms
  below the PGM section on Urbanismo are excluded.

## Date and spatial semantics

The inventory HTML has no approval date, publication date or explicit approval
phase for the PGM. All corresponding fields are null. Upload paths such as
`2021/12` are not publication dates. Crawl time is not an event date.

Manual document review found different events on the first pages of both checked
PDFs: provisional municipal approval on 27 July 2021; a diligence stating approval
by Orden Foral 131E/2021 of 14 October; and the diligence's own date of 15 October
2021. The cover also says May 2021. These must not be conflated. They are documented
here as research findings; the HTML-only parser does not infer event fields from
them or hardcode dates. The statutory publication date and the complete subsequent
amendment history have not been established.

Drawings are retained as document links, not converted to points or polygons.
No verified coordinates or vector geometry were obtained. `lat`, `lon` and
`geometry` remain null, `publication_ready` is false, and coordinate jitter is
explicitly disabled. This is a genuine document inventory, not map-ready coverage.

## Adapter behaviour

Implements the four methods of `AyuntamientoAdapter`. Backfill and update both
refresh the whole single-page inventory. Stable ID `corella-pgm` represents the
same municipal instrument across attachment changes. Deduplicates by document URL
without a record/document limit. Uses reviewed section boundaries to exclude
forms, general information and street maps. Requires EMOT and PUM sections plus
the real memoria and normativa labels. Changed headings, incomplete sections,
unreviewed links, redirects, pagination markers and oversized responses fail
explicitly. HTTP errors propagate; output is replaced only after successful parsing.
There is no pagination on this reviewed source; no news archive or announcement
pagination is partially crawled. Licence methods return an empty disabled result.

## Validation and local evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
No dependencies or shared sources changed.

- `-m unittest municipio.test_corella -v`: six tests passed. Checks grouping,
  exclusion boundaries, null date/geometry semantics, Unicode labels, retention
  of 120 extra documents without truncation, URL deduplication, missing content,
  changed/nested sections, invalid document links, pagination rejection, snapshot
  replacement, disabled licences and manifest loading.
- Live `CorellaAyuntamientoAdapter.backfill_proyectos`: status `ok`, 1 record,
  76 source documents. No fabricated dates, granted licences or coordinates.
- `evidence/proyectos.jsonl` and `evidence/validation.json` hold actual live output
  and coverage limitations. `urbanismo-live.html` captures the adapter response;
  `urbanismo.html`, `peau09.html` and `transparencia.html` are research captures.
  `normativa.pdf`, `memoria.pdf` and first-page text extracts support the manual
  document review. Evidence is local and must not be committed.
