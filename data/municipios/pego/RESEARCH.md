# Pego — INE 03102, Alicante

Verified 2026-11-07 using the preinstalled batch virtualenv. Adapter implements a
complete snapshot of the **planning-document accordion** of the municipal
Urbanisme i Medi Ambient page, not a complete municipal activity history or a
consolidated legal planning register. Scheduling, coordinate jitter and licence
extraction are disabled.

## Official source discovery

- https://pego.org/ — official municipal site, identifying Ajuntament de Pego,
  Plaça de l'Ajuntament, Pego (Alacant), and linking its municipal departments.
- https://pego.org/area/urbanisme-i-medi-ambient/ — live HTTP 200, server-rendered
  inventory headed `Pla General Ordenació Urbana`. The reviewed accordion has
  six groups. Four contain the supported instruments; cultural protection and
  general regulations are explicitly excluded. No pagination was present in this
  inventory. All supported entries are read, without a record limit. New groups,
  missing groups, documents without instruments and detected pagination fail
  closed and require review instead of quietly returning a partial snapshot.
- https://pego.org/recursos/tauler-danuncis/ — live HTTP 200; directs readers to
  https://pego.sedelectronica.es/board. The electronic board is discovered but
  not crawled or claimed as covered by this implementation.
- https://pego.org/recursos/transparencia/ — live HTTP 200; links to
  http://pego.sedelectronica.es/transparency/. This separate inventory is not
  covered. No authentication was attempted.

## Extracted coverage and provenance

The live adapter emits **13 instruments with 41 unique document links**:

- PGOU revision: 9 documents (catalogues, memorandum, regulations, plans and BOP).
- Calvari I partial alignment plan: 1 DOGV document.
- Ten point modifications: MP 01, 02, 03, 04, 05, 06, 08, 11, 12 and 13.
  Missing modification numbers are not synthesized. MP 11 has no descriptive
  subtitle in the inventory; its original short title is retained.
- Special Plan No. 1, extension of public facilities for an indoor pool:
  3 documents.

Documents are grouped by their actual plan heading. Duplicate icon/text anchors
are deduplicated within that instrument, not converted into multiple projects.
IDs use the municipal instrument labels (MP number, special-plan number) or
reviewed stable names (PGOU revision, Calvari I); these are **not expediente
numbers**. `source_entity_type: documento` describes this grouped documentary
inventory honestly. Registry entity policy returns 13 documents, zero unknowns;
it does not mark these as activity-eligible granted acts.

Each document retains its original label, original href, resolved URL and the
municipal inventory URL as provenance. Elementor lightbox payloads are decoded
to preserve the actual image URL. Ten plan-image links point to
`pego.servidortigres.com`, an external host explicitly linked by the municipality;
these are labelled external rather than claimed to be municipal-hosted files.
Their availability is not verified. No URL is rewritten to an invented host.

Two linked municipal PDFs were downloaded successfully (HTTP 200, PDF signature)
as supplementary evidence:

- https://pego.org/wp-content/uploads/2025/11/BOP-135-1999-06-15.pdf
- https://pego.org/wp-content/uploads/2025/11/DOGV-3924-24.01.2001.pdf

The parser extracts **publication dates from BOP/DOGV/DOCV link labels only**.
Each belongs to its document; an instrument-level `fecha_publicacion` is set
only when all available dated labels have one distinct date. Multiple dates
remain in `fechas_publicacion_documentos`. No approval or agreement dates are
extracted from PDF contents: `fecha`, `fecha_acuerdo`, `fecha_aprob` and `fase`
remain null. Upload path `2025/11` is not a publication or approval date.

## Deliberate limitations

This is a historical inventory accessible today, with bulletin labels dating
from 1999–2009. It does not establish which instruments remain legally in force,
and does not include later changes merely because they appear in search results.
The page's separate public-participation/public-exhibition sections (Favara,
Calvari II and Penya Roja), cultural-protection entries, general regulations,
news and licence environmental-exhibition notice are outside this adapter's
explicit scope. A licence exhibition notice is not evidence of a granted licence.
No procurement announcements or unrelated news are emitted as projects.

The adapter downloads the inventory HTML; it preserves all linked documents but
does not download or semantically parse every PDF or image. Only two PDF targets
were independently checked here. The electronic board and transparency portal
need a separate investigation to extend coverage. No total municipal coverage,
construction commencement or project approval is inferred.

No verified geometry is supplied by this inventory. Coordinates and geometry
remain null and `publication_ready` is false; no centroids or jitter are used.
Updates refresh the whole inventory; no date cursor drops undated records. Output
is replaced atomically only after successful download and parsing. The optional
`portal.config.evidence_dir` captures the exact HTML used, without being enabled
in the committed manifest.

## Reproduction and evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Run parser/contract tests:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_pego -v
```

Six tests pass: document grouping and separate date semantics, rejection of
changed/missing sources and pagination, stable identities, no record truncation
(105 fixture instruments), download failure preserving prior output, and manifest
loading/disabled licences/update contract.

Live extraction uses `load_portal_adapter(load_manifest('pego'))`, optionally
sets `adapter.config['evidence_dir'] = 'evidence'`, then calls
`adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`. Final result:
13 real planning-document records, 41 retained links, registry policy status ok,
zero unknown classifications, no geometry. Local `evidence/validation.json`
records counts, source URLs, source hash and limitations. HTML captures, the two
PDFs, source checks, live result and test log are in `evidence/` and are not source
files for commit. No shared source files or dependencies were changed.
