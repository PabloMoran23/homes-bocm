# Sant Fost de Campsentelles — INE 08209, Barcelona

Verified live on 2026-11-07. This adapter extracts one genuine municipal planning
instrument from the current official document inventory. Coverage is deliberately
partial: the POUM and its normative documents, not all municipal planning,
physical works, historical dossiers or granted licences. The three documents are
one instrument, not three projects. Scheduling and missing-coordinate jitter are
disabled. No geometry is available in the extracted inventory, so
`publication_ready` is false.

## Discovery and official sources

- https://www.santfost.cat/ajuntament/informacio-oficial/urbanisme/ — HTTP 200;
  current urbanism index links to Planejament urbanístic and Normes urbanístiques.
- https://www.santfost.cat/ajuntament/informacio-oficial/urbanisme/planejament-urbanistic.html
  — HTTP 200; explanatory page, updated 2025-02-11, with generic RPUC and MUC
  viewer links. These generic links are not individual planning records. The
  linked RPUC root (`https://dtes.gencat.cat/rpucportal/#/inici`) is a discovery
  pointer, not an extracted dossier; the adapter does not claim registry coverage.
- https://www.santfost.cat/ajuntament/informacio-oficial/urbanisme/normes-urbanistiques.html
  — HTTP 200; actual document inventory in `#page-documents`, headed Normes
  urbanístiques. Page update is 2026-10-13, not a planning approval/publication
  date. Its three links are grouped under the named POUM:
  - https://www.santfost.cat/media/repository/informacio_oficial/urbanisme/SF_MEMORIA_TRF.pdf
    — municipal POUM document (page reports 73.6 MB); retained as a link, not
    downloaded during this run.
  - https://www.santfost.cat/media/repository/informacio_oficial/urbanisme/NORMES_TEXT_REFOS_POUM_DOGC_6466_25_09_2013.pdf
    — Catalan normative text; HTTP 200 application/pdf, 679422 bytes; captured
    and inspected with the already installed `pdftotext` for research.
  - https://www.santfost.cat/media/repository/informacio_oficial/urbanisme/NORMES_TEXT_REFOS_POUM_DOGC_6466_25_09_2013_castellano.pdf
    — Spanish normative rendition; retained as a link, not downloaded.

The Catalan PDF is DOGC 6466, published 2013-09-25, CVE-DOGC-A-13255043-2013,
expedient 2006/024366/B. Its first page distinguishes definitive approval on
2012-10-31, conformity to the consolidated text on 2013-07-22, and an edict dated
2013-09-12. These are different legal events. This HTML-only adapter does not
parse PDF contents or infer dates from filenames; all record date fields and
phase remain null. Those research observations must not be confused with
adapter-extracted date values. The inventory itself identifies neither a legal
event date nor an expediente number.

## Implementation and limits

Inspected `municipio/manifest.py`, `municipio/adapters/portal.py`, registry loading,
and existing Manlleu/Hernani examples before implementation. The manifest uses
the existing module/class adapter contract and identifies the exact municipality,
province and INE code. No shared code or dependencies were changed.

The adapter retrieves the fixed official inventory with a 30-second timeout and
a 2 MB streamed response limit. It requires the expected page heading, the named
POUM and normative attachments inside the document section. URLs must be HTTPS
PDFs within the official municipal media repository. Links are preserved with
labels and parent source provenance; duplicate links are deduplicated. Stable
identity derives from the instrument inventory page, independent of PDF language
or modification date. Updates refresh the whole single-page snapshot.

The inspected document section is unpaginated. Pagination markers or next links
raise an error, rather than silently truncate. Unknown document labels also
raise an error to avoid silently discarding new planning instruments or treating
unrelated attachments as the POUM. Changed/login/navigation-only markup and
external attachment URLs fail validation. Licence application forms, tenders,
service descriptions and unrelated news are not records. No verified granted
licence register was found in these urbanism inventories; licence extraction is
disabled and returns no records. This is not a claim to have searched every
municipal notice or administrative file.

No coordinates, municipal centroid or random offset are generated. Map geometry
and wider municipal coverage remain unresolved. The HTML inventory does not
prove that all subsequent amendments to the POUM are included.

## Validation and local evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_sant_fost_de_campsentelles -v`: six tests passed;
  document grouping/deduplication, null event dates and geometry, non-record
  rejection, pagination detection, unexpected documents/hosts, manifest adapter
  loading/disabled licences, and full snapshot updates.
- Live `load_portal_adapter(load_manifest(...)).backfill_proyectos(...)`: status
  ok, one actual instrument, three document links. Existing entity annotation
  reports unknown entity type; no residential classification is asserted.
- `evidence/proyectos.jsonl` contains the live output; `evidence/validation.json`
  contains record count, source URLs, timestamp, test result and limitations.
- Source captures: `evidence/urbanisme.html`, `planejament.html`, `normes.html`,
  `live-normes.html`, `normes-cat.pdf`, and its `normes-cat.txt` extraction.
  Evidence remains local and is not part of the four source files.
