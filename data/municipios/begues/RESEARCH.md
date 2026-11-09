# Begues — INE 08020, Barcelona, Catalunya

Verified live 2026-11-09 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
The scraper covers **numbered amendments to Begues's general plan**, not all
municipal projects or granted licences. Schedule and coordinate jitter are disabled.

## Official source discovery

The municipal Urbanisme index at
https://www.begues.cat/ajuntament/informacio-oficial/urbanisme/
links to Projectes urbanístics, Normativa urbanística, and Planejament i plans
territorials. The latter points to the official transparency portal:
https://www.seu-e.cat/web/begues/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme
The transparency planning page references Generalitat RPUC and MUC. Those viewers
are not scraped and no claim of a complete current legal planning register is made.

The normative index at
https://www.begues.cat/ajuntament/informacio-oficial/urbanisme/normativa-urbanistica/
includes a consolidated PGO text and other regulations. It is not a granted-licence
inventory. Consolidated norms, ordinances, application forms, generic services,
procurement notices and unrelated news do not become records.

The implemented inventory is:
https://www.begues.cat/ajuntament/informacio-oficial/urbanisme/projectes-urbanistics/
The live HTML exposes **10 pages and 111 entries**, rather than the 9 pages in the
search engine's older snapshot. Pages 2–10 use `?pag=N`. Every page is requested;
the declared total and active-page markers are validated. Missing pagination,
changed totals, repeated selected entries, empty pages, unexpected redirects,
missing detail documents and response-size bounds cause an error before output
replacement. The maximum page bound raises an error; it does not truncate output.

## Extracted instruments and document grouping

The live run selected 14 municipal publications and grouped them into **10 real
planning instruments**, amendments **23, 25, 26, 27, 28, 29, 30, 31, 34 and 35**.
There are 27 document links after deduplication within each instrument. For example:

- https://www.begues.cat/ajuntament/informacio-oficial/urbanisme/projectes-urbanistics/modificacio-puntual-del-pla-general-dordenacio-num-35.html
  publishes amendment 35 on 2026-08-19 and explicitly states initial approval by
  the municipal plenary on 2026-07-20. It links the plan, plenary certificate,
  legal and technical reports, and urban-planning agreement.
- https://www.begues.cat/ajuntament/informacio-oficial/urbanisme/projectes-urbanistics/modificacio-puntutal-pla-general-num-31-condicions-dedificacio-dels-edificis-dinteres-en-sol-no-urbanitzable-can-rigol.html
  records provisional approval on 2023-10-02. Its earlier initial-approval page
  is retained in the same amendment's `publicaciones`, with its own dates,
  description and documents.
- Amendment 23 has three publications; amendment 29 has two. They become one
  instrument per amendment number, with every publication URL retained.

Identity uses the source's explicit amendment number, scoped to Begues PGO. This
number is **not** presented as an administrative expediente number. Document links
are collected from the detail's Documents section and content links, with their
source publication URLs. No PDF is represented as a separate project. Attachment
contents are not parsed or independently verified, and links may later expire.

Each publication's numeric inventory date is `fecha_publicacion`. Only an explicit
approval sentence naming Ple/Junta/decret/acord can provide `fecha_acuerdo`.
Page-update timestamps and crawl dates are excluded. Ambiguous or missing agreement
dates remain null. `fecha` and `fecha_aprob` remain null. `fase` describes the latest
municipal publication (by publication date), not certified current legal validity.
Earlier publication dates, stages and descriptions remain in `publicaciones`.

## Coverage and validation

Excluded from this intentionally narrow extractor: unnumbered/special plans,
reparcel·lacions, public works, regional plans and all licence material. A missing
numbered instrument on this municipal website is not proof it does not exist.
The update operation refreshes the same complete inventory snapshot and does not
claim incremental/legal change tracking.

No verified project coordinates or vector geometry are exposed by this extraction.
`lat`, `lon`, `geometry` are null and `publication_ready` is false. No municipal
centroid or fabricated point is substituted.

Six offline tests pass with:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_begues -v
```

Tests cover selection/exclusions, distinct publication/agreement dates, Catalan
month names, absent/ambiguous dates, grouping and document provenance, source
markup/instrument mismatch, pagination traversal/failures, preservation of prior
output on failure, and manifest identity/safety flags.

A real `load_portal_adapter(load_manifest('begues')).backfill_proyectos(...)` run
wrote 10 records. Local, uncommitted evidence in `evidence/` includes
`proyectos.jsonl`, `validation.json`, 24 adapter HTTP captures under `captures/`,
and exploratory source captures. Validation lists all 24 fetched source URLs,
counts and limitations.

The shared entity policy classifies these 10 records as `pendiente` and reports
`adapter_incident / unknown_entity_spike`: its current rules do not establish
activity identity from a municipal PGO amendment number without an administrative
expediente reference. This limitation is retained in validation, not bypassed by
inventing expediente identifiers or changing shared policy. These are genuine
extractable planning instruments, but downstream activity/publication eligibility
remains unresolved, in addition to missing geometry. Independent review is required.
