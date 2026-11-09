# Fisterra — INE 15037, A Coruña

Verified 2026-11-09. One adapter covers two genuine planning instruments from the
municipal urbanism inventory. It is a partial document snapshot, not comprehensive
municipal works, an up-to-date legal status register, or granted licences.

## Official inventories

- https://concellofisterra.gal/portal_cidadan/presentacion_urbanismo/gl — municipal
  index linking PXOM, PEPRICH and two physical-work pages.
- https://concellofisterra.gal/portal_cidadan/pxom/gl — named PXOM, explicit order
  date 05/08/2019 and BOP publication 07/08/2020. Three document categories:
  `descargas_areas/gl/130` (ordering plans), `/131` (norms), `/132` (catalogue).
  The scraper follows all categories and retains 42 unique PDF links including BOP.
- https://concellofisterra.gal/portal_cidadan/peprich/gl — named historic-centre
  special plan, page narrative says new initial approval following substantial
  modifications. Seven categories `/160`, `/161`, `/162`, `/163`, `/165`, `/166`,
  `/170` under `https://concellofisterra.gal/portal_cidadan/descargas_areas/gl/`.
  All 63 unique PDF links retained, including subordinate catalogue/block links
  outside h3 headings. No agreement/publication date is stated in the page.
- https://concellofisterra.gal/portal_cidadan/humanizacion_recta_da_anchoa/gl and
  https://concellofisterra.gal/portal_cidadan/rehabilitacion_faro_fisterra/gl — HTTP
  200 but main content only has a heading. Excluded, insufficient project evidence.
- https://concellofisterra.gal/portal_cidadan/plans_proxectos/gl — mixed transparency
  inventory with funding agreements for Mixirica and Mercado Cultural, Portos and
  property-cession agreements, equality/LEADER plans and an aggregated 2015 works
  PDF. Outside this adapter's two planning instruments; not promoted to project
  records from agreement titles. This inventory is not claimed as covered.
- https://sede.concellofisterra.gal/sxc/es/procedimientosytramites/tramites/Comunicacionpreviadeobra_N
  — application procedure, not evidence of a granted licence; excluded.

## Provenance and conflicting labels

https://bop.dacoruna.gal/bopportal/publicado/2020/08/07/2020_0000005430.pdf
was downloaded (HTTP 200, PDF, 207 pages). Its opening heading mentions an order
of 5 August **2020**, but the body expressly gives definitive approval by order of
5 August **2019**, DOG publication 4 September 2019 and registration 14 July 2020.
The municipal PXOM inventory also gives 2019. The record parses the inventory's
2019 approval and 2020 BOP publication separately. No generic date or agreement
signature date is inferred; 4 August 2020 edict signature is not plan approval.

The sampled PEPRICH memory
https://concellofisterra.gal/media/documentos/01_memoria_lopd_signed_compressed.pdf
has a cover labelled “Aprobación provisional e definitiva”, September 2020,
whereas its municipal page says new initial approval. The record preserves the
page's stated stage, documents the discrepancy and makes no claim about present
legal effectiveness. A cover label/month is not an approval agreement/date.

Sampled PXOM index PDF
https://concellofisterra.gal/media/documentos/FIS_ADP08_05_PL_ORDENACION_INDICE_signed.pdf
also returned HTTP 200 with PDF bytes. Only these three PDFs were downloaded for
content checks; the other attachment links are preserved, not individually verified.

## Implementation and limits

Index verifies the two plan links; detail parsing requires the correct heading and
substantive narrative. Navigation, licence forms and empty works pages do not
become records. Each instrument is one stable record, with complete recursively
visited category inventories and deduplicated attachment URLs. Every document
retains its listing source URL and municipal/BOP provenance. No currently exposed
pagination was found. Pagination controls cause a hard failure requiring crawler
review; a category expansion over 100 pages also fails. No partial JSONL replaces
a previous snapshot after a fetch/parser failure. Update refreshes the snapshot.

No coordinates or vector project geometry were verified. PDF maps are documents,
not extracted geometry. `lat`, `lon`, `geometry` remain null and
`publication_ready=false`. Schedule, licence ingestion and missing-point jitter
are disabled. No dates are inferred from file names, crawl time or document covers.

## Validation

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_fisterra -v`: 6 passing tests covering date semantics,
  initial stage, null geometry, all subordinate PDF links/deduplication, pagination
  rejection, complete grouping and failure preserving existing output, manifest and
  disabled licences.
- Real `FisterraAyuntamientoAdapter.backfill_proyectos` extraction: 2 records,
  13 HTTP source pages, 42 + 63 attachments, zero inferred coordinates.
- Local `evidence/proyectos.jsonl`, `evidence/validation.json`, HTML captures under
  `evidence/live_sources/`, three sample PDFs and text extracts support review.
  Evidence is local, outside the four source files.
