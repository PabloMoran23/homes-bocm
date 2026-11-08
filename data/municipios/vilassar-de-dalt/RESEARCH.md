# Vilassar de Dalt — INE 08214, Barcelona

Verified live on 2026-11-07 with the preinstalled batch Python runtime. This
adapter covers two official planning document inventories, not all municipal
projects, physical works or granted licences. Scheduling and coordinate jitter
are disabled. Records have `publication_ready: false` and null geometry.

## Discovery and official sources

The municipal territory index at
https://www.vilassardedalt.cat/temes/territori returned HTTP 200 and links directly
to both inventories used by the scraper:

- https://www.vilassardedalt.cat/temes/territori/pla-dordenacio-urbanistica-municipal-poum
  — HTTP 200. One POUM dossier with 121 document rows: normative texts, memoranda,
  environmental studies, economic studies, sector sheets and plans. All 121 links
  are retained within one instrument, with their table section labels. A sector
  sheet or viability annex is not emitted as an independently approved project.
- https://www.vilassardedalt.cat/temes/territori/planejament-urbanistic-en-tramit
  — HTTP 200. Eleven document rows grouped into three instruments:
  Desclassificació sector Matagalls (1 document), Pla parcial de Can Reig
  (8 documents), and Horts de Can Jaumetó (2 documents). For the generic
  “Modificacions puntuals en tràmit” category, the first document label names the
  Matagalls instrument. Continuation rows belong to the preceding instrument.

The alternative municipal information-official POUM route,
https://www.vilassardedalt.cat/ajuntament-seu-electronica/informacio-oficial/urbanisme/poum,
was also inspected and contains the same document inventory. It is not ingested
again. The `.org` host appearing in search results is not a separate inventory.

The public procedure catalogue at
https://seu-e.cat/es/web/vilassardedalt/tramits-i-gestions/-/tramits/classificacio/urbanisme
lists applications and notifications, including major/minor works applications.
It is not a granted-licence register. Licences are disabled; no forms become
records. The territory page also links a Google map of street improvements;
that embedded map was not ingested or treated as verified project geometry.
News, procurement and municipal government competency descriptions are excluded.

## Provenance, status and date limitations

These are currently accessible inventories whose content includes older planning
documents. Their labels and update timestamps do not establish present legal
status. The adapter retains inventory title, document title, section and exact
absolute document URL. The original page-update text is stored separately as
`source_page_updated_text`; it is never an approval or publication date.

Four sample PDFs, one per record, were fetched successfully (HTTP 200, PDF
signature) and captured locally. Their first two pages were extracted with the
already installed `pdftotext` for manual source verification:

- The POUM modification justification identifies the municipal POUM and March
  2013 consolidated text. It mentions different CTUB agreement dates on the
  cover and following page (31 January and 12 February 2013). Neither is
  automatically promoted to the POUM approval date.
- The Matagalls PDF identifies modification number 6 of the POUM for the
  declassification of the Matagalls partial-plan sector, dated May 2020.
  That document date is not a grant, agreement or publication date.
- The Can Reig memorandum explicitly refers to the plenary definitive-approval
  agreement of 21 December 2020 and is dated January 2021. This demonstrates why
  membership in the “en tràmit” index cannot establish current procedural phase.
- The Can Jaumetó PDF identifies the landscape-integration study for demolition
  of existing buildings. It is grouped with the POUM modification memorandum,
  not represented as a granted demolition licence or completed physical work.

The extraction parses HTML inventories, not PDF legal narratives. Consequently
`fase`, `fecha`, `fecha_publicacion`, `fecha_acuerdo` and `fecha_aprob` remain null,
even where manual PDF review identifies a historical agreement. This deliberately
avoids assigning a document's date to the wrong event. All 132 document links
are retained; only four PDFs were downloaded for verification. Link availability
and legal contents of the remaining PDFs have not been individually verified.
No coordinates, parcels, centroids or vector boundaries are inferred from plans.

## Parser and refresh behavior

Both live indexes contain their entire document table in one HTML response,
without pagination controls. Every table row is parsed. The adapter raises on
pagination controls/query parameters, absent or changed headings/table schema,
empty inventories, malformed/orphan rows, and unexpected document hosts/types.
It never returns a silently truncated first page. A future pagination mechanism
requires extending the crawler before extraction resumes.

Requests use a timeout, bounded 5 MB HTML response and official HTTPS host check.
Updates refresh both inventories in full, without a date cutoff. IDs derive from
the inventory URL and instrument title, independent of document order. Both
inventories must succeed before the JSONL snapshot is atomically replaced.
Disabled licence methods produce zero records.

## Validation and local evidence

Command:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_vilassar_de_dalt -v
```

Eight parser/contract tests passed: instrument grouping/provenance, POUM annex
aggregation, identity stability, rejection of empty/login/navigation sources,
pagination rejection, malformed/untrusted documents, preservation of an existing
snapshot on second-source failure, and manifest/disabled-licence behavior.

A live extraction was run via `load_manifest`, `load_portal_adapter` and
`backfill_proyectos`, using the same installed runtime. Result: **4 actual
planning records, 132 linked documents**, no invented dates or coordinates.
The existing entity-policy wrapper returned status `ok`, with all four records
classified `unknown`; no unsupported residential category is asserted.

Local, uncommitted evidence under `evidence/`:

- `proyectos.jsonl`: actual adapter output, including policy annotations.
- `validation.json`: count, source URLs, limitations, test command/result,
  per-record document counts and sample PDF URL/hash/status metadata.
- `poum_live.html`, `processing_live.html`: captures from the live adapter run.
- `territori.html`, `poum.html`, `poum_current.html`, `tramit.html`: discovery captures.
- `document_sample_1.pdf` through `document_sample_4.pdf` and corresponding `.txt`
  files: source verification samples in output-record order.

Only the municipality manifest, this research note, adapter and parser test are
source additions. No shared code/dependencies, credentials, deployment or
publishing operations are involved.
