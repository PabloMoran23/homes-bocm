# Ceutí — INE 30018, Murcia

Verified on 2026-11-07 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
This adapter extracts the official municipal planning document inventory, not
licences or a complete historical register. Scheduling and coordinate jitter are
disabled. All five records have `publication_ready: false`.

## Official source inventory

Source: https://ceuti.es/urbanismo/ (HTTP 200, live extraction and local HTML
capture). The municipal page separates ACTIVIDADES and OBRAS application forms
from the actual AVANCE MODIFICACION PUNTUAL IX PGMO and PGMO document sections.
It is a single document page: there are no result pages to truncate. The adapter
rejects pagination markers if they appear in future responses.

The following are instrument groups, not twelve separate projects:

- PGMO: Normas Urbanísticas, Plano General and Ordenación Estructural Modificada
  V03. The latter is retained as a general planning drawing under the source's
  PGMO section; the index does not explicitly identify its modification number.
  Its label says `pub. 13/03/2018`, which is not used as a plan approval date.
- Modification I: PLANOS_MOD_PUNTUAL_I and its BORM publication.
- Modification II: PG0903_02 MEMORIA MODIFICACION 2 v01d and PG0903_03 PLANOS
  MODIFICACION 2 V01. The memory identifies “MODIFICACIÓN PUNTUAL II” and carries
  an October 2012 drafting date. Neither that date nor the 2016 upload directory
  proves an approval or publication date.
- Advance of modification IX: BORM notice, modification project, initial strategic
  document and municipal public-information notice. The blank “Modelo solicitud
  inicio evaluación ambiental” is excluded. This is a genuine planning proposal,
  not a claim of definitive approval or execution of physical works.
- Plan parcial, usos y destinos del suelo: one linked PDF. Its first page
  identifies the Plan Parcial del Sector URSAE. The adapter preserves the index's
  broader label instead of hardcoding details from this research into live data.

All twelve actual document URLs and their original labels are retained in the
records' `documentos` arrays and in `evidence/validation.json`. Record IDs derive
from instrument identities, so a changed document upload URL does not generate
another instrument. No inferred expediente number or cadastral reference is used.

## Document checks and date semantics

Municipally hosted documents were downloaded without authentication and captured
locally. The following checks establish that this is real planning documentation:

- [IX BORM notice](https://ceuti.es/wp-content/uploads/2026/04/2026-1579-Anuncio-información-pública-avance-de-la-modificación-puntual-IX-del-PGMO-de-Ceutí.pdf):
  BORM 81, 2026-04-10, notice 1579. Plenary agreement **2026-02-26** approves the
  advance for access from RM-533 to the MAGAL industrial complex, former Anukka
  Foods area. The notice is dated 2026-02-27. These are three different dates.
- [Municipal IX notice](https://ceuti.es/wp-content/uploads/2026/03/Publicación_Anuncio_anuncio-Avance-Modificación-IX-PGMO.pdf):
  repeats the 2026-02-26 plenary agreement and is signed 2026-03-05. Signature is
  not BORM publication or definitive approval.
- [Plan parcial PDF](https://ceuti.es/wp-content/uploads/2026/10/Plan_parcial_usos_y_destinos_uso.pdf):
  BORM 49, publication **2011-03-01**, notice 3090. Definitive approval of Sector
  URSAE was agreed **2009-11-26**. The notice is dated 2011-02-04. Its 2026 upload
  directory does not date the instrument.
- [Modification I BORM](https://www.ceuti.es/wp-content/uploads/2016/10/PUBLICACIÓN-BORM-modificación-puntual-I-del-PGMO.pdf):
  BORM 109, publication **2015-05-14**, notice 5971. The approval order is dated
  **2015-04-17**, with dossier 170/11 stated in the PDF.
- [Modification II memory](https://www.ceuti.es/wp-content/uploads/2016/10/PG0903_02-MEMORIA-MODIFICACION-2-v01d.pdf):
  identifies the instrument explicitly; historical PGMO approvals in its background
  are not approvals of modification II.

The production parser reads the HTML index, not the PDF bodies. Consequently all
record date fields and `fase` remain null. The dates above are research evidence,
not hardcoded extraction values. No claim is made that every document represents
current consolidated law. No procurement notice or unrelated news was ingested.

## Implementation and limitations

`CeutiAyuntamientoAdapter` implements all four portal methods. Projects refresh
as a complete snapshot; licence methods explicitly return disabled and no records.
Only the two named planning sections are considered. Forms in ACTIVIDADES,
OBRAS and OTRAS SOLICITUDES are not granted licences. No public granted-licence
register was verified; the official sede search result is not used as a dataset.

The parser checks all five expected groups, minimum document counts and official
PDF hosts. Unknown PGMO links, changed headings, missing content, nonmunicipal
redirects and pagination cause failure before output replacement. Responses are
bounded to 3 MB with a 40-second requests timeout. Optional `capture_dir` saves
the actual response used by the adapter. Document URLs are retained, but ongoing
PDF availability is not checked on every snapshot refresh.

Coverage is partial: the currently linked municipal planning documents only.
Other instruments, historical changes, works and granted licences are outside
this inventory. No coordinates or verified vector geometry were extracted from
the schematic PDF plans. `lat`, `lon` and `geometry` remain null; no centroid or
random offset is substituted. The shared entity policy annotates these inventory
records as unknown (5/5); extraction readiness does not imply activity eligibility.

## Validation and local evidence

- `python -m unittest municipio.test_ceuti -v`: **7 passed**. Covers document
  grouping, form exclusion, stable IDs, date/geometry semantics, missing/changed
  source rejection, pagination rejection and disabled licences.
- Live `load_portal_adapter(load_manifest('ceuti')).backfill_proyectos(...)`:
  **5 records, 12 document links**, shared entity annotation completed.
- `evidence/proyectos.jsonl`: actual live records.
- `evidence/validation.json`: record count, source URLs, limitations, policy report,
  timestamp and SHA-256 of the live source capture.
- `evidence/urbanismo-live.html`: exact adapter response. `urbanismo.html` is the
  initial research capture. `doc-00` through `doc-06` PDFs/texts and
  `estructura.pdf`/`.txt` are research captures. PDF text checks used the already
  installed `pdftotext`; the adapter does not require that executable.

Evidence is local and is not source to commit. No shared source files,
dependencies, credentials, databases or deployment resources were changed.
