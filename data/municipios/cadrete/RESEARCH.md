# Cadrete — Zaragoza — INE 50066

Verified live on 2026-11-09 using the preinstalled Python runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Official source discovery

- https://cadrete.es/urbanismo-y-medio-ambiente/ is the official municipal service
  page indexed with a PGOU access. Direct HTTPS requests timed out (also tested
  www, HTTP and the public WordPress page endpoint). Search snippets served only
  for discovery; no records were extracted from them.
- https://cadrete.es/impresos/ lists application forms, including major/minor works
  and first occupation. These are not grants; licences remain disabled.
- https://cadrete.sedelectronica.es/transparency responds HTTP 200 anonymously.
  Its section 7 advertises 349 documents, with 80 in section 7.1 planning and 247
  in section 7.4 public works. These are document counts, not project counts.
- https://cadrete.sedelectronica.es/transparency/14ef2e83-b6e7-4490-b8b1-fdf49342ce19/
  is section 7. Public folder navigation is encoded in Wicket GET callbacks.
  Requesting folder callbacks as ordinary GET requests redirects to stable UUID
  folder URLs. Adding AJAX headers had returned a blank response; these are not
  required for ordinary public navigation. No login or authentication was used.
- https://cadrete.sedelectronica.es/transparency/4f82e54f-53f4-4420-91aa-c85715af55f2/
  is the current planning inventory and adapter entry point.
- https://cadrete.sedelectronica.es/board responds HTTP 200 with ten initial
  notices and “Mostrar más”. No board records are ingested; it is explicitly
  outside this adapter's scope, not treated as an exhausted history.
- https://idearagon.aragon.es/archivoSIUa/ is an official regional planning
  catalogue found during discovery; direct runtime requests were reset. It is
  not used as a source or assumed to provide complete alternative coverage.

## Extracted instruments and grouping

| Instrument | Documents | Stable folder UUID |
| --- | ---: | --- |
| Plan General de Ordenación Urbana de Cadrete | 38 | 79563926-62f4-45aa-a6de-76ba50373a99 |
| Plan Parcial Sector 1 Residencial | 2 | 42de6bf7-5fad-4514-8be7-e2603391d12d |
| Plan Parcial Sectores 2 y 3 Industriales | 3 | dc1a06d4-2f36-483d-b881-8c90b7c592c5 |
| Plan Parcial La Corona | 3 | 3c0e89b6-a64f-4fd0-ab62-857a82984bc9 |
| Plan Parcial El Olivar | 2 | bd739949-4180-457e-a4f3-0d2315e7010f |
| Plan Especial de Protección del Entorno de la Muralla del Monasterio de Santa Fé | 19 | 2544ab7f-daf7-4a90-9201-8b3ae08d0f6e |
| Plan Especial del Castillo de Cadrete | 2 | 1f9d5c86-f425-417a-b9e5-08fe20394f3b |

The live adapter emitted seven instruments with 69 document links. Memories,
regulations, corrections and nested plan sheets stay together within the source
instrument folder. PGOU sheets carrying MOD labels remain part of the municipal
PGOU document collection, not separate invented modification records. Each
attachment retains its title, official preview-document UUID URL, source folder
URL and relative folder path. Instrument IDs derive from stable folder URLs,
not session-specific callback URLs. Two industrial sectors are one record because
the municipality publishes them together as one plan folder.

## Coverage and semantics

Coverage is deliberately partial: only named Plan General, Plan Parcial and Plan
Especial folders in section 7.1. The nine-document detail-study collection,
planning-status reports, PGOU8 agreement, public-works inventory, mobility,
environment, civil-protection and other sections are excluded. This is not a
complete municipal project, licence or planning-history register.

The source establishes actual planning instruments with associated technical
materials; it does not establish their approval dates or current legal validity.
PDF contents are not parsed or downloaded by the adapter: document links target
the official public preview. There are no inferred agreement, approval or
publication dates. The site's current clock and filename dates are not used.
`fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` and `fase` stay null.
No centroids, invented coordinates or jitter: `lat`, `lon`, `geometry` stay null,
`publication_ready` is false, scheduling and licences are disabled.

## Pagination and verification

All “Mostrar más” responses in the selected planning inventory and descendant
folders are consumed. The endpoint returns XML components with appended rows;
a hidden replacement control explicitly signals exhaustion, including when the
initial inventory has exactly ten rows and the next response has no rows.
Subfolders are traversed recursively and document totals must match the advertised
recursive count for every selected folder. Duplicates, empty responses, unexpected
links, count mismatches or a pagination/depth guard fail extraction before output
replacement. Limits are errors, never silent truncation. Updates refresh the
whole scoped inventory atomically; no incremental completeness is claimed.

Validation: `python -m unittest municipio.test_cadrete -v` passed five tests covering
metadata/date semantics, excluded entity kinds, XML and navigation guards,
pagination including empty end and repeated rows, recursive count reconciliation,
manifest flags and disabled licences. Real `CadreteAyuntamientoAdapter.backfill_proyectos`
completed successfully with seven records. Local `evidence/proyectos.jsonl`,
`evidence/validation.json` and numbered source captures preserve the live run;
evidence is not source material to commit. Captures contain public website
responses, without session cookies or request headers.
