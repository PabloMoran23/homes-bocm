# Sóller — INE 07061, Illes Balears

Verified live 2026-11-07. This adapter provides a deliberately partial snapshot
of three genuine planning instruments listed in the municipal document inventory.
It does not assert that the historic plan versions are the complete consolidated
law currently in force. Scheduling, licence extraction and coordinate jitter are
disabled; publication_ready is false because geometry has not been verified.

## Official inventories discovered

- https://ajsoller.net/es/arxius-i-documents/normativa-activitades-obras-y-urbanismo
  is the current municipal urbanism document index (HTTP 200). Eight folders:
  three planning folders, pending PGOU modifications, ordinances, heritage,
  environmental legalisation measures, and solar-panel guidance. The last four
  are not project records; a legalisation guide is not a granted licence.
- https://ajsoller.net/ca/arxius-i-documents/urbanisme/01-pla-general-1998
  lists 10 documents: approval document, four amendment bulletins, normative
  annexes, catalogue and a ZIP of plans. One parent planning record retains all
  ten links, including the amendments. No separate project per PDF.
- https://ajsoller.net/ca/arxius-i-documents/urbanisme/02-pla-especial-proteccio-i-sanejament-de-lhorta-2011
  lists 13 documents for the special protection and sanitation plan of l'Horta:
  norms, CIM agreement, guide map, ordering plans and infrastructure sheets.
  One planning record retains all thirteen links.
- https://ajsoller.net/ca/arxius-i-documents/urbanisme/03-adaptacio-dot-2005
  lists 10 documents for the DOT adaptation, including BOIB norms and nine
  numbered PDFs. One planning record retains all ten links.
- https://ajsoller.net/ca/enlla%C3%A7os/urbanisme/04-mod-pgou-en-tramitacio
  links to the separate official electronic-office inventory:
  https://soller.sedelectronica.es/transparency/7bfdf34e-6880-453d-9a9b-ccc19f5cfbaf/
  (HTTP 200, anonymous HTML). It lists Muleta delimitation 3320/2018, PGOU
  modifications 8746/2023, 1909/2025 and 1910/2025, alongside applicability and
  environmental-measure files. This is usable for further work, but its child
  folders and documents are outside this adapter's explicitly limited coverage.
  They are not claimed as extracted, nor represented by placeholders.

## Provenance and semantics

The adapter fetches the index and discovers the three reviewed folder URLs and
advertised document counts. It parses actual titles, document links and file-list
dates from those pages. Every document carries its source folder URL. The folder
URL identifies each instrument and provides a stable hashed scraper identity;
no municipal expediente number is invented. Parent-folder grouping follows the
municipality's organisation and does not resolve amendment instruments into
independent dossiers.

Folder headings include years (1998, 2011, 2005); these remain title text, never
synthetic approval dates. File-list dates, such as 19/11/2019, 15/11/2019 and
01/06/2023, have unknown administrative semantics. They are stored only as
fecha_listado_archivo on documents. fecha_publicacion, fecha_acuerdo and
fecha_aprob remain null. Linked approval documents have not been parsed for
actual agreement dates. No phase is inferred from an attachment title. PDF/ZIP
contents and plan geometry are not extracted. Coordinates remain null; no
centroids, invented points or jitter are used.

The current index and folders expose no pagination. The crawler rejects pager
markup or rel=next and validates each folder against the index document count,
so a first page or changed structure cannot silently become a complete snapshot.
Missing folders, content, titles, external document origins or count mismatches
fail extraction. The output replaces the previous snapshot only after all three
folders succeed. Update performs the same full refresh; state is not a date
watermark. Requests have timeouts and a 3 MB response bound. Dependencies are
already installed; no shared files or dependency definitions changed.

## Validation and local evidence

- Runtime: /home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python
- Parser/behaviour checks: `-m unittest municipio.test_soller` (5 tests passed).
  Covers grouping, date semantics, missing content, pagination refusal, document
  counts/origins, stable refresh and disabled licences.
- Live extraction through the manifest/registry adapter writes
  evidence/proyectos.jsonl: 3 instruments with 33 document links.
- evidence/validation.json records live_records, source_urls, limitations and
  the entity-policy report. Unknown entity-policy classification, if present,
  reflects absent municipal dossier references; no references are fabricated to
  make records activity-eligible.
- evidence/captures contains the exact four HTML responses consumed by the live
  adapter. evidence/inventory.html, folder-0.html through folder-7.html and
  sede.html capture source discovery, including excluded inventories.

Evidence remains local and is not a source deliverable. No publication, external
writes, credentials, databases, deployment or git mutations are used.
