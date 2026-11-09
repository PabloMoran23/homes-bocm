# Cardona — INE 08047, Barcelona

Verified 2026-11-09 with the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
One municipal adapter; partial planning coverage only. Scheduling, granted
licences and missing-coordinate jitter are disabled. No verified geometry is
available, so all records have null coordinates and `publication_ready: false`.

## Official discovery and inventories

- Municipal plans inventory (HTTP 200):
  https://www.cardona.cat/ajuntament/plans-i-campanyes-municipals/
  links the actual POUM page among other municipal policy plans.
- Municipal POUM page (HTTP 200):
  https://www.cardona.cat/ajuntament/plans-i-campanyes-municipals/pla-dordenacio-urbanistica-poum.html
  explicitly identifies the published municipal POUM and the special plan for
  Muntanya de Sal / Vall Salina. Its RPUC link contains `municipiSel=08047`.
  The page publication (2019-07-22) and update (2019-09-02) are NOT instrument
  approval dates. The link uses the obsolete ptop host; a direct HTTPS attempt
  failed certificate verification. TLS verification was not disabled.
- Municipal transparency planning inventory (HTTP 200):
  https://seu-e.cat/ca/web/cardona/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  contains an independent municipal link to the same RPUC municipal query at
  https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=08047
  which redirects successfully to
  https://planejamenturbanisme.territori.gencat.cat/rpucportal/index.html#/consulta/cercaPublic?reqCode=cerca&municipiSel=08047
- RPUC is the Generalitat's public planning register. The Angular shell alone
  has no records. Public frontend JavaScript exposes the unauthenticated API
  under `https://planejamenturbanisme.territori.gencat.cat/RPUC-portal/rest/consulta/`.
  The adapter calls `basica?municipi=08047&idioma=ca&firstRecord=1&rpp=10&sortDirection=asc`,
  then pages 2 and 3; it fetches `detall` and `arbre` for each selected dossier
  with `codiExpedient`, `idioma=ca`, `cercaPublic=false`. This last parameter is
  the public frontend's normal detail/tree request parameter, not authentication.
  No session or credentials are used.
- https://cardona.eadministracio.cat/dossier.4 redirects to the procedures
  catalogue (`dossier.0`): licence applications, not granted licences.
- https://cardona.eadministracio.cat/board is a live notices inventory with a
  “Veure'n més” control. Its current first page includes a procurement notice
  for Cal Muntada. That announcement is not extracted as a project. The board
  is outside this adapter's scope; no claim is made to have traversed its pages.
- https://www.cardona.cat/ajuntament/informacio-publica/ is an information-access
  request page, not a works/project inventory. General policy plans, unrelated
  news and forms are excluded.

## Extracted scope and semantics

The RPUC municipal query returns 23 entries across three pages (10 + 10 + 3).
Eleven are planning instruments whose **primary municipality field** is Cardona.
The remaining 12 entries are deliberately excluded: ten entries with another
primary municipality (including regional plans and generic criteria), one
urban-planning convention and one consolidated-urban-area boundary (TUC).
Some excluded supramunicipal instruments may affect Cardona; this is a coverage
limit, not a claim that they are unrelated to its territory.

| RPUC dossier | Instrument | Approval field | Publication field | Documents |
| --- | --- | --- | --- | ---: |
| 262286 | POUM | 2015-01-23 | 2020-10-22 | 167 |
| 279776 | POUM modification, PMU-06 Folch-Madoz | 2020-10-02 | 2020-10-29 | 2 |
| 283673 | POUM modification, Passeig de Mossèn Joan Riba | 2019-07-26 | 2019-09-30 | 2 |
| 288038 | POUM modification, PPD03 la Cort II | 2022-02-02 | 2022-04-26 | 2 |
| 292415 | POUM article 136, industrial subzone 6 B | 2022-02-02 | 2022-04-29 | 2 |
| 294153 | POUM modification, Escorials | 2025-06-04 | 2025-07-07 | 2 |
| 297604 | POUM protected-assets entry I-10, Arquers | 2025-04-09 | 2025-07-04 | 2 |
| 292423 | Partial plan, La Cort II | 2022-07-07 | 2022-07-19 | 10 |
| 287638 | Special plan, tanatori extension | 2021-04-26 | 2021-06-22 | 2 |
| 133393 | Special plan, Muntanya de Sal / Vall Salina | 1990-05-30 | 1990-08-22 | 32 |
| 294096 | Urban improvement plan, Colònia Arquers | null | 2025-08-19 | 3 |

