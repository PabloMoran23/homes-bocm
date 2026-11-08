# Vidreres — INE 17213, Girona

Verified anonymously on 2026-11-08 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
This adapter extracts real planning-instrument document resources from the
municipality's currently accessible inventory. It does not establish their present
legal validity, approval dates or construction activity. Scheduling, licences and
coordinate jitter are disabled; `publication_ready` is false.

## Official source discovery

- https://vidreres.cat/pgou/ — HTTP 200. Dedicated municipal planning inventory,
  headed “Aquí trobaràs tota la documentació relacionada amb el PGOU de Vidreres”.
  Four sections: Documents PGOU, Modificacions PGOU, Plans especials and Altres.
  The displayed publication date is 7 July 2021; structured page metadata also
  reports modification in November 2021. Neither is an instrument agreement date.
  A live inventory is not proof that it includes later amendments.
- https://seu-e.cat/ca/web/vidreres/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  — HTTP 200. The municipal transparency inventory delegates to the official
  RPUC and MUC, specifically selecting municipality 17213. It contains links,
  not an extractable table of municipal instruments in the inspected response:
  https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=17213
  and http://dtes.gencat.cat/muc-visor/AppJava/home.do?municipi=17213&set-locale=ca.
  Those inventories are discovery references, not crawled by this adapter.
- https://vidreres.cat/e-tram/ — discovered municipal application-form directory;
  search results identify licence applications, not granted licences. Excluded.
- Searches also surfaced council-minute PDFs and procurement documents. Neither
  was substituted for a complete projects or granted-licence inventory. No news
  feeds, procurement announcements, generic ordinance or form entries are emitted.

## Extraction and provenance

The complete single-page PGOU inventory yields **14 records**:

- One PGOU resource grouping its 14 component documents, including norms,
  classification/ordering maps and the expressly informational 2014 composite map.
- Ten separately named PGOU modifications.
- Two special plans (rural-house catalogue and drinking-water supply).
- One partial plan, PPU SUS 4.

The standalone “Plànol delimitació Vidreres” map under Altres is excluded because
the label alone does not identify a planning instrument. It is recorded among
`excluded_inventory_entries`. Normative sections of the PGOU remain attachments
of the PGOU instead of becoming fourteen artificial projects.

Every document retains its original link, full paragraph label, anchor text,
municipal source URL and explicit municipal-link provenance. Google Drive URLs
are retained because the official municipality links them; their hosting does
not independently prove their contents or approval. A representative municipal
PDF (`9-Normativa-clau-4b-La-Goba.pdf`) returned HTTP 200/application-pdf. The
linked main PGOU Google Drive viewer returned HTTP 200. Both were captured;
not every attachment was downloaded or read. No login or credentials were used.

A source defect is preserved: the “MP PGOU sus 8” paragraph has three anchors.
The first and last reuse the SUS 2 Drive file, while the middle points elsewhere.
All three anchor associations remain in the SUS 8 record, with shared-link
warnings on both affected instruments. Titles, not reused attachment URLs,
determine instrument identity. No guessed correction or invented file is added.
There are 29 document associations, including these fragmented source anchors.

`fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob`, generic `fecha`, and `fase`
remain null. The visible date is separately named
`source_page_fecha_publicacion=2021-07-07`; years in labels or upload paths are
not approval dates. Instrument IDs are deterministic local hashes of inventory
identity, never represented as municipal expediente numbers. Each resource has
`source_entity_type=documento`: the shared policy correctly treats these as
document resources without an independently established approval/activity identity.

## Completeness and failure behaviour

The adapter reads the whole reviewed inventory, without a record-count cap or
slicing. No pagination appears in the captured page. Detected next/page controls
cause an error instead of silent truncation; pagination requires a crawler update.
Missing headings, unfamiliar sections or entries, invalid document hosts, HTTP
errors, unexpected cross-host redirects and oversized responses also fail.
Updates refresh the same full inventory rather than append duplicates. Output is
replaced atomically only after successful parsing. Licence methods return an
explicit disabled result with no records.

This is partial municipal coverage: no full RPUC/MUC, gazette, council-minute,
public-works or historical archive backfill. Current legal validity and attachment
contents remain unverified. There are no verified project geometries or
coordinates; no municipality centroid, geocoder result or jitter is substituted.

## Validation and local evidence

- `python -m unittest municipio.test_vidreres -v`: **5 tests passed** with the
  runtime above. Covers component grouping, dates, shared/fragmented links,
  stable identity, changed-source/form rejection, pagination rejection and
  manifest/adapter contract.
- Real live extraction through `load_portal_adapter(load_manifest('vidreres'))`
  and `backfill_proyectos`: **14 records**, status `ok`; shared entity policy
  status `ok`, zero unknown identities. All are documentary resources, not
  activity-eligible approval acts.
- Local, uncommitted `evidence/proyectos.jsonl`, `evidence/validation.json`,
  `evidence/proyectos.entities.json`, `evidence/pgou.html`, representative source
  captures and `evidence/source-checks.json` retain the result and limitations.
- Only the four requested source files are added. No dependency/shared source
  changes, deployment, database, publishing or git mutation is required.
