# Albuixech — INE 46014, Valencia

Verified against live official sources on 2026-11-09. This adapter extracts a
snapshot of the public municipal **normas subsidiarias inventory**, with four
instruments and all 22 linked documents. It does not establish that every
instrument is legally in force, or provide complete municipal planning coverage.

## Discovery and official inventories

- https://albuixech.es/urbanisme-i-medi-ambient/ identifies the official urbanism
  transparency sections.
- https://albuixech.es/planejament-urbanistic-i-normativa-urbanistica/ links to
  https://albuixech.sedelectronica.es/transparency/89fdd654-a1bd-4648-9edf-89aae7be6e37/.
  This parent inventory advertises 24 planning entries, nine regulatory entries,
  and zero environmental plans. Its revision label (28/09/2026) is a portal
  maintenance date, not any instrument's publication or agreement date.
- The planning folder resolves through its public navigation action to
  https://albuixech.sedelectronica.es/transparency/6b558ca4-37b4-4ebf-9fb0-9d77b2e06c18/.
  It contains two external cartographic resources (ICV and the regional viewer)
  and the 22-document NNSS folder. Cartographic resource links are not projects.
- The NNSS folder resolves to
  https://albuixech.sedelectronica.es/transparency/c7fa40f1-3e45-4961-8f45-1a6f81eb76df/.
  This is a real inventory of municipal planning documents, not a licence form
  catalogue or a news search.
- https://albuixech.es/plans-programes-i-estudis-durbanisme-i-ambientals/ links to
  https://albuixech.sedelectronica.es/transparency/91e5b19a-869e-4afd-8854-f9c17a5e97aa/,
  which returned “No se han encontrado elementos”. No records inferred.
- The home-page Urbanismo link resolves to the regulatory section
  https://albuixech.sedelectronica.es/transparency/52c350c9-5a32-4c95-bccc-8ab1b82bde64/.
  Its general regional-register and legislation links are not additional projects.
- https://albuixech.es/plans-i-programes/ points to a broader institutional plans
  section, outside this adapter's deliberately bounded NNSS scope.

## Extracted instruments and document provenance

| Instrument (source folder title) | Stable municipal folder | Documents |
| --- | --- | --- |
| NORMES SUBSIDIÀRIES | https://albuixech.sedelectronica.es/transparency/f5a24581-b28a-426c-bdf4-3643d1e5cf17/ | 13 |
| MODIFICACIÓ DE NORMES SUBSIDIÀRIES ART.15 POLÍGON INDUSTRIAL | https://albuixech.sedelectronica.es/transparency/45fb05a1-1478-47e7-83d8-c3b23d8c4c90/ | 4 |
| MODIFICACIÓ DE NORMES SUBSIDIÀRIES Nº3 ECOPARQUE | https://albuixech.sedelectronica.es/transparency/662e4193-723e-49ce-8bfa-43222495f15e/ | 2 |
| MODIFICACIÓ DE NORMES SUBSIDIÀRIES Nº1 | https://albuixech.sedelectronica.es/transparency/95c6ea92-5ccd-4ae5-88a0-290c9106be0e/ | 3 |

One output record per official instrument folder; plans, memory, regulations,
ACUERDO and BOP attachments stay grouped under `documentos`. Source titles and
stable official `/preview-document/<uuid>` links are retained alongside the
listing page that exposed each link. The scraper does not parse PDF contents.
Filename labels such as `46014-1000 1986-0085` are preserved as titles, not invented
municipal expediente numbers or dates. Record IDs hash the stable folder URL.

The NNSS folder initially shows ten documents. Its public “Mostrar más” control
returns Wicket XML containing three more documents, including ACUERDO, BOP and
MEMORIA. The adapter follows the public action in the same anonymous HTTP
session and parses component HTML without executing JavaScript. It continues
until there is no more control. Advertised document counts are checked per
instrument and against the parent NNSS count. Loops, no progress, count mismatch,
unexpected nesting or new unsupported pagination fail before replacing output.
Updates refresh the complete scoped snapshot; no date-based incremental cursor.

## Semantics and limitations

The record represents a named planning instrument evidenced by its official
folder and supporting documents. It does not claim a granted building licence,
a physical construction start, a planning approval stage or an approval date.
`fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` and `fase` remain null.
The portal's live clock, revision labels, upload paths and filename years are
never substituted for those dates.

The official inventory has no verified machine-readable project geometry.
`lat`, `lon`, `geometry` remain null; no municipal centroid or jitter is used.
`publication_ready=false`, `schedule.enabled=false`,
`geocode.jitter_missing=false`, and `licencias.enabled=false`.

This is partial coverage: it does not crawl historical municipal posts, all
regional-register instruments, PGE documents outside this NNSS inventory,
procurement announcements, all public works or personal licence files. A newer
regional environmental determination for the PGE surfaced in discovery; that
separate plan is not merged with these NNSS records or asserted approved.
The shared entity policy classifies these four records as pending identity
review (`insufficient_identity_evidence`); no expediente is fabricated to force
activity eligibility. This does not prevent preserving the real planning
inventory, but these rows are not publication-ready activity records.

## Validation and reproducibility

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_albuixech -v`: parser/contract tests, including
  XML pagination, grouping, missing dates, rejecting login/changed content,
  excluding generic external links and preserving output on incomplete coverage.
- Live extraction via `load_manifest('albuixech')`, `load_portal_adapter(manifest)`
  and `adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`: four records,
  22 documents, seven live requests including the second document page.
- Set `adapter.config['capture_dir']='evidence/live'` to retain response captures.
  `evidence/validation.json` records `live_records`, `source_urls`, limitations,
  capture paths/hashes, extraction timestamp and shared entity-policy result.
  `evidence/proyectos.jsonl` contains the actual live records. Discovery HTML
  captures also live under `evidence/`. Evidence is local and uncommitted.

No dependencies or shared sources changed. No credentials, private data,
database, deployment or publishing operations are needed or used.
