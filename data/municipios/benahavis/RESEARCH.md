# Benahavís — INE 29023, Málaga, Andalucía

Research and live verification: 2026-11-07. This is a **partial planning-document
snapshot**, not a list of granted licences or a claim that every instrument is
currently in force. Scheduling and missing-coordinate jitter are disabled.

## Official inventories investigated

- https://www.benahavis.es/ — HTTP 202 with an empty body in the direct request.
  No municipal news or inferred projects were extracted from this response.
- https://benahavis.sedelectronica.es/transparency — HTTP 200. The municipal
  transparency index reports **322** documents under category 7 (urbanism, public
  works and environment). Anonymous access works; no login is needed.
- https://benahavis.sedelectronica.es/transparency/480bb655-bfb0-4b16-9411-328164095310/
  — category 7. Contains **7 direct documents**, all numbered parts of the
  Proindiviso A RLQ urbanization project, plus child categories.
- https://benahavis.sedelectronica.es/transparency/ed77de34-9f82-4ef8-8414-1e292e40b901/
  — category 7.1 (planning), **314 documents**, retrieved over **32 pages** (initial
  10 and 31 AJAX continuations, ending with 4). Most are historical PGOU map sheets,
  annexes and RIU register files. They are not emitted as separate projects.
- https://benahavis.sedelectronica.es/transparency/6b7c4625-9077-4020-be00-01c2ca1fea78/
  — category 7.4 (public works/infrastructure), **1 document**, MAPAS-CALLEJERO.
  A street map is excluded because it does not establish a physical works project.
  The other three category-7 child folders report zero documents.
- The sede catalogue at https://benahavis.sedelectronica.es/info.0 advertises an
  urbanistic licence application procedure. This is not a granted-licence register
  and is not extracted. `licencias.enabled` is false.

The current inventory includes older documents. Neither its presence on the sede
nor its upload timestamp establishes current legal validity. The adapter covers
category 7 and descendants, not every document in other transparency categories,
all notices on the board, procurement, municipal minutes or the entire province.

## Four instrument groups supported by actual documents

1. **Proindiviso A, sector El Real de la Quinta — urbanization project.**
   https://benahavis.sedelectronica.es/preview-document/aae475c2-3c69-4227-81d2-cb63fd3c3232
   Its PDF cover identifies the project and Benahavís. The category-7 root has all
   seven numbered parts; planning repeats parts 1, 2, 3, 4, 6 and 7 under different
   document UUIDs. All **13 preview links** are kept together in one instrument,
   including the root-only part 5. Duplicate uploads are not separate projects.
2. **Tajos Blancos / La Zagaleta — hotel-parcel study of detail.**
   https://benahavis.sedelectronica.es/preview-document/407e16a1-3fa2-4251-80af-def149c3d0d9
   The PDF describes reordering hotel parcels H1.1, H1.2, H2.1, H2.2 and H2.3 in
   Benahavís. One source document, one instrument. No approval is inferred from
   the document's September 2018 preparation date.
3. **El Madroñal, parcels 3, 4 and 5 — modification of study of detail.**
   https://benahavis.sedelectronica.es/preview-document/11e056fd-d38d-4a47-91df-38e56a0090bc
   The PDF is a modification for those parcels. The inventory also supplies a
   plan and an initial-approval edict; all **3 links** belong to one record. The
   memory mentions approval of the earlier study on 2018-10-05; that date must
   not become approval of this modification. The phase is explicitly qualified
   as coming from the edict title, not a newly verified final approval.
4. **La Fuente — partial development plan.**
   https://benahavis.sedelectronica.es/preview-document/1a9b929a-96d1-4c94-8ec0-3b9c63d14dda
   The official edict identifies PPO sector Surs-C5 and initial approval. It is a
   planning-instrument notice, not a procurement announcement. Its body describes
   an agreement of 2020-07-23, while the signature is dated 2020-07-28 and the
   preview creation timestamp is 2020-08-14. These are distinct events. The
   adapter does not parse PDF dates and leaves agreement/approval/publication
   dates null rather than substitute the signature or upload date. One edict
   link is retained; the external file share named inside the PDF is outside
   this extraction's coverage.

Representative PDF bodies were downloaded anonymously and inspected with the
preinstalled `pdftotext` during research. Captures include `rlq.pdf`,
`zagaleta.pdf`, `madronal.pdf`, `fuente.pdf`, their preview HTML and text extracts.
A representative RIU PGOU file was also captured for inventory investigation;
RIU files are not classified as project records by this adapter.

## Extraction, provenance and limits

The scraper fetches the index's category-7 count, enumerates every page of the
root and nonempty child folders, then checks direct plus descendant counts.
Wicket folder callbacks return an `Ajax-Location` header; pagination returns XML
components with CDATA and sometimes `wicket1` encoding. Only the callback URL
is read from markup: external JavaScript is never executed. Pagination must
reach the explicit hidden load-more component. Count mismatch, stalled pages,
unknown encoding, unexpected hosts, HTTP errors, expired sessions, response
limits and traversal limits raise errors before replacing the output snapshot.
The update method repeats the full snapshot, so older and later-page files are
not silently skipped. Responses are bounded at 4 MB, timeout 40 seconds;
limits fail explicitly rather than accept truncated output.

Classification is intentionally limited to the four reviewed title families.
New or ambiguously named files are enumerated but excluded until reviewed. In
particular, hundreds of PGOU sheets, RIU register entries (including an explicitly
annulled entry), ambiguous compensation-board material, street maps, licence
forms and procurement minutes are not converted into projects. This is partial
semantic coverage even though inventory pagination is complete.

Stable instrument IDs use the reviewed instrument family, independent of page
order. All selected source preview URLs, inventory memberships and original
link titles are retained. Every selected preview must still identify the exact
file, expose PDF format and an official PDF frame, and supply its integrity
hash. Its CSV, integrity hash and original creation timestamp are preserved.
The adapter checks previews but does not repeatedly download large PDF bodies.
No source update, crawl, signature, professional visa or creation date is used
as a publication or approval date; all record-level date fields remain null.

No verified project geometry or point coordinates were obtained. `lat`, `lon`
and `geometry` are null; `publication_ready` is false. No municipality centroid
or random coordinates are substituted. The shared registry's entity-policy
wrapper reports these four unnumbered instruments as `pendiente` with
`insufficient_identity_evidence`; no invented dossier reference is supplied to
force eligibility. Independent review and further enrichment are still needed.

## Validation and local evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
No packages were installed and no shared source or dependency files were changed.

- `python -m unittest municipio.test_benahavis -v`: **9 tests passed**. Covers
  grouping multiple parts, exclusions, date provenance, exact municipality and
  disabled flags, preview rejection, Wicket decoding, traversal of all pages,
  mismatched counts, pagination stalls, and preservation of a previous complete
  output after a late-page failure.
- Live extraction uses `load_manifest('benahavis')`, `load_portal_adapter(...)`
  and `backfill_proyectos(Path('evidence/proyectos.jsonl'))` with the local
  `capture_dir` option. **4 records, 18 document links, 322 inventory documents**.
- `evidence/proyectos.jsonl` contains real extracted rows, including the shared
  policy annotations. `evidence/validation.json` records live count, source URLs,
  per-folder counts, limitations and the runtime. `evidence/final-live/` contains
  the final run's raw HTML/XML responses; earlier research captures are also
  under `evidence/`. Evidence stays local and is excluded from source changes.

No database, credential, production, deployment, publication or Git write
operations are needed or used.
