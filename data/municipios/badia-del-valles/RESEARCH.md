# Badia del Vallès — INE 08904, Barcelona

Verified live 2026-11-07 using the preinstalled Python 3.12 venv. This adapter
extracts the official current-planning inventory, not a register of granted
licences or a complete inventory of municipal construction. Scheduling and
coordinate jitter are disabled. Records have `publication_ready: false` because
no verified project geometry is extracted.

## Sources and scope

The official Urbanisme page https://www.badiadelvalles.cat/area.php?id=9 links to
https://www.badiadelvalles.cat/seccio.php?id=35 (Planejament urbanístic). The
latter exposes an actual nested inventory under Planejament vigent, category
118, with four named instruments and their document categories:

| Instrument category | Instrument | Document categories | Unique PDFs |
| --- | --- | --- | --- |
| 590 | Modificació del Pla General Metropolità i del Pla Comarcal de Sabadell dintre del terme municipal | 591–594: agreement, rules, information maps, zoning maps | 11 |
| 595 | Modificació puntual del Pla general metropolità a l'àmbit de les instal·lacions esportives | 596–597: agreement and maps | 4 |
| 598 | Modificació pla general metropolità per a la creació de la clau sistema habitatge dotacional (HD) | 599–601: initial-approval documents, unified document, definitive approval | 4 |
| 602 | Modificació puntual del Pla general metropolità al front del Riu Sec | 603–605: resolution, agreement, definitively approved documentation | 5 |

Category URLs use `https://www.badiadelvalles.cat/fitxes.php?categoria=NUMBER`.
The current inventory and all twelve document-category responses returned HTTP
200. One agreement/resolution PDF per instrument (categories 591, 596, 601, 603)
was additionally downloaded, returned HTTP 200, and had a PDF signature; these
four files are retained locally. All 24 original PDF links are preserved in the
JSONL. The adapter does not claim to download or interpret all PDFs.

The index also advertises Planejament en tramitació (category 589). Its HTTP 302
redirect points to https://seuelectronica.badiadelvalles.cat/fitxa.php?id=7474;
following it failed TLS verification with an expired certificate. Verification
was not disabled. This branch is outside the adapter's explicit current-plan
scope; it is a coverage limitation, not a reason to invent an in-progress row.
The municipal Urbanisme page also links licence application procedures and an
Actuacions a la via pública section. These have not been established as complete
project or granted-licence inventories and are not emitted. No procurement or
news announcements are used as project records.

## Parsing, provenance and semantics

The adapter reads the current-plan subtree and discovers every direct instrument
and its document groups dynamically. Every document category must contain actual
municipal urban-planning PDF blocks. PDF thumbnails and filename links within a
block are one document. One stable record per instrument category groups all its
documents; each document retains title, URL, group label and originating category
URL. The instrument retains its category URL and the inventory source URL.

Phase `vigent` means listed under the municipality's current-planning heading;
it is not inferred from the presence of an initial-approval document. Initial,
unified and final documents remain together, not separate projects. Publication,
agreement and approval dates are separate null fields: source category pages do
not provide reliably typed dates, and filenames, scan metadata and crawl time
are not used as dates. PDF text/date extraction is outside this implementation.
No invented dossier identifiers, addresses, centroids or coordinates are supplied.

The municipal HTML is ISO-8859-1; parsing original response bytes preserves
Catalan accents. Requests have a 30-second timeout and 3 MB HTML bound, with TLS
verification enabled. Missing inventory, unsupported hierarchy, empty categories,
unexpected document hosts, pagination links/containers and changed document
markup raise errors. There is no page-count cutoff or first-page-only output:
the reviewed inventory is unpaginated; any detected pagination requires a crawler
extension. Output is written atomically only after all categories succeed.
Updates refresh the complete scoped snapshot and do not advance a date cursor.

## Validation and local evidence

- `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_badia_del_valles -v`: six tests passed. Covers grouping and provenance, encoding, date/geometry nulls, stable full updates, disabled licences, rejection of forms/navigation, missing/foreign documents and pagination, and preservation of prior output on failure.
- Real extraction used `load_manifest` and `load_portal_adapter`, exercising the manifest import and shared entity-policy wrapper: four records, 24 document links, status `ok`. Shared entity policy currently labels these records unknown (4/4); this is retained in validation, with no shared policy changes.
- `evidence/proyectos.jsonl`: actual live rows.
- `evidence/validation.json`: live count, fetched source URLs, all document URLs, limitations, parser test result, shared policy report and four PDF fetch checks.
- `evidence/live-*.html`: exact bytes fetched by the adapter; `inventory.html` and `category-*.html`: discovery captures. `agreement-*.pdf`: four source PDF captures. `in-progress-redirect.json`: observed redirect.

Evidence is local only. No shared files, dependencies, credentials, databases,
publishing, deployments or git metadata were modified.
