# Boqueixón — INE 15012, A Coruña, Galicia

Verified live 2026-11-09. A deliberately partial municipal planning inventory:
two instruments, five retained document/inventory links. No licence records,
geometry, or inferred dates. Scheduling and coordinate jitter are disabled.

## Official sources

- https://www.boqueixon.gal/servizos-municipais/urbanismo/ — HTTP 200.
  Current municipal service page, with a discrete Documentación section.
  Names the NNSS 1996 and modification 4, concerning road setbacks, at initial
  approval stage. The latter has one agreement certificate, an annex, and PDF
  and editable ZIP packages. These are one instrument, not four projects.
  The annex is supporting documentation, never a granted licence.
- https://www.boqueixon.gal/pxom-nnss-1996/ — HTTP 200. Visible municipal notice
  explicitly says the PXOM was annulled by judgment and the NNSS 1996 are in
  force. Required by the live parser before emitting the NNSS record.
- https://siotuga.xunta.gal/siotuga/inventario?inv=1&idconcello=15012 — HTTP 200.
  Official regional inventory linked from Urbanismo (the municipality's original
  HTTP link is retained verbatim). The fetched HTML is an interactive search
  shell, with no dossier rows. This adapter does not claim to extract the
  regional inventory, its full planning history, or its geometry services.
- https://www.boqueixon.gal/concello/pxom/ and
  https://www.boqueixon.gal/2012/01/06/plan-xeral-de-ordenacion-municipal/ — HTTP
  200. Historical PXOM category/article. Excluded from extraction: its 2012
  publication and old document links do not establish a currently valid plan,
  especially given the current explicit annulment notice.

The modification certificate was downloaded for research:
https://www.boqueixon.gal/wp-content/uploads/2021/11/2021_U032_000001_Certificado-Acuerdos-EXPEDIENTE-2021_U032_50447.pdf
(HTTP 200, PDF). Its first page identifies expediente 2021/U032/000001 and a
plenary agreement on 9 June 2021. It also explains that the 2015 PXOM was annulled
in 2020. This date is an agreement date, not the publication date or the date in
the upload directory. The adapter extracts HTML only, so exact date fields remain
null rather than embedding this research observation as a parser constant. The
phase is the stage of the linked document, not a guarantee that no later approval
exists elsewhere. Publication dates of the instruments were not established.

All four modification links returned HTTP 200 on HEAD verification, with PDF or
ZIP content types. The large ZIPs (16,070,518 and 136,449,705 bytes) were linked,
not downloaded or expanded. The certificate PDF and its pdftotext output are in
local evidence. No external runtime dependency was added to the adapter.

## Extraction contract and limits

The parser scopes itself to the municipal document section, validates the exact
15012 inventory link, and groups the certificate, annex and both MP04 packages.
Stable identities describe instruments and survive document URL changes.
Duplicate document URLs are removed. Unexpected documents, changed approval
labels, missing current-status notices, and pagination produce errors, allowing
review instead of silently skipping new content. The verified inventory is a
single page with five document links and no pagination. The update method
refreshes that complete small snapshot; no historical incremental coverage is
claimed. No limit on record count or pagination cap is used.

The service descriptions and licence application procedures are not a public
register of granted licences. News and procurement announcements are not used.
Physical public works, other modifications, regional dossiers, and historical
annulled plans remain outside this implementation's coverage. No source geometry
is extracted: lat/lon/geometry remain null and publication_ready is false.

## Validation and local evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_boqueixon -v`: six tests passed. Covers grouping,
  provenance, unknown dates/geometry, wrong INE, missing content/status, pagination,
  unexpected documents, deduplication, stable IDs, manifest loading, snapshot
  update and disabled licences.
- Real extraction through `load_portal_adapter(load_manifest('boqueixon'))`, with
  evidence_dir configured locally: two records, shared entity-policy status ok.
  Entity categorization is unknown for both planning instruments; this does not
  imply a physical building project category.
- `evidence/proyectos.jsonl`: actual live records and all five links.
- `evidence/validation.json`: live_records, source_urls, limitations, parser-test
  result, runtime, extraction timestamp and HTTP document checks.
- `evidence/urbanismo.html`, `nnss.html`, `siotuga.html`, `pxom.html`,
  `pxom-detail.html`, `agreement.pdf`, `agreement.txt`: source captures.

Evidence is local only. Exactly the municipal manifest, research, adapter and
parser test source files are added; no shared source or dependency edits.