Dates come only from detail fields `dataAprovacio` and `dataPublicacio`,
respectively. Generic inventory `data` stays in `source_metadata` with no inferred
meaning; generic output `fecha` is null. No agreement date is inferred from
filenames, registration entries, crawl time, news or page timestamps. The POUM
has later documentation changes and judicial/administrative documents: its
2015 approval field does not assert there were no subsequent legal changes.
`fase=vigente` reflects inventory `vigencia=SI`, not a construction milestone.

Each RPUC identifier creates one stable record; nested document-tree entries
are grouped and deduplicated by `idDocument`, retaining category paths, titles,
links and original flags (`portal`, `baixa`, `afectat`, `recurs`). Historical and
judicial documents are retained as provenance, not emitted as separate projects
or labelled individually current. Source register entries (`assentaments`) and
bulletin references are retained. Document URLs use the frontend's public
`documents?documentId=...&downloadType=inline&idioma=ca` scheme. One actual POUM
agreement PDF (269226) was fetched successfully and its PDF signature verified;
all 226 PDFs were not downloaded or text-parsed. Document trees, rather than
flat detail document lists, supply the public categorized attachments.

## Pagination, failures and updates

Despite its name, `firstRecord` is a **one-based page number**, as confirmed by
frontend code and live probes. Treating it as a row offset returns an empty page;
the first implementation correctly failed closed before writing output, and was
corrected to page numbers. Evidence preserves that failed probe separately.
The successful run traverses all three pages, checks the declared total and
municipal filter, and rejects empty premature pages, changing totals, repeated
identifiers or counts exceeding the total. Detail identity and nonempty document
trees are required. HTTP/JSON/schema errors propagate; there is no placeholder
fallback. Output is replaced only after all selected dossiers succeed.
Updates refresh the complete scoped snapshot; they do not claim an incremental
history or all planning ever approved. Registry ordering changes that preserve
total and avoid duplicate identifiers cannot be ruled out without server-side
snapshot support.

## Validation and local evidence

- `python -m unittest municipio.test_cardona -v`: 6 tests passed using the
  specified venv Python. Tests cover separate/missing/invalid dates, nested
  document grouping, stable identity, municipal/detail mismatches, excluded
  forms/procurement types, malformed inventory, full pagination, repeated pages,
  changing totals, premature exhaustion, preserving previous output on failure,
  manifest loading and disabled licences.
- Real extraction through `load_manifest('cardona')`, `load_portal_adapter` and
  `backfill_proyectos`: 11 records, 23 inventory entries, 12 exclusions,
  226 document links. The existing entity policy reports 11 total, 2 unknown,
  status ok; this classification is not manual verification of those categories.
- `evidence/proyectos.jsonl`: actual live rows, including the shared policy's
  annotations. `evidence/validation.json`: count, exact live request URLs,
  limitations, parser test result and PDF link check.
- `evidence/live-success/`: complete API response captures, including all three
  inventory pages and all 22 dossier detail/tree responses. Discovery HTML,
  frontend JavaScript, probes and `poum-acord-2015.pdf` are also local evidence.
  These evidence files are not source changes and are not committed.
- No coordinates, parcel matches or municipal centroids were fabricated. No
  licence register or physical-works inventory is claimed. No shared source or
  dependency changes, deployment, database access, installation or git mutation
  was needed.
