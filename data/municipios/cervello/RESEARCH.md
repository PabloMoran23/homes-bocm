# Cervelló — Barcelona — INE 08068

Verified live on 2026-11-07 with the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
This adapter extracts physical public works from the municipal inventory.
Coverage is partial; it is not a comprehensive urban-planning or granted-licence
register. Do not confuse Cervelló with the separate municipality La Palma de
Cervelló. The transparency portal's official RPUC link explicitly selects 08068.

## Official source discovery

- https://www.cervello.cat/ajuntament/organitzacio-administrativa/obra-publica
  — HTTP 200. Actual municipal project inventory, with approval notices and
  attached technical documents. The live first page includes the initial
  approval of the mobility/traffic-safety project agreed on 2026-09-23.
- https://www.cervello.cat/ajuntament/organitzacio-administrativa/obra-publica?pag=2
  — HTTP 200. Second inventory page, followed in full. Both pages advertise
  two pages. Combined: 62 distinct detail URLs, all fetched successfully.
- https://www.cervello.cat/ajuntament/urbanisme — HTTP 200. Provides urban
  regulations and links to RPUC and the AMB planning viewer, rather than an
  independently structured project inventory. Not turned into project rows.
- https://seu-e.cat/ca/web/cervello/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  — HTTP 200. Refers to the RPUC municipal search at
  https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=08068.
  RPUC and AMB inventories are outside this adapter's deliberately limited
  coverage; their content/geometry was not extracted.
- https://www.cervello.cat/tramits/tramits-i-gestions — HTTP 200. Procedures and
  application information are not evidence of granted licences. No verified
  structured granted-licence inventory was established; licences remain disabled.

## Records, grouping and semantics

The live adapter returns **46 projects**, from **48 included approval notices**,
with **91 document links with notice provenance**. Fourteen policy-plan notices
are explicitly excluded: civil protection, fire-prevention, delimitation and
supramunicipal air-quality plans. Every included live project has attachments.
The scope is works projects or a valued works memorandum; procurement, reusable
licence forms, navigation and unrelated news are not extracted as activities.

Each detail is one notice, not one row per PDF. All links from its Documents
section are retained, including plans, budgets, memoranda and annexes. Normalized
instrument titles group notices differing only in approval wrapper/typography:
Les Rovires sewer works and the football-field canopy each have initial and
definitive notices, preserved under `anuncios` on one project. Definitive titles
have precedence. Distinct works, years, sites and construction phases are not
fuzzily merged. Identity is a deterministic hash of the normalized instrument
name, not an invented official expediente number.

`fase` comes from the actual approval title, including the source's misspelling
“difinitiva”. Conditional wording about eventual definitive approval cannot
advance an initially approved project. The narrative is preserved as
`descripcion`, including any quoted agreement, publication and author dates.
Only explicitly dated council sessions are parsed as `acuerdos`; the date is
copied to `fecha_acuerdo` only when the adjacent actual approval wording proves
that it belongs to the notice's approval stage. For example, the Pota-Roges
kitchen notice records an initial agreement on 2026-05-12 and mentions BOP
publication on 2026-05-21, followed by definitive approval without an explicit
date: its definitive `fecha_acuerdo` stays null. Website “Darrera actualització”
is never used as publication or approval. `fecha_publicacion` and generic
`fecha` remain null: no unambiguous publication field was extracted. Some dates
are therefore retained only in the original text. PDFs are linked, not parsed,
and their availability/signatures have not been individually validated.

No verified project geometry is available from the parsed HTML. `lat`, `lon`
and `geometry` remain null and `publication_ready` is false. No geocoder,
centroid or jitter is used. Schedule, jitter and licences are disabled in the
manifest. These results do not claim completed construction or map readiness.

## Completeness and validation

The adapter follows all exposed pagination URLs, checks declared page counts,
deduplicates detail URLs and fails on unexpected pagination, changed/empty
inventory markup, missing details or projects lacking both narrative and
documents. The 100-page safety bound and 5 MB HTML limit raise errors rather
than silently truncate. HTTP failures abort the snapshot. Output replacement is
atomic after the complete crawl succeeds. Updates refresh this entire inventory;
there is no historic deletion log. Capture mode saves the exact fetched HTML
under SHA-256 URL filenames and is enabled only for local evidence.

Validation command:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_cervello -v
```

Five tests passed: date/stage separation and conditional approval; grouping and
document provenance; invalid content and policy exclusion; complete pagination,
page-count mismatch and atomic failure; manifest identity and disabled licences.
A real `CervelloAyuntamientoAdapter.backfill_proyectos` run returned status `ok`,
46 rows, 62 detail pages, 48 included notices and two inventory pages. Unique IDs,
INE identity and null coordinates were checked on the output.

Local evidence (not committed): `evidence/proyectos.jsonl`,
`evidence/validation.json` (live_records, complete source_urls, exclusions,
limitations and test result), `evidence/live-captures/*.html`, discovery captures
and `evidence/research-sources.json`. No shared source or dependency changes,
credentials, external workspaces, database, deployment or publishing tools were
used.
