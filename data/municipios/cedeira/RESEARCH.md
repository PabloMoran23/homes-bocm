# Cedeira — INE 15022, A Coruña, Galicia

Verified on 2026-11-09 using the preinstalled Python environment. This adapter
covers the municipal planning-document inventory, not all municipal projects or
works. Live extraction produced **2 instruments with 80 distinct PDF links**.
Independent acceptance is pending; publication_ready remains false.

## Official sources inspected

- [Municipal planning index](https://www.cedeira.gal/documentos-municipais-de-interese/plan-de-urbanismo/)
  returned HTTP 200 and links three instrument-document sections. All three are
  fetched; there is no pagination in the inspected inventory or detail pages.
- [Interpretación do PXOM 2008](https://www.cedeira.gal/documentos-municipais-de-interese/plan-de-urbanismo/interpretacion-do-pxom-2008-2/)
  exposes 14 PDF links: agreement, transitional-regime application and plans.
- [Interpretación do PXOM 2023](https://www.cedeira.gal/documentos-municipais-de-interese/plan-de-urbanismo/interpretacion-do-pxom-2023/)
  exposes 5 PDF links: certification, technical report and plans. These and the
  2008 documents belong to one PXOM interpretation collection, with both source
  sections retained. They are not 19 separate projects.
- [Modificación puntual nº2 — centro de saúde na rúa Río da Veiga](https://www.cedeira.gal/documentos-municipais-de-interese/modificacion-puntual-no2-do-plan-xeral-de-ordenacion-urbana-centro-de-saude-na-rua-rio-da-veiga/)
  exposes 61 distinct PDF URLs for the planning amendment: indices, reports,
  information and proposed-ordering plans, regulations, economic studies and
  environmental assessment. All are retained in one instrument. The explicit
  document label “APROBACIÓN INICIAL” supplies the phase of this documentation;
  it does not establish the instrument's latest legal status or a granted works
  licence for the health centre.
- The index links [SIOTUGA's legacy municipal inventory URL](https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=15022).
  Direct HTTP 200 returned a search form listing all municipalities, without
  instrument rows for Cedeira. This response is captured in discovery-1.html;
  it is not treated as a planning record or as proof that no other plans exist.

## Provenance and semantics

The source heading is retained for each section. Document objects retain their
source page, section heading and all distinct anchor labels for the same URL.
Repeated links are deduplicated by URL, not by filename or title: different PDFs
with identical labels remain distinct. The amendment page links the same PDF
under both ordering and historic orthophoto labels; both labels are preserved,
without correcting or inventing a destination. Offsite image placeholders on the
2008 page are excluded. The source's repeated introductory paragraph on the
2008 page refers to a 2023 agreement; it is retained as source description and
is not interpreted as the approval date of the 2008 documentation.

All generic, publication, agreement and approval dates remain null. Heading
years, filenames (including 26.05.2023) and upload directories (2025/07) are not
parsed into event dates. No coordinates or geometry are inferred from maps,
addresses or a municipal centroid. The documents' PDF contents are not parsed.
The full original PXOM is outside this municipal document collection.
No procurement notices, unrelated news or application forms become records.
Licencias, scheduling and missing-coordinate jitter are disabled in the manifest.

## Implementation and validation

The manifest follows municipio/manifest.py and the existing municipal manifests;
the adapter implements AyuntamientoAdapter and loads through the unmodified
registry. Backfill and update fetch a complete snapshot: the index plus every
reviewed linked section. Empty inventories, changed headings, unexpected hosts,
missing PDF links, unknown instrument types and pagination raise errors before
replacing the output. There is no page or record slicing and no date watermark.
A failed refresh does not write a partial new snapshot.

Executed:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_cedeira -v
```

Five tests passed, covering instrument grouping, document deduplication and label
retention, unknown dates/geometry, changed/empty sources, pagination in both page
types, missing or foreign PDF links, registry loading and full snapshot updates.
A real extraction through load_portal_adapter(load_manifest('cedeira')) returned
2 records (19 and 61 PDFs); shared entity policy annotation returned status ok
with both categories unknown. This is extraction evidence, not acceptance or
publication approval.

Local, uncommitted evidence: evidence/proyectos.jsonl, evidence/validation.json,
evidence/captures/ (all four live pages plus URL sidecars), discovery HTML,
detail HTML and representative PDF checks. The source index and detail pages
supply the inventory; sample PDF downloads validate representative links only,
not the accessibility or contents of every linked PDF.
