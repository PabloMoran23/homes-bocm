# Vimianzo — INE 15092, A Coruña

Verified live on 2026-11-09 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
This adapter provides a deliberately partial snapshot: municipal NNSS
modifications in the urbanism normative inventory, not all municipal projects,
not a certification of current legal validity, and not granted licences.

## Official inventories investigated

- https://www.vimianzo.gal/info.php?sec=311&idioma=gl — HTTP 200,
  municipal Urbanismo → Normativa. One inventory page, three named planning
  instruments and one generic links/downloads entry. The adapter extracts the
  named NNSS modifications only. The generic entry also contains industrial-park
  documentation, ordinances and a catalogue; it is excluded from this scope.
- https://www.vimianzo.gal/info.php?sec=10&idioma=gl&page=1 — municipal
  Transparencia → Plans e proxectos. All five pages were inspected and captured
  locally (`evidence/sec=10_idioma=gl_page=1.html` through `page=5.html`). The
  inventory mixes genuine physical works (energy efficiency, roads, photovoltaic
  installation) with staffing programmes and subsidies. It is not consumed by
  this narrow planning adapter; no claim to full works coverage is made.
- https://sede.vimianzo.gal/sxc/gl/portal_transparencia/Institucional_Organizativa/Planes_y_Programas/Planes_Programas.html
  — HTTP 200. Its PXOM link points to the official regional inventory with
  `idconcello=15092`, rather than to an independently published municipal PXOM.
- https://siotuga.xunta.gal/siotuga/inventario?inv=1&idconcello=15092 — HTTP
  200, anonymous response exposes the inventory search interface, not instrument
  rows. Captured for research; no records synthesized from its search controls.
  Regional API/geometry extraction is outside this implementation.

## Extracted instruments and provenance

| Municipal detail | Instrument | Publication explicitly in municipal text | Attached documents |
| --- | --- | --- | --- |
| https://www.vimianzo.gal/info.php?id=482&idioma=gl&sec=311 | MP4 NNSS | BOP 2017-09-11 | 1 BOP PDF |
| https://www.vimianzo.gal/info.php?id=483&idioma=gl&sec=311 | MP5 NNSS | BOP 2018-11-19 | BOP PDF and MP5 planning document |
| https://www.vimianzo.gal/info.php?id=484&idioma=gl&sec=311 | MP6 NNSS | Not stated | Memory, urban rules, settlement sheets, catalogue, plans |

The live extraction yields **3 records with 8 document links**. Identity uses the
explicit modification number; each instrument groups all PDF anchors in its
content, retaining source URL, label and surrounding list-item text. Duplicate
anchors are deduplicated. HTML comments do not become duplicate documents.
Document URLs are resolved relative to the actual detail page, including `../`
segments. Original BOP HTTP links are retained; separate live checks used HTTPS
and followed their redirect to `bop.dacoruna.gal`. All eight links returned HTTP
200 with application/pdf and a PDF signature in the first response chunk.
This checks availability, not the entire PDF contents or legal status.

MP4 and MP5 have explicit definitive-approval document labels. Their BOP dates
are `fecha_publicacion`, never agreement/approval dates. `fecha_acuerdo`,
`fecha_aprob` and generic `fecha` remain null. MP5 retains an older paragraph
about provisional approval on 16 March 2018 and pending definitive approval;
that text belongs to the older document and is preserved, not used to replace
the later definitive-publication evidence. MP4's apparent entry-into-force date
inconsistency is preserved as source text and is not mapped to approval.
MP6 has no explicit phase/date in its HTML, so both remain null. PDF body dates
and geometry are not parsed.

## Crawl behavior and limits

The adapter checks the expected inventory/detail headings and exact instrument
titles, requires PDF documents, and fails on changed/login/empty pages. It
follows all discovered pagination links for section 311, including links outside
the main content and pages discovered on subsequent pages. Repeated inventory
pages raise an error instead of silently terminating. There is no fixed page
count or record truncation. The current scoped inventory has no pagination.
A failed request or parser validation does not replace the existing snapshot.
Updates refresh the complete scoped snapshot, without a date cutoff.

No coordinates are inferred from municipal centroids, document names, maps or
addresses. `lat`, `lon`, `geometry` are null; `publication_ready` is false.
`schedule.enabled`, `geocode.jitter_missing` and `licencias.enabled` are false.
Licence methods explicitly return disabled with an empty output; application
forms, procurement notices, news and general service pages are not licence
records. No public granted-licence register was verified in this investigation.

## Validation and local evidence

- `python -m unittest municipio.test_vimianzo -v`: **7 passed**. Tests cover
  grouping/provenance, publication versus agreement dates, undated documents,
  false/missing details, inventory selection, multi-page discovery, repeated-page
  failure without overwriting output, manifest loading and disabled licences.
- Direct `VimianzoAyuntamientoAdapter.backfill_proyectos` with live HTTP:
  status ok, 3 rows, 1 inventory page, 3 detail pages.
- `evidence/proyectos.jsonl`: actual extracted records.
- `evidence/validation.json`: live count, URLs, limitations and checks.
- `evidence/live/`: exact fetched inventory and detail HTML bytes.
- `evidence/document-checks.json`: live document availability checks.
- Additional research HTML captures are under `evidence/`.

Evidence is local and is not part of the four source files. No shared source or
dependency changes, installation, database access, deployment or publishing
steps are required.
