# L'Aldea — INE 43904, Tarragona

Verified on 2026-11-09 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
One municipal adapter, with a deliberately partial planning-document snapshot.
Live extraction produced **2 records with 3 PDF attachments**. This is not a
complete municipal planning/works archive or a register of granted licences.

## Official source discovery

- https://laldea.cat/ajuntament/urbanisme — HTTP 200. Municipal urbanism index;
  its “Normativa d'Urbanisme Municipal” navigation link establishes the provenance
  of the municipal transparency inventory on seu-e.cat. Captured in
  `evidence/urbanisme.html`.
- https://laldea.cat/ajuntament/informacio-oficial — HTTP 200. Links to municipal
  public-information dossiers, contracting and official publications. Contracting
  links and general service/navigation links are not extracted as projects.
- https://seu-e.cat/ca/web/aldea/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/normativa-d-urbanisme
  — HTTP 200. **Actual implemented inventory**, with the text refós, planning map,
  general MUC viewer and mobility study. Page displays “Actualització: 28/09/2023”.
  That date describes page maintenance, not approval, agreement or publication
  of any individual instrument. No inventory pagination is present. The adapter
  rejects pagination rather than returning the first page only.
- https://seu-e.cat/ca/web/aldea/govern-obert-i-transparencia/accio-de-govern-i-normativa/normativa-plans-i-programes/memories-i-documents-dels-projectes-normatius-en-curs
  — HTTP 200. Current public-information listing contains an ordinance governing
  trenches and restoration of public domain, expediente
  `4390440003-2026-0003824`. This is a regulatory procedure, not evidence of an
  actual physical works project or a granted licence; excluded.
- https://seu-e.cat/ca/web/aldea/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/projectes-tecnics
  — guessed discovery route returned HTTP 404; not used as a source.
- https://dtes.gencat.cat/rpucportal/#/consulta/cerca — linked official general
  planning register search. Not enumerated by this adapter; no claim of complete
  RPUC coverage. Likewise the general MUC viewer is not an individual project.

## Records and attachment provenance

1. **Text refós de les Normes Subsidiàries de Planejament al terme de L'Aldea**.
   Normative text and its associated municipal planning map are grouped in one
   record, retaining both labels, roles and URLs:
   - https://seu-e.cat/documents/28831/6221824/NNSS/22b75a62-2363-4f88-8437-6468fb5c7f23
   - https://seu-e.cat/documents/28831/6447614/mapa+planejament.pdf/7f2a48c6-263a-445d-82f5-b155bc49c68c
   Both returned HTTP 200 with PDF content. Manual text inspection of the norms
   identifies DOGC 4405, **publication 2005-06-14**, an edict dated **2005-05-09**,
   and the commission's **agreement 2005-04-06**, expediente `2005/017006/E`.
   These three dates have distinct meanings. The scraper does not parse PDF text
   and therefore does not populate date/phase/expediente fields from this manual
   observation. This is a historically dated instrument still listed by the
   municipality, not proof that every subsequent amendment is consolidated.
2. **Estudi de Mobilitat Urbana Sostenible**.
   - https://seu-e.cat/documents/28831/15681284/projecte+EMUS.pdf.pdf/761ef3a7-6f8b-45a1-a8bd-6c0451561572
   HTTP 200, genuine 63,439,017-byte study PDF. Manual inspection identifies the
   municipality, requesting Ajuntament, Diputació de Tarragona provenance, Doymo
   authorship and edition “Setembre de 2022”. Signature 2022-12-20 and certified
   copy emission 2022-12-23 are not approval/publication dates. This is a mobility
   planning **study**, not a claim that proposed works were approved or executed.
   Approval status remains unknown (`fase: null`).

Each record retains the inventory URL, main attachment and all associated
`documentos` with source URL and SHA-256. Stable IDs derive from the canonical
main document URL. HTTP document links are normalized to HTTPS and the canonical
seu-e.cat host. No dates or coordinates are synthesized. The map remains a PDF
attachment; it is not converted to a municipal centroid or fabricated geometry.

## Implementation and limits

The HTML parser scopes extraction to the unique municipal content article with
the actual norms title, not menus or page feedback. It recognizes the reviewed
instrument labels, groups the map, rejects unexpected document provenance,
conflicting attachments, new unreviewed document labels, missing norms/map,
ambiguous inventory blocks and pagination. The optional mobility study can
vanish without changing the norms record ID. Every run refreshes the complete
single-page snapshot; update uses the same mechanism and makes no historical
incremental-coverage claim.

Requests use explicit timeouts, streaming size checks (3 MB HTML / 80 MB per PDF)
and HTTP status validation. All attachments must have a PDF signature before
output is atomically replaced. A failed document download preserves the prior
JSONL. Optional `config.evidence_dir` captures the exact inventory and PDFs used
by a run. No new runtime dependency is required; requests and BeautifulSoup are
already declared. `pdftotext` was used only for research, not by the adapter.

Dates are null because the inventory does not state instrument event dates and
PDF dates are outside the implemented parser. No granted-licence inventory has
been verified. `licencias.enabled=false`, `schedule.enabled=false`,
`geocode.jitter_missing=false`; geometry/coordinates are null and
`publication_ready=false`. The shared entity annotator reports 2 unknown entity
categories; these are not inferred as buildings or residential development.

## Validation and local evidence

- `python -m unittest municipio.test_l_aldea`: **4 tests passed**, covering grouping,
  unknown date/geometry semantics, stable identity, optional study removal,
  pagination/markup/provenance failures, loader integration, document validation,
  disabled licences and preservation of prior output on failure.
- Real extraction through `load_manifest`, `load_portal_adapter` and
  `backfill_proyectos`: status `ok`, **2 records**, 3 live PDF attachments checked.
- `evidence/proyectos.jsonl`: actual extracted records; `evidence/validation.json`:
  UTC capture time, `live_records`, source URLs, test result and coverage limits.
- `evidence/inventory.html`, `normativa.pdf`, `plano.pdf`,
  `estudio_movilidad.pdf`: captures produced by that adapter run. Additional
  discovery HTML/PDF/text captures are local research evidence.
- Evidence is local and excluded from source changes. Only the manifest, this
  research file, the adapter and its tests are added; no shared files,
  dependencies, publication systems or Git metadata are modified.
