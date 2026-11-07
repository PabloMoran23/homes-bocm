# Orpesa / Oropesa del Mar — INE 12085, Castellón

Verified 2026-11-07 using the preinstalled Python 3.12 virtual environment.
This adapter extracts a real but partial municipal planning/document archive.
It does not assert that archived instruments are approved, legally current,
executed works, or granted licences. Scheduling and coordinate jitter are disabled.

## Discovery and official provenance

- https://www.oropesadelmar.es/ — working official municipal website.
- https://www.oropesadelmar.es/es/sitemap — links to PGOU and downloads.
- https://www.oropesadelmar.es/es/pgou — HTTP 200, but only a PGOU heading,
  taxonomy and feedback form; no usable plan record. Not emitted.
- https://www.oropesadelmar.es/es/descargas — paginated category directory.
  Discovery identified the specific Urbanismo category; this general directory
  is not the adapter's record inventory and is not presented as exhaustive.
- https://www.oropesadelmar.es/es/descargas/urbanismo-y-medio-ambiente — HTTP
  200; its article embeds the public municipal document folder below. The adapter
  verifies this delegation on every run before fetching documents.
- https://drive.google.com/embeddedfolderview?id=0B5fl2C1HLL08a3FSSTd2b2dkT1U&resourcekey=0-UrzYYiFLxU3zbsZazwYBGw
  — HTTP 200, 30 entries (28 files, two child folders).
- https://drive.google.com/embeddedfolderview?id=1AvoNACFgDpnkd-QniS9zDlM8-qZoIeXQ
  — Convenios child folder, one water-supply agreement; excluded because the
  isolated agreement filename does not substantiate a physical project.
- https://drive.google.com/embeddedfolderview?id=1k9bgdNFlB7RP8JK8UfcwNAhhGlzUuRyW
  — five restoration-project and landscape-study files, grouped with the
  corresponding Torre Bellver restoration instrument in the root folder.
- https://sede.oropesadelmar.es/portal/transparencia/se_principal1.jsp?codMenu=46&seccion=se_seccion_menus.jsp
  and the indexed `se_contenedor2.jsp` Urbanismo menu: direct HTTPS requests
  failed certificate validation (including with system CA bundle); browser
  retrieval returned 502. HTTP fallback returned 404. TLS verification was not
  disabled. These are not runtime dependencies and no cached search result
  becomes an extracted record. Indexed catalogue pages describe application
  procedures, not granted licences, so licences remain disabled.

The municipal embedding is the provenance for Drive hosting; this is not an
independently chosen third-party folder. Access is anonymous. No credentials,
private Drive API, account session, or authentication bypass is used.

## Extraction semantics and coverage

Live output: **17 instruments, 29 document links, three folders visited**.
Examples include PGOU modifications Palmavera, 1-2015 R4B/R5A, 2-2016 sector
noroeste, 1.2023 residence/day centre Els Cuarts; La Colomera special-plan
consultation; Torrepaquita PAI; UE2 La Catalaneta urbanization; Paseo Marítimo
Mediterráneo legalization; restoration R2C/R14 Torre Bellver; and R3/CHT2 service
road and pavement urbanization. PGOU 2017 is identified only as an environmental
memorandum/synthesis, not as an approved new general plan.

The restoration landscape-study PDF was downloaded anonymously and inspected
with the installed `pdftotext`. Its cover explicitly identifies the restoration
of R.2C and R14 of Plan Parcial Torre Bellver in Oropesa del Mar; this corroborates
grouping the EIP memory/annexes, including the child folder bearing the wider
LIC Litoral Benicàssim name. Local captures include this PDF and extracted text.
The adapter itself reads inventory names and links, not PDF bodies or archives.

Documents for a single instrument are grouped under a stable instrument key:
Palmavera (three), R4B/R5A (two), sector noroeste (two), La Catalaneta (three),
and restoration (seven). Separate Drive IDs with the same filename are retained
as distinct source links; identical IDs are deduplicated while retaining each
inventory URL. All original resource keys in file links are preserved.
Filename numbers are instrument identifiers, never manufactured approval dates.

Five non-project documents are explicitly excluded: two licence/application
forms, two ordinances (including a proposed beach ordinance), and the isolated
water agreement. Unknown new filenames cause failure for review, not silent
omission. No procurement feed or unrelated news is used.

Drive labels are **last modified**, sometimes abbreviated or without a year.
They remain raw `fecha_modificacion_archivo_texto` in each document. Generic,
publication, agreement and approval dates are null. Phase is null: a filename
mentioning an environmental resolution or public consultation does not establish
the entire instrument's present legal stage. There are no verified coordinates
or vector geometries: lat/lon/geometry are null and publication_ready is false.

All nested folders are traversed, with cycle detection. Reviewed embedded views
are static HTML listings, with no next-page links or continuation controls.
Explicit pagination or a folder reaching 50 entries raises an error rather than
silently truncate. This is a deliberate fail-closed threshold, not a fetched
record cap. Archive growth or markup changes require re-review. Unknown formats,
missing provenance, HTTP failure and empty usable output also fail without
replacing an existing snapshot. Updates refresh the entire archive snapshot.

This is not a full register of municipal projects, a historical gazette crawl,
or a guarantee of current planning validity. Approval dates, legal status,
PDF contents and geometry would require separate documentary investigation.

## Reproduction and evidence

Run from repository root with:

```
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_orpesa -v
```

Six deterministic tests pass: grouping/exclusions and unknown-file rejection,
original links and modified labels, malformed/login/paginated inventories,
recursive snapshot with deduplication and date semantics, failed extraction
preserving the old output, and manifest loading.

Live extraction was executed through `OrpesaAyuntamientoAdapter.backfill_proyectos`
with `config={'capture_dir': 'evidence/captures'}` into
`evidence/proyectos.jsonl`. `evidence/validation.json` records live_records,
source_urls, limitations, exclusions and verification details. Evidence contains
municipal discovery HTML, folder captures, and a sampled source PDF/text. Evidence
is local and is not part of the four source files. No shared code or dependency
changes, publishing, database access or git mutations were performed.
