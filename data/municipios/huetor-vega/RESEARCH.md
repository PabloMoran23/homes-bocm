# Huétor Vega — Granada — INE 18101

Verified 2026-11-07 with the preinstalled Python runtime at
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
This adapter extracts planning instruments from document inventories, not a
granted-licence register. Coverage is partial and publication is disabled.

## Official source discovery

The current municipal homepage, <https://huetorvega.org/>, identifies the
Ayuntamiento de Huétor Vega, its Granada address, and an Urbanismo menu linking
the following two inventories. Both returned HTTP 200 in the live extraction:

- <https://huetorvega.org/normas-subsidiarias-nnss/>: original NNSS documentation,
  original plans, amendments, and current plans. All four sections are processed.
- <https://huetorvega.org/pgou-adaptacion-parcial-nnss/>: adaptation memorandum
  and plans. All tables, including continuation tables without headers, are
  processed as one instrument.

The linked electronic headquarters is
<https://huetorvega.sedelectronica.es/info.0>; its public transparency landing
page <https://huetorvega.sedelectronica.es/transparency/> returned HTTP 200 and
was captured. A working granted-licence inventory was not established. Neither
the headquarters landing page nor application forms are treated as licences.
News and procurement announcements are outside this adapter's extraction.

The historical BOJA notice at
<https://www.juntadeandalucia.es/boja/2016/155/37> concerns provisional approval
of a PGOU revision in 2016. It is distinct from the adaptation inventory and is
not used to claim the revision's current legal status, nor included as another
record in this bounded inventory scraper.

## Records and provenance

Live extraction produced **11 records with 30 unique PDF links**:

- One NNSS dossier groups 11 documents: approved text, fichas, five original
  plans and four current plans.
- Nine amendment instruments derive from seven linked BOP documents. The
  municipal label for the 2003 BOP names modifications 1, 3 and 7; these become
  three separate instruments sharing the same document link. The other six
  inventory entries each describe one amendment.
- One adaptation dossier groups its memorandum and 11 plans.

The shared document
<https://huetorvega.org/wp-content/uploads/2024/04/NNSS_Boletin_20031222.pdf>
was downloaded and inspected on pages 48–49. It confirms the three distinct
numbered modifications. Other notices in the same full BOP are not extracted:
the unit of discovery is the municipal inventory entry, not every item inside a
linked gazette. Each document retains its label, section, URL and inventory
provenance. Record IDs derive from the inventory URL for main dossiers and
document URL plus instrument number for numbered amendments. No invented
municipal expediente reference is supplied.

All 30 document URLs returned HTTP 200 and a PDF signature in independent live
streaming checks, recorded in `evidence/document-checks.json`. This confirms
document availability, not exhaustive interpretation of their contents.

## Dates, semantics and limitations

Seven explicit BOP publication dates are parsed from inventory labels and apply
to nine amendment records. `fecha_publicacion` is separate from `fecha_acuerdo`
and `fecha_aprob`; the latter fields and generic `fecha` remain null. Neither
the 2024 upload directory nor the memorandum's month/year label supplies a date
of approval. The 2003 PDF has an agreement date, but automatic PDF agreement
extraction is outside the implemented parser and is not copied into other acts.
No current processing phase or legal validity is inferred from an archive label.

These are real planning document dossiers. `source_entity_type: documento`
accurately describes this inventory's evidence; the shared entity policy marks
them as documents with no activity eligibility, rather than inventing an
expediente number. `publication_ready` is false. No verified project geometry is
extracted from the PDF plans: `lat`, `lon` and `geometry` are null. No centroid,
geocoding or coordinate jitter is used. Scheduled execution and licences are
disabled in the manifest.

The inventories are single-page tables with no observed pagination. The parser
consumes every table and attachment, rejects unknown sections and unaccounted
links, and fails if pagination appears. It does not impose a record/page cap or
silently truncate. Both inventories must parse before replacing the output.
Update is a complete snapshot refresh; it is not a chronological delta feed.
Changes in attachment URLs may change amendment identity and need review.

HTTP requests use a 40-second timeout and a bounded 4 MB HTML response, failing
on overflow. A custom `municipio-huetor-vega` User-Agent returned HTTP 403 during
validation; the standard Requests User-Agent returned HTTP 200. The adapter
therefore uses the ordinary Requests default without browser impersonation,
cookies, credentials or challenge handling. Unexpected redirect hosts fail.

## Validation

`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_huetor_vega -v`
passes five tests: document grouping and distinct modification identity, date
semantics, continuation tables, pagination/layout rejection, atomic snapshot
preservation on failure, manifest resolution and disabled licences.

A live call through `load_portal_adapter(load_manifest('huetor-vega'))` to
`backfill_proyectos` produced 11 records; shared entity policy status is `ok`,
with zero unknown records. Evidence is local under `evidence/`: actual
`proyectos.jsonl`, `validation.json`, HTML captures, the shared BOP PDF and
document availability checks. Evidence is not source material for the adapter
and is not to be committed. Only the four requested source files are added.
