# Sant Hilari Sacalm (INE 17164, Girona)

## Official sources and scope

Verified live on 2026-11-09 using the preinstalled batch virtualenv Python.
The official municipal [Urbanisme catalogue](https://www.santhilari.cat/categories_areastematiques/urbanisme/)
contains the published planning inventory and links to POUM detail pages. It
also contains licence application forms, service descriptions and a generic
explanation of the POUM. Those are excluded from records.

The adapter produces two instruments, never one project per attachment:

1. **Pla General Municipal d’Ordenació Urbana (PGM)**. The catalogue explicitly
   identifies this as the planning instrument for Sant Hilari Sacalm, definitively
   approved in 1994, subsequently redefined by approved amendments. Retain the
   stated year as `ano_aprobacion`; no day/month is supplied. Group the
   [normative text](https://www.santhilari.cat/wp-content/uploads/2020/01/plageneral.pdf)
   and [urban ordering map](https://www.santhilari.cat/wp-content/uploads/2020/01/Ordenacio_Sol_Urba_Gral_NoNormatiu.pdf).
   The map filename explicitly indicates non-normative character; it remains a
   supporting document, not a separate instrument or extracted geometry.
2. **POUM — Avanç de planejament**. The [advance page](https://www.santhilari.cat/areastematiques/avanc-de-planejament/)
   supplies the memorandum, initial strategic environmental document and two
   strategy maps. The [participation page](https://www.santhilari.cat/areastematiques/programa-de-participacio-ciutadana/)
   supplies the related participation programme, grouped into the same POUM
   instrument. Five attachments total. The published advance is substantive
   planning documentation, not evidence of final POUM approval. `fase` records
   the document stage only, without asserting current administrative progress.

The [generic POUM explanation](https://www.santhilari.cat/areastematiques/que-es-el-poum/)
was inspected and excluded: explanatory prose alone is not an additional plan.
The municipal navigation links to the [official transparency portal](https://www.seu-e.cat/ca/web/santhilarisacalm/govern-obert-i-transparencia),
but this adapter does not claim to cover that portal, the RPUC, historical
amendments, public works, procurement or all municipal planning proceedings.
No public granted-licence inventory was verified; licence forms confer no grant.

## Extraction and provenance

The scraper reads the live catalogue's scoped `.item-medium` planning cards,
requires the identified PGM narrative and attached PDFs, and discovers both POUM
detail links from those cards. All attached PDFs in the detail download sections
are retained, including documents added later; duplicate URLs within each
instrument are collapsed. Each document retains its title, URL and source page.
The PGM record uses the catalogue as provenance; the POUM retains both detail
source URLs. Stable instrument IDs do not change when attachment filenames do.

These are static unpaginated pages in the observed source. Pagination controls
or continuation links cause an explicit failure; there is no page/item/date
cutoff. Changed headings, missing documents, foreign document hosts or failed
HTTP requests also fail the snapshot before replacing an existing output.
Update refreshes the complete scoped snapshot and does not append duplicates.
Licences return disabled and zero records. No shared registry edits are needed:
the manifest identifies the importable adapter class directly.

`fecha`, `fecha_publicacion`, `fecha_acuerdo` and `fecha_aprob` remain null:
neither upload-directory dates, HTTP metadata nor retrieval dates are approval
or publication evidence. The PGM year remains year precision. No coordinates
are inferred from the town hall, municipality centroid or document titles;
geometry and coordinates are null and `publication_ready` is false. Schedule,
licences and missing-coordinate jitter are disabled in the manifest.

## Validation and limitations

Run from the workspace root:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_sant_hilari_sacalm -v
```

Five offline tests check grouping, deduplication, identity, date/geometry
semantics, form exclusion, changed/missing sources, foreign links, pagination,
manifest loading, repeat snapshots, disabled licences and preservation of prior
output on failure. Fixtures model source structure and are not extracted data.

A separate real call to `backfill_proyectos(Path('evidence/proyectos.jsonl'))`
with `capture_dir='evidence'` produced **2 live records with 7 document links**.
`evidence/validation.json` records live count, source URLs, retrieval time,
limitations and PDF HTTP checks. The HTML source captures and fetched PDFs are
local evidence only; documents are checked for successful responses and PDF
signatures, not parsed for legal dates, legal status or geometries.

Coverage is partial and tied to what this municipal catalogue currently
publishes. Neither the catalogue nor the scraper establishes a complete or
up-to-date consolidated legal planning history. PGM amendments are mentioned
collectively by the source but not separately enumerated here. The POUM advance
must not be interpreted as a granted licence, approved replacement plan or
executed public work. No records are synthesized from news or procurement.
