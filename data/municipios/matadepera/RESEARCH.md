# Matadepera — Barcelona — INE 08120

Verified 2026-11-07 using the preinstalled batch virtualenv. This adapter extracts
real municipal ordinary public-works dossiers, with deliberately partial municipal
coverage. Scheduling and licences are disabled; no missing coordinates are jittered.
No deployment or publication is authorized or performed.

## Official source discovery

- Urbanism inventory: https://seu-e.cat/ca/web/matadepera/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme
  (HTTP 200). Official transparency portal identifies Ajuntament de Matadepera and
  links to planning, municipal works and several special projects in nonurban land.
- Implemented source: https://seu-e.cat/ca/web/matadepera/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/projectes-d-obra-municipal-204
  (HTTP 200). The page explicitly publishes documentation for ordinary local works
  subject to public information. Its page-update date is 19/05/2026, which is not
  used as any project's publication, approval or execution date.
- Planning inventory: https://seu-e.cat/ca/web/matadepera/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  (HTTP 200, captured). A separate current inventory of POUM, modifications,
  special plans, urban improvement plans and pending instruments; page updated
  20/10/2026. Not part of this adapter's scope and not claimed as extracted.
- Discovery also surfaced AOC catalogue entries describing *requested* building
  licences, including staging/development catalogue hosts. They are not proof of
  granted licences and were not used. Procurement search results and general news
  were likewise not used as project records.

## Extraction and provenance

The complete single-page works inventory yields **32 dossier groups**. Examples
include school ventilation, Can Prat sewer renewal, structural works at Can Vinyers,
photovoltaic installations, municipal street improvements and forestry firebreaks.
There are 249 document anchor occurrences; 242 links remain after deduplicating
URLs inside each dossier. Every published document URL is retained. Repeated links
across dossiers remain in each published association.

One record corresponds to one heading published by the municipality. The headings
covering two schools, three collectors or nine photovoltaic projects remain bundled
records, with all their technical and administrative documents. Reports, budget
parts, plans, certificates and announcements do not become separate projects.
Two explicit expediente references, X2025007096 and X2025009638, are retained.
Document folder numbers are only source folder identifiers, never expediente IDs.
Stable scraper IDs hash the source heading; changed heading text changes identity.

The source has some document links pointing into other folders, particularly in the
photovoltaic/EDAR area. The adapter retains these as published, adds a warning on
mixed-folder groups and makes no claim to independently validate every attachment's
association. A certificate and associated technical project for school ventilation
were downloaded live and confirmed to be PDFs (HTTP 200), with hashes and URLs in
validation.json. The remaining attachments are retained links, not downloaded or
individually interpreted decisions.

Nine records have explicit initial-agreement dates in the page narrative. These
populate fecha_acuerdo and fecha_aprob; fecha_publicacion and generic fecha stay
null. Dates in filenames, announcement labels, crawl time and the page-update
footer are not substituted. A decree date present only in an attachment label is
therefore not extracted. Initial approval is distinguished from definitive approval
and from completion of works; only an explicit initial phase is normalized. Other
phases remain null, with the original title and narrative preserved.

No geometry is derived from PDF plans, municipal centroids or approximate addresses.
lat, lon and geometry are null and publication_ready is false throughout. The shared
entity-policy wrapper classifies 30 records as pending because no municipal expediente
is stated, reporting adapter_incident / unknown_entity_spike; two explicitly referenced
records satisfy that identity guard. This is preserved in evidence, not bypassed by
inventing references. The extraction is reviewable but not ready for publication.

## Completeness and validation

The page is a static, unpaginated inventory. All recognized dossier headings and all
document URLs are processed; there is no record-count slice. A next-page link raises
an error instead of silently accepting a truncated snapshot. Changed/missing source
markup, empty records, missing technical documentation, duplicate headings or
unexpected document hosts also fail. Requests have a timeout and a bounded response;
oversize responses fail rather than being parsed partially. Updates replace a full
snapshot and do not use a date watermark that could conceal amended older dossiers.

Executed successfully:

```
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_matadepera -v
```

Eight parser/integration tests cover grouping and deduplication, paragraph headings,
explicit date semantics, unknown dates, bundled projects and mixed folders, exclusion
of forms and standalone announcements, pagination rejection, stable identities,
manifest loading, disabled licences and full-snapshot update delegation.

A real live extraction used load_manifest('matadepera'), load_portal_adapter and
backfill_proyectos. Local evidence (not source files to commit):

- evidence/proyectos.jsonl: 32 actual records, including shared policy annotations.
- evidence/validation.json: live count, URLs, limitations, checks, PDF capture hashes
  and the shared policy incident.
- evidence/live-public-works.html: exact HTML consumed by the live adapter.
- evidence/urbanisme.html and evidence/planejament-urbanistic.html: discovery captures.
- evidence/projectes-d-obra-municipal-204.html: initial inventory capture.
- evidence/sample-document-1.pdf and evidence/sample-document-2.pdf: source samples.
- evidence/proyectos.entities.json: shared entity-policy report.

Coverage is the currently displayed ordinary-works inventory, not a complete archive,
not the separate planning inventory, not a granted-licence register and not a reliable
statement of current construction status. Shared source files and dependencies were
not modified.
