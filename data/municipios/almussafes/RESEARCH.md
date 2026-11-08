# Almussafes — INE 46035, Valencia

Verified 2026-11-08 with the preinstalled batch Python runtime. This adapter
extracts genuine planning instruments from the municipality's current-planning
inventory. Coverage is deliberately partial at municipal level. Scheduling,
granted-licence extraction and missing-coordinate jitter are disabled.

## Official source discovery

- [Urbanisme](https://almussafes.net/departamentos/urbanismo/) — HTTP 200;
  municipal department index links to Serveis and separately to licence services.
  Department contact coordinates/addresses are not instrument geometry.
- [Urbanisme – Serveis](https://almussafes.net/departamentos/urbanismo/serveis-urbanisme/)
  — HTTP 200; the `PLANTEJAMENT VIGENT` table contains five numbered instruments
  and eight document links. This is the complete selected inventory, with no
  pagination or load-more controls. The following industrial-park history and
  slideshow are outside the table and are excluded.
- [Transparency planning inventory](https://almussafes.net/portal-de-transparencia/economica/plans-urbanistics/)
  — HTTP 200; mixes planning, environmental public-information applications,
  emergency plans and other policies. Its initial ten entries are followed by
  dynamic `MOSTRAR MÉS`. This adapter does **not** extract that archive or claim
  those initial entries are its complete contents.
- [PGE 2025 dossier](https://almussafes.net/plans-programes-i-projectes-pla-general-estructural-durbanisme-2025-transparencia/)
  — HTTP 200; separately identifies the structural-plan revision as `EN
  TRAMITACIÓ`, with final-proposal edict and DOGV notice. The 23/09/2025 and
  01/10/2025 dates label those publications/documents; they are not evidence of
  definitive plan approval. This pending revision is outside the selected
  current-planning table and is not merged into its Pla General record.
- [Revision documentation](https://almussafes.planifica.org/documentacion) —
  discovered through web search; search index describes partial PGE/POP dossier
  documents and an addendum. Direct HTTPS connection was refused during local
  verification. It is not an adapter dependency and its contents are not emitted.

## Extracted inventory and provenance

| Instrument as listed by the municipality | Grouped document labels |
| --- | --- |
| PLA GENERAL | MODIFICACIONS; NORMATIVA |
| PLA PARCIAL ÁREA INDUSTRIAL ALMUSSAFES | MODIFICACIONS; NORMATIVA; PLÀNOLS |
| PLA ESPECIAL AMPLIACIÓ PARC INDUSTRIAL | NORMATIVA |
| PLA ESPECIAL LA TORRE | PLA ESPECIAL LA TORRE |
| PLA PARCIAL PORTETA | PLA PARCIAL PORTETA |

Every document retains its original URL and municipal `url_procedencia`.
Two normative PDFs are hosted directly by the municipality; six links point to
Google Drive file views explicitly linked by this municipal table. The two
municipal PDFs returned HTTP 200 and were captured locally. Drive contents were
not downloaded, parsed or authenticated; their accessibility is not asserted.
Modification collections remain attached to their parent instrument rather than
being expanded into invented individual dossiers. Documents are not extra
projects. No procurement notices, forms, news or granted licences are emitted.

The source heading supports only “vigente según inventario municipal”, not a
specific approval event or independent legal verification. All date fields
(`fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob`) remain null because
the table supplies none. Upload-folder years, crawl time and dates in unrelated
industrial-park prose are never substituted. No coordinates, centroids or
polygons are inferred; geometry fields are null and `publication_ready=false`.
The shared registry annotator leaves all five Valencian titles as `pendiente`
(`insufficient_identity_evidence`, activity_eligible false). That classification
limitation is preserved in evidence; no shared policy was changed.

## Adapter behaviour

The parser requires the municipal article content, a unique current-planning
heading, its adjacent two-column table, the expected column labels, consecutive
numbered instrument headings and document links for every instrument. It reads
all rows without a record cap. Unrecognised rows, incomplete groups, duplicate
instrument titles, unexpected document URLs or pagination controls fail the run.
A future source change cannot silently produce a partial successful snapshot.
Instrument identity hashes the accent-normalised source title, independent of
row position and document order. A changed instrument title changes its ID.

Backfill fetches the live page with a timeout and a 4 MB bounded response, parses
it completely before replacing output atomically, and optionally captures the
source via `portal.config.capture_dir`. Updates refresh the same full snapshot;
no date-based incremental assumptions or state cursor are used. Licence methods
return disabled with empty output. HTTP or parsing failures preserve previous
project output.

## Validation and local evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `python -m unittest municipio.test_almussafes -v`: **5 tests passed** covering
  grouping and identity, null date/geometry semantics, incomplete/changed markup,
  pagination rejection, exclusion of unrelated prose, manifest resolution and
  preservation of existing output when a live response cannot be parsed.
- Live extraction used `load_manifest('almussafes')`,
  `load_portal_adapter(manifest)` and
  `adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`, with capture_dir
  set locally to `evidence`. Result: **5 records, 8 document links**, no invented
  dates or coordinates; shared entity-policy annotations retained.
- `evidence/validation.json` records live count, source URLs, limitations and
  discovery results. `planeamiento-vigente.html` captures the actual adapter
  response. Additional HTML captures, two municipal PDFs and `discovery.json`
  document investigation. Evidence is local and excluded from source changes.

Only the four municipality-specific source files are added. No dependencies or
shared sources were changed; no publishing or production actions were performed.
