# Santoña — INE 39079, Cantabria

Verified live on 2026-11-07. This adapter extracts one genuine planning instrument
from the current municipal website, with its documentary inventory grouped under
one stable record. Coverage is deliberately partial: the municipal PGOU index,
not a complete works register or legally consolidated planning database. Scheduling
is disabled, licences are disabled, missing-coordinate jitter is disabled, and
`publication_ready` is false.

## Source discovery and provenance

- https://santona.es/guia-ciudadana/urbanismo — official municipal urbanism page,
  HTTP 200. Three download categories: PGOU, responsible declarations and
  certificates/applications. The PGOU category contains one actual downloadable
  index. The other categories contain application forms; none are licences granted.
  The live category has no pagination or next-page links. The adapter rejects
  detected pagination and additional PGOU inventory entries for review rather than
  selecting the first document or silently dropping entries.
- https://santona.es/descargas/51/PGOU/139/Plan-General-Ordenacion-Urbana-Santona
  — HTTP 200, 74,955 bytes, PDF signature (served as application/octet-stream).
  Redirects to the same official host's Joomla Dropfiles download handler.
  This is an index, **not the complete plan in one PDF**. It expressly names the
  PGOU, definitive approval by the Comisión Regional de Urbanismo de Cantabria
  on 1987-11-20 and BOC publication on 1988-08-19. These dates come from the index
  narrative; the original agreement and bulletin were not independently retrieved.
  PDF creation metadata is not used as an approval/publication date. The 2014–2015
  dates in related ordinance/PORN references are not dates of PGOU approval.
- http://www.santona.es/Datos/Urbanismo/PG.SANTOÑA_1_memoria_1.1.pdf
  — one constituent memory document checked live using both the index's HTTP URL
  and HTTPS variant, both HTTP 200 application/pdf, 925,389 bytes. The index links
  31 PGOU documents (including the legacy index), retained along with the current
  download as 32 document links under one instrument. The adapter preserves the
  exact source URLs; it does not invent replacements or create a project per PDF.
  Not all 31 linked documents were downloaded or checked for accessibility.
- The same index also links ordinances and the regional marshes PORN. Those links
  remain `referencias`, not additional Santoña projects or PGOU components.
  The source repeats one BOC URL with two different labels; URL deduplication keeps
  its first label. No attempt is made to silently repair that source discrepancy.
- https://santona.es/ayuntamiento/plan-de-sostenibilidad-turistica — HTTP 200,
  inspected as an alternative current municipal inventory. Lists a mixed programme
  of physical interventions, services, supplies and awareness activities. This
  adapter does not extract it or claim coverage of those actions.
- The municipal navigation links its electronic headquarters at
  https://sedesantona.simplificacloud.com/ and the national procurement profile.
  Neither was extracted as a granted-licence or project register. Procurement
  announcements and unrelated municipal news are not used as substitute records.

## Implementation and limitations

`municipio.adapters.santona:SantonaAyuntamientoAdapter` implements the shared
portal interface. It fetches the current inventory and its linked PDF on each
backfill/update. Update is a complete snapshot refresh; it does not append duplicate
records or advance a date cursor. Requests have timeouts and bounded byte counts;
oversize responses raise an error rather than being truncated. The PDF must have a
PDF signature. Parsing requires the named Santoña PGOU, explicit dated approval
and publication statements, and constituent plan links. An empty page, login page,
wrong municipality or unexpected inventory fails before replacing prior output.

PDF text and hyperlinks are read with the existing Poppler `pdftohtml` executable
using a temporary directory, no installation or new Python dependency. Missing
Poppler or a conversion failure is an extraction error. The adapter groups plan
parts separately from contextual references and retains document provenance and
the fetched PDF's SHA-256. Dates are parsed from the source, not hardcoded.

No claim is made that the 1987 plan is unchanged, that every subsequent amendment
is represented, or that every listed legacy document still works. No project
coordinates/vector geometry were extracted; `lat`, `lon`, and `geometry` are null.
The municipality centroid is not substituted. Licence methods emit zero records
with disabled status and perform no network requests.

## Validation and local evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_santona -v`: six tests passed. Covers source/form
  separation, grouping/deduplication, distinct dated provenance, rejection of
  changed/paginated inventory and missing dates, manifest resolution, disabled
  licence methods, full-refresh update and preserving old output on failure.
- Live `load_manifest('santona')`, `load_portal_adapter(manifest)` and
  `backfill_proyectos(Path('evidence/proyectos.jsonl'))`: status ok, **1 record**,
  32 documentary links. Shared entity policy reported unknown classification for
  this planning instrument; it is not evidence of a construction project category.
- Local uncommitted `evidence/validation.json` records live count, source URLs,
  timestamp, tests, policy result and limitations. `urbanismo.html`, `pgou.pdf`,
  `pgou-links.html`, `pgou.txt`, `turismo.html` and `legacy-document-check.txt`
  retain source captures/checks. Evidence is not part of the source contribution.

Exactly four source files are added for Santoña; shared sources and dependencies
are unchanged. No publishing, database, deployment or remote repository operation
is required or performed.
