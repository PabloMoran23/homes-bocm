# La Sénia — INE 43044, Tarragona, Catalunya

Verified on 2026-11-09 with the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
This adapter extracts actual physical public-works projects, with deliberately
partial coverage. It does not extract granted licences. Scheduling and missing
coordinate jitter are disabled; every record has `publication_ready: false`.

## Official source discovery

- [Municipal website](https://lasenia.cat/web/) exposes current approval notices,
  including the Casa de Cultura and sports-hall roof notices published 2026-11-03.
  These are formal notices of identifiable physical works, not procurement notices.
- [Urbanisme](https://lasenia.cat/web/urbanisme/) describes the department and
  links to POUM/RPUC. Its generic service description is not emitted as a project.
- [Official transparency planning inventory](https://seu-e.cat/ca/web/lasenia/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic)
  links to the Generalitat RPUC municipality search with `municipiSel=43044`,
  independently confirming the municipality identifier. It provides external
  RPUC/MUC access, rather than an HTML table of individual planning instruments.
- The municipal navigation links to
  [RPUC dossier 283524](https://dtes.gencat.cat/rpucportal/#/consulta/fitxaExpedient/283524).
  Live HTTP 200 returns a JavaScript application shell. No planning rows,
  approval dates or feature geometry are inferred from that shell. The older
  municipal RPUC link uses public code `2018/67801/E`; neither is used as a works
  expediente number.
- [Municipal WordPress posts endpoint](https://lasenia.cat/web/wp-json/wp/v2/posts)
  is the extractable official inventory used by this adapter. The initial
  unrestricted `search=projecte` discovery returned 128 posts across two pages
  at `per_page=100`. This was discovery only, not an exhaustive historical scrape.
  Actual extraction restricts publication to after `2025-08-01T00:00:00` and
  follows **all** response-header pages at `per_page=20`. Exact requested URLs
  are recorded in `evidence/validation.json`.

## Coverage and grouping

The live scoped inventory contains **27 posts across two pages**. The parser
selects **17 formal approval/correction notices grouped into nine instruments**:

| Instrument family | Notices | Linked documents |
| --- | ---: | ---: |
| Storm-damaged municipal paths, November 2024 storm | 2 | 1 |
| Urbanisation of streets adjoining Plaça Montsià | 3 | 2 |
| Casa de Cultura improvement, adaptation and modernisation | 2 | 2 |
| Sports-hall roof doubling against leaks and energy improvement | 1 | 1 |
| Barranquet street stormwater collector repairs | 2 | 1 |
| Drinking-water distribution network digitalisation | 2 | 1 |
| Fibre-cement drinking-water pipes, service connections and valves renewal | 1 | 1 |
| Northern access renewal, Osca–Santander section | 2 | 1 |
| Northern access renewal, Santander–T-1040 section | 2 | 1 |

These are reviewed title-based identity families, not a fabricated record list.
Titles, publication dates, notice IDs, narratives and document links come from
live responses. Other families and notices outside the date/search scope are
excluded. This is not complete municipal works or planning coverage. A new
family requires review of its identity aliases; scheduling remains disabled.

The two northern sections remain distinct. Initial/definitive approvals and the
Plaça Montsià correction remain within their respective instrument. Casa de
Cultura has June and November 2026 versions with different budgets; both notices
and documents remain attached, without claiming they are identical revisions.
Each notice retains its source post URL, API URL, WordPress ID, phase, publication
date, explicit agreement date, description and its own document links. Top-level
fields describe the latest notice, not an invented final project status.
Document URLs are deduplicated per notice and per instrument. File titles such
as `Baixa` are not separate projects. Source descriptions remain `descripcion`.

## Dates, documents and geometry

`fecha_publicacion` is the municipal WordPress `date` field. It is not the BOPT
publication date. Only explicit HTML `acord de Ple ... de data` or mayoral
resolution dates populate `fecha_acuerdo`; generic `fecha` and `fecha_aprob`
remain null. Earlier notices keep their own dates even where the latest notice
contains only a PDF. Signature timestamps, filename dates and crawl dates do
not become approval dates.

For example, Plaça Montsià has municipal publication 2025-11-18 and an explicit
agreement of 2025-10-27. The November Casa de Cultura notice was published on the
web 2026-11-03; its linked BOPT PDF states publication 2026-11-02 and resolution
2026-10-29. The sports-hall PDF distinguishes BOPT publication 2026-10-30 from
resolution 2026-10-28. These two PDFs were manually inspected and captured for
research; the adapter **does not parse PDFs**, so their agreement dates remain
null in automated records. No dates are hardcoded from this manual inspection.

All **11 distinct document URLs** were fetched live with streaming reads and
verified to return HTTP 200 and a PDF signature. This verifies accessibility,
not every page of their contents. `document-checks.json` records the checks.
The two recent BOPT notices have full PDF/text captures. No geometry or project
coordinates were verified. `lat`, `lon` and `geometry` remain null; a municipal
centroid is not substituted.

No usable public granted-licence inventory was established from these sources;
forms, generic departmental pages, grants, employment programmes, ordinance
consultations and procurement announcements are not licence or project records.
The shared entity classifier leaves these nine grouped instruments `pendiente`
because it requires identity evidence such as an expediente number that this
source does not consistently provide. No expediente is synthesized to bypass
that policy. Parser readiness does not imply publication readiness.

## Validation and reproducibility

Run from the repository root:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_la_senia -v
```

Eight tests pass: dates and duplicate document links; initial/final/correction
grouping and stable identity; rejection of forms/procurement/unrelated projects;
unknown PDF-only dates and rejection of login-only content; distinct street
sections; full multi-page updates; duplicate/changing/empty/incomplete pagination
rejection without replacing previous output; manifest identity and disabled
licences/scheduling/jitter.

Live extraction used `load_manifest('la-senia')` and `load_portal_adapter`, with
`manifest.portal.config['capture_dir'] = 'evidence'`, then
`adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`. The registry's
existing entity annotation ran normally. Backfill/update replace a complete
scoped snapshot atomically after successful fetching/parsing. Header totals must
remain stable, IDs cannot repeat and fetched count must equal `X-WP-Total`;
failures raise instead of silently truncating pagination or overwriting output.

Local, uncommitted evidence under `evidence/` includes `proyectos.jsonl`,
`validation.json`, both extracted inventory pages, discovery HTML/JSON, the RPUC
shell, document checks and two BOPT PDF/text captures. Live result: nine genuine
projects, seventeen notices, eleven linked documents, zero invented coordinates.
Only the manifest, this research note, the adapter and its test module are source
changes. No shared files, dependencies, credentials, publishing or deployment
operations were needed.
