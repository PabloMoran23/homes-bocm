# Zafra — Badajoz — INE 06158

Verified 2026-11-07. This adapter extracts one genuine planning instrument:
SITEX's current consolidated document package for Zafra's PGOU.R-001. It is a
partial planning inventory, not a complete municipal project or licence census.
`publication_ready` is false: project geometry has not been extracted.

## Official sources discovered and inspected

- https://zafra.es/urbanismo-y-obras/ — municipal urbanism service page;
  live Python request returned HTTP 403. Captured in `evidence/urbanismo.html`.
- https://zafra.es/normativa-y-reglamentos/ — municipal normative inventory;
  live Python request returned HTTP 403. Captured in `evidence/normativa.html`.
  No access-control bypass or authentication was attempted.
- https://sitex.juntaex.es/SITEX/ptofiguras/viewrefundido/212 — HTTP 200,
  official Junta de Extremadura planning inventory, explicitly headed
  “Refundido vigente de la figura 'PGOU.R-001' y sus modificaciones”, Zafra.
  This is the adapter's actual extraction source. The source is regional;
  `proyectos.source: ayuntamiento` selects the repository's municipal adapter
  pathway, while records explicitly attribute provenance to Junta/SITEX.
- https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/37814 — HTTP 200,
  linked base-plan record: Plan General de Ordenación Urbana, revisión 001,
  territorial scope Zafra, reference PGOU.R-001, state Vigente. Captured in
  `evidence/sitex_pgou.html` for research. Its explicit original approval date
  is 1988-12-26 and BOP publication date is 1989-06-16. These are base-plan
  dates, not the approval/publication of the consolidated package, and are
  deliberately not transplanted into the extracted package record.

Search also located the official DOE publication of the 2025 modification:
https://doe.juntaex.es/otrosFormatos/html.php?anio=2025&doe=490o&xml=2025080386
and the non-current PGM dossier
https://sitex.juntaex.es/SITEX/ptofiguras/imprimirinfogeneral/37053 .
These discovery results are outside the implemented package snapshot; neither
is claimed as live adapter coverage. Procurement notices, licence application
forms and general news are not ingested as projects or granted licences.

## Implemented extraction and semantics

One request retrieves the complete static refundido page (40-second timeout,
4 MB response bound). Parsing requires the exact package and Zafra identity,
the inclusion/exclusion provenance table, and normative and catalogue documents.
HTTP errors, unexpected redirects, changed package identity, malformed document
paths, missing essential content and detected pagination fail explicitly.

All download anchors inside the document inventory are retained, including
collapsed map sheets. Live extraction found **34 unique document URLs**:
9 PDFs and 25 WebP images. They belong to **one** instrument and remain grouped
in `documentos`, with original URLs, source-relative filenames, referring page,
and explicit document update dates. Original download URLs are preserved rather
than reconstructed from guessed filenames. Duplicate URLs are consolidated.
No arbitrary page/record limit is applied. This single package has no pagination;
the regional search results and historical evolution are outside coverage.

The source identifies 12 figures as incorporated and 10 as not incorporated.
All 22 references and their actual detail URLs are retained under
`figuras_refundidas`; their individual dossiers are not separately scraped.
“Not incorporated” is not interpreted as “invalid” or “not approved”. The
consolidation does not claim to contain every modification or every instrument
in the municipality. Update refreshes the complete same package snapshot and
does not claim a historical incremental cursor.

All live documents show update date 2026-09-07. This is preserved only as
`documentos[].fecha_actualizacion`. Agreement, approval and publication fields
remain null because the package page does not establish those dates for this
consolidation. No date is inferred from a filename, crawl date or related plan.

No coordinate, parcel centroid, town centroid or randomized location is emitted.
Raster plan links are documentary provenance, not extracted feature geometry.
Licence methods return disabled with zero records; no granted-licence register
was verified. Scheduling and missing-coordinate jitter are disabled in the
manifest. Document binary contents are not parsed; this is an inventory scraper.

## Validation and local evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_zafra -v`: 6 tests passed. Checks cover grouping,
  update-vs-approval date semantics, all hidden documents without truncation,
  duplicate document URLs, changed municipality, loading/navigation shells,
  incomplete inventory, unexpected pagination, missing document dates, manifest
  resolution and disabled licences without network requests.
- Real live `load_portal_adapter(load_manifest('zafra')).backfill_proyectos(...)`
  completed successfully: **1 record**, 34 document links, source/record parity
  checked against the captured page. Registry policy annotation also completed;
  its category is unknown, which is not a claim of a physical construction work.
- `evidence/proyectos.jsonl`: actual extracted record, including all document and
  related-figure URLs. `evidence/validation.json`: live count, source URL, test
  result, limitations and provenance counts.
- `evidence/sitex_refundido_live.html`: exact live extraction response;
  `evidence/sitex_refundido.html`: initial research capture. Other captures listed
  above document municipal HTTP 403 and base-plan research.

Only the four requested source files are added. Evidence is local, not intended
for commit. No dependencies or shared sources changed; no database, credential,
publication, deployment or git mutation commands were used.
