# Castellbisbal — INE 08054, Barcelona, Catalunya

Verified anonymously on 2026-11-07. This adapter extracts a partial municipal
planning-instrument inventory, not granted licences. Scheduling and coordinate
jitter are disabled. No database, publishing or deployment operations are needed.

## Discovery and source selection

- [Municipal POUM index](https://www.castellbisbal.cat/ajuntament/normativa/pla-dordenacio-urbanistica-poum)
  links the official Normativa urbanística transparency page, memory, maps and
  modifications. This establishes the municipality's provenance for seu-e.cat.
- [Normativa d'urbanisme — extraction source](https://seu-e.cat/ca/web/castellbisbal/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/normativa-d-urbanisme)
  returned HTTP 200 with the full server-rendered five-column table. The table
  contains 19 document rows: five POUM norms/resolution documents (including
  translations) and two documents each for amendments 1, 2, 3, 5, 6, 7 and 8.
  Those become **eight instruments**, not 19 independent projects. Amendment 4
  is absent and is not invented. The table's update timestamp is 25/06/2025;
  another explanatory block is updated 08/09/2026. Neither is an agreement date.
- [Municipal modifications inventory](https://www.castellbisbal.cat/ajuntament/normativa/pla-dordenacio-urbanistica-poum/modificacions-poum/)
  returned HTTP 200 with five entries (1, 2, 5, 6, 8), no populated pager.
  It is less comprehensive than the transparency table. Its amendment 8 page
  publication is 26/05/2021 and its title says 14 febrer 2021, whereas the
  transparency table dates both amendment 8 documents 07-02-2020. We use the
  table dates strictly as dates stated by that source, without reconciling these
  different publications into a legal approval date. The inventory's amendment
  2 approval narrative has a truncated year, another reason not to infer dates.
- [Municipal public-works inventory](https://www.castellbisbal.cat/ajuntament/projectes)
  returned HTTP 200 with four named initiatives: central-street reform, residence
  and services for older people, Carrer de la Lluna urbanisation, Can Pedrerol de
  Dalt restoration. These are genuine candidates for future coverage but are
  outside this adapter's deliberately bounded planning-document inventory.
- [Planning transparency index](https://seu-e.cat/ca/web/castellbisbal/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic)
  refers to RPUC/MUC. A complete register/geometry extraction is not implemented.
- [Private works page](https://www.castellbisbal.cat/municipi-per-temes/obres-privades)
  lists application procedures. These are not evidence of granted licences and
  are excluded. News and procurement notices are also excluded.

Discovery used public web search and live anonymous HTTP reads; no authentication.
The extraction itself requests only the selected Normativa d'urbanisme source.

## Semantics and grouping

The stable municipality-scoped identity is the POUM or its municipality-labelled
amendment number; this is not a fabricated expediente number. The main POUM's
Catalan/Spanish norms and 2009 resolutions are grouped under that one instrument.
Every link retains its row title, language, source URL and publication date.
The record-level publication date is set only when all attached documents share
one date. Thus the main POUM's date is null while its document dates remain intact.
`fecha`, `fecha_acuerdo`, `fecha_aprob` and `fase` remain null: the table provides
no unambiguous agreement/approval dates or procedural phases. Document types are
not phases. No coordinates, municipal centroids or geometry are substituted.

Municipal document labels are the identity evidence. The adapter does not parse
PDF contents or claim independent legal validity. The source includes a public
comment reporting an incorrect Spanish amendment 7 attachment, with a municipal
reply on 13/05/2026 stating it was corrected. Links and labels are retained as
currently served, with no attempt to guess contents or historical replacements.
One resolution attachment was independently fetched: HTTP 200, application/pdf,
PDF signature verified, 41,258 bytes. Other attachment bodies were not verified.

The existing shared entity classifier marks all eight records `pendiente` /
`insufficient_identity_evidence` because there is no numbered administrative
expediente; it reports status `ok` with unknown=8. No reference is fabricated to
force activity eligibility. These are usable planning source records but are
**not publication-ready** and need downstream review before activity ingestion.

## Completeness and failure handling

All 19 rows are in the initial HTML. The page initialises client-side DataTables
ordering/filtering/pagination without AJAX or serverSide data. The parser reads
every row regardless of visible browser page, including malformed nested `<tr>`
elements in the official HTML. It does not cap record counts. Active server
pagination or remote DataTable configuration raises an error. An empty, changed,
ambiguous or unsupported table, missing documents, invalid dates and unexpected
document hosts also fail instead of silently creating a partial success.

Only current table coverage is claimed: no deleted rows, historic snapshots,
full RPUC, complete works register or licence register. Updates replace a full
snapshot without a date cutoff, preserving old and newly listed instruments.
No incremental state timestamp is advanced. HTTP has explicit timeouts and a
4 MB response ceiling; exceeding it fails before output replacement. Successful
output replaces the JSONL atomically. Licence methods return disabled.

## Validation and local evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_castellbisbal -v`: **8 tests passed**. Tests cover
  malformed/nested rows, translation grouping, base-plan/resolution grouping,
  publication versus agreement semantics, missing and invalid dates, stable IDs,
  unrelated rows, absent documents, external URLs, pagination/AJAX rejection,
  no truncation of 30 instruments, full update delegation and disabled licences.
- Live `load_manifest('castellbisbal')` and registry-loaded adapter
  `backfill_proyectos(evidence/proyectos.jsonl)`: **8 records, 19 documents**.
  Manifest identity and required disabled flags, unique IDs and nonempty document
  groups were asserted. Shared entity annotation also ran through the registry.
- `evidence/validation.json`: live count, extraction URL, limitations, test result
  and shared entity-policy report.
- `evidence/normativa-live.html`: exact UTF-8 live extraction response.
  `normativa.html`, `modificacions.html`, `projectes.html`: discovery captures.
  `poum-resolucio-febrer-2009.pdf` and `document-check.json`: sample PDF provenance,
  response metadata and SHA-256 hash.

Evidence stays local. Only the manifest, this research note, adapter and parser
test module are source additions. No shared code or dependencies changed.
