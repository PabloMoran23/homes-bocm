# Mont-roig del Camp — INE 43092, Tarragona

Verified live on 2026-11-07 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
One municipality adapter, with deliberately partial current-inventory coverage.
Scheduling and licences are disabled; missing coordinates are never jittered.

## Official sources

The [municipal planning index](https://mont-roig.cat/lajuntament/arees/urbanisme-i-territori/ordenacio-urbanistica-del-municipi/)
and municipal navigation distinguish documents in force (POUM, modifications,
derived planning, management) from documents in public information. The adapter
covers these two official public-information inventories, both HTTP 200:

- [Projectes municipals](https://mont-roig.cat/lajuntament/arees/urbanisme-i-territori/ordenacio-urbanistica-del-municipi/documents-en-tramit/informacio-publica/projectes-municipals/):
  one named urbanization project, “Projecte d’urbanització de l’entorn del cotxe
  restaurant”, with its signed project PDF. The surrounding text explicitly says
  public information. There is no municipal expediente number on this heading.
- [Planejament urbanístic](https://mont-roig.cat/lajuntament/arees/urbanisme-i-territori/ordenacio-urbanistica-del-municipi/documents-en-tramit/informacio-publica/planejament-urbanistic/):
  three genuine urbanization projects for Càmping de les Arts: roundabout
  (13218/2026), CN-340 access road (13220/2026), exterior road (2639/2026).
  Each heading owns an edict and technical project link. These are three distinct
  municipal dossiers, not seven documents represented as seven projects.

All seven retained PDF links returned HTTP 200, `application/pdf` and PDF magic
bytes in a separate live document check. Full edict captures and extracted text
are in local evidence. The roundabout edict describes initial approval of a
physical urbanization project promoted by CAMPING CAR, S.L.; it is not a tender
announcement or a granted building licence. The inventory category name is not
used as the record type: these records are urbanization projects.

## Semantics and limits

The roundabout and exterior road headings explicitly label their edicts
“Aprovació inicial”; the access road heading says “Exposició pública”. Those
labels determine the HTML-derived phase. Public-information labels do not prove
that the statutory consultation period is still open on the crawl date, or that
no subsequent approval exists elsewhere.

No dates are populated by this HTML-only adapter. For example, the captured
roundabout edict separately states a JGL agreement on 7 September 2026 and an
electronic signature on 8 September 2026; the text refers to subsequent bulletin
publication. Those are different events. The parser does not read PDFs and does
not substitute a signature date, page metadata, year in a dossier number, or
crawl date for agreement or publication. `fecha`, `fecha_publicacion`,
`fecha_acuerdo`, and `fecha_aprob` remain null. PDF extraction/date enrichment is
outside this implementation's coverage.

Each record retains its inventory URL, document labels and URLs, and document
source URL. Duplicate anchors for the exterior-road edict (the word “Arts” is
split across two anchors) are joined into a single document. Stable IDs derive
from the actual municipal expediente or, for the unnumbered project, its source
title. Document replacements do not change project identity. Conflicting entries
for one identity cause extraction to fail.

The two pages are static, unpaginated inventories. Every direct project heading
and subsequent attachment is processed; no record cap is applied. Pagination
markup, unknown headings, absent public-information context, missing documents,
unexpected redirects, nonofficial attachment URLs, empty inventories and
oversized responses cause errors. Output is replaced only after both pages
succeed. Updates refresh this full snapshot and do not imply historical coverage
or deletion of instruments that leave public information.

The broader documents-in-force inventory, other management instruments, public
notice board, historical bulletins, and any later approvals are not harvested.
The public notice-board link is retained in the captured source HTML, but is
not itself a project. No licence application, unrelated news or procurement
announcement is emitted as a project or granted licence.

No verified geometry is available from the parsed HTML. Coordinates and geometry
remain null, and `publication_ready` is false; no municipal centroid or guessed
location is substituted. The source PDFs may contain plans, but extracting and
georeferencing those plans requires additional work.

## Validation and local evidence

- `python -m unittest municipio.test_mont_roig_del_camp -v`: seven tests pass.
  Tests cover grouping, stable identity, phase/date semantics, no invented
  coordinates, rejection of forms/empty/changed sources and pagination,
  preservation of existing output after a network failure, and manifest flags.
- Real `MontRoigDelCampAyuntamientoAdapter.backfill_proyectos` execution:
  four unique records, seven retained document URLs, all INE 43092.
- `evidence/proyectos.jsonl`: actual live adapter output.
- `evidence/validation.json`: live count, source URLs, extraction time, limitations
  and parser test result.
- `evidence/inventory-0.html`, `inventory-1.html`: exact adapter source captures;
  `index.html`, `projects.html`, `planning.html`: discovery captures.
- `evidence/document_checks.json`: status, final URL, content type and PDF header
  checks for all seven attachments. `edict-0`, `edict-2`, `edict-4` PDF/text files
  capture the three municipal edicts.

Evidence is local and excluded from source delivery. No shared source files,
dependencies, database or deployment configuration were changed.
