# Centelles — INE 08067, Barcelona

Verified live on 2026-11-08 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
This adapter exports a partial snapshot of real municipal planning instruments and
physical works, with scheduling and licence extraction disabled. It is not a full
historical register. No geometry was verified: `publication_ready` is false and
coordinates remain null, with jitter disabled.

## Official inventories

- https://www.centelles.cat/ajuntament/informacio-oficial/planejament-urbanistic
  — HTTP 200, curated planning-document inventory, page updated 5 November 2026.
  Six grouped instruments: MP42, MP39 Casa Pujol, MP44 La Gavarra, Casa Ripoll,
  MP45, and the PMU for carrer Mare de Déu del Pilar 3. The page-update date is
  not an instrument publication or approval date.
- https://www.centelles.cat/viure/urbanisme-i-medi-ambient/urbanisme
  — HTTP 200, municipal urbanism documentation page, updated 15 October 2026.
  The adapter reads only the physical-works section (`PROJECTE D'OBRES` and
  `Projecte executiu Vapor`): Palau dels Comtes phase 2 project modification and
  the Vapor municipal-parking photovoltaic project. The four numbered
  installation documents remain together under the source's Vapor heading;
  installation numbers and capacities remain in their individual document labels.
  Existing general PGO, PEPCH, mobility and regional-plan links on this page
  are deliberately outside the implemented snapshot.
- https://www.centelles.cat/ajuntament/tramits/urbanisme-i-obres/
  — discovery identified a catalogue of applications, not a granted-licence
  inventory. Forms are excluded. Municipal meeting minutes may contain individual
  decisions, but their historical extraction is not implemented or claimed.
- Municipal links to MUC/RPUC/SITMUN are geographic/register discovery links,
  not verified project geometry. No municipal centroid is substituted.

## Grouping and provenance

The planning page contains unusual sibling ULs rather than consistently nested
lists. The parser associates subsidiary lists with the preceding instrument.
MP44 has seven documents: advance, environmental assessment, Catalan memory and
annexes, Spanish memory and annexes, and the initial-approval summary. They are
one La Gavarra amendment, not seven projects. The six PMU documents include the
original project, technical report, public-information announcement, extension,
provisional project and council certificate. Every document retains its label,
absolute URL and inventory source URL. Stable record IDs use instrument keys or
the actual Palau project-document URL; dates and document counts do not determine
identity. Repeated document URLs are deduplicated within the instrument.

The Osonament surface-right agreement and its two attachments are excluded:
a land-right decision alone is not a verified construction project or granted
licence. Procurement announcements, general news, subsidies, service explanations
and navigation do not become records.

Neither inventory is paginated in the captured source. The complete selected
sections are traversed without a record-count cap. Pagination controls, next
links or page/offset parameters cause an explicit failure for review, rather than
a truncated success. Missing headings, empty records, unclassified planning
entries or unexpected document hosts/formats also fail. Both inventories must
parse successfully before atomic output replacement. Updates refresh the whole
snapshot; disappearance means disappearance from this inventory, not revocation.

## Date semantics and limitations

Month/year labels such as November 2022 or April 2026 remain document text, with
no invented day or approval event. “Document per a l’aprovació inicial” does not
establish that approval occurred. Generic `fecha`, publication dates, and phases
without explicit evidence remain null. The PMU certificate label explicitly
states the council meeting on 20 July 2026 and provisional approval; only that
record receives `fecha_acuerdo` and `fecha_aprob` = `2026-07-20`, with the exact
certificate URL as provenance. The live certificate was also downloaded for
manual verification: its body confirms the 20 July meeting and provisional
approval; electronic signatures dated 22 July are not used as agreement dates.
The adapter reads inventory labels, not PDF bodies, and does not infer other
approval histories, completion status, budgets or coordinates.

## Validation and local evidence

- `python -m unittest municipio.test_centelles -v`: seven offline tests pass,
  covering grouping, document provenance, distinct date meanings, absent
  geometry, excluded forms/agreements, pagination rejection, missing/changed
  sources, stable refresh, output preservation on failure and manifest loading.
- Direct live `CentellesAyuntamientoAdapter.backfill_proyectos`: eight records,
  22 distinct document links. All 22 returned HTTP 200 and PDF signatures when
  checked using streaming GETs. This verifies document availability, not full
  semantic parsing of those PDFs.
- `evidence/proyectos.jsonl`: actual live records.
- `evidence/validation.json`: timestamp, live count, source URLs, document checks,
  parser-test result and coverage limitations.
- `evidence/planejament.html`, `evidence/urbanisme.html`: complete source captures.
  `evidence/pmu-certificat.pdf` and its text extraction preserve the manual date
  verification. Evidence is local and excluded from source changes.

Only the municipality manifest, this research note, its adapter and its parser
test module are source additions. No shared code, dependencies, databases or
publication tools are changed or used.
