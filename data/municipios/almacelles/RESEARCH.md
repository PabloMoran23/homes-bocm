# Almacelles — INE 25019, Lleida, Catalunya

Verified live 2026-11-09. Deliberately partial municipal scraper: the complete
latest reviewed annual works folder (2024), three genuine technical projects.
Not a municipal licence register; not evidence of approval, award or execution.
Scheduling and coordinate jitter are disabled; publication_ready is false.

## Official inventory discovery

- https://www.almacelles.cat/ajuntament — municipal navigation identifies both
  “Projectes/convenis municipals” and “Projectes/convenis en exposició pública”.
- https://www.almacelles.cat/ajuntament/projectes-municipals — live HTTP 200,
  annual project folders 2014–2022, projectes-2023 and projectes-2024, plus
  unrelated convenis folders 2021 and 2026. These are separate categories:
  convenis-2026 is not a newer works inventory.
- https://www.almacelles.cat/ajuntament/projectes-municipals/projectes-2024 —
  live HTTP 200, three entries: phase II municipal pool refurbishment, earth-road
  maintenance and asphalt-road patching, and municipal sports-hall floor
  replacement. All three extracted, without sampling or pagination truncation.
- https://www.almacelles.cat/ajuntament/projectes-en-exposicio-publica — live
  HTTP 200, mixed inventory of market rules, staffing, a poultry-farm construction
  proposal, music-school rules and public-security measures. Outside this adapter's
  stated annual-works scope. A construction proposal is not a granted licence.
- https://seu-e.cat/ca/web/almacelles/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme
  — discovered official transparency navigation for planning; not used to assert
  planning records or complete municipal coverage.

## Document provenance

Each 2024 municipal entry is a Plone Link that redirects to a public Google Drive
PDF viewer. Live viewers return HTTP 200 and expose PDF names in og:title:

- Pool: https://drive.google.com/file/d/1oX53GGPaCMJdUlAZkEuBDqwkzyfgKoLy/view?usp=sharing
  — PROJECTE FASE II PISCINES DEFINITIU_SIGNAT.pdf.
- Roads: https://drive.google.com/file/d/1zEjCmxapOwG9SxFGJFInOVGduUAN7-EI/view?usp=sharing
  — 20240603_PROJECTE COMPLERT_MANTENIMENT DE CAMINS_2024_SIGNAT-7.pdf.
- Sports hall: https://drive.google.com/file/d/1KhS21UaV1dPPPsKFeh_f9OEp9FC9MkEv/view?usp=sharing
  — 20240611_00_MEMÒRIA PAVIMENT PAVELLÓ COMPLERTA_signada.pdf.

The municipality establishes provenance of those external viewers. The adapter
retains each municipal URL, archive URL, destination and document title. PDF bodies
have not been parsed or verified. Filename words “DEFINITIU” and dates do not prove
an administrative approval. No publication/agreement/approval dates are asserted;
archive year is a separate field. No invented expediente numbers or coordinates.
Records explicitly identify source_entity_type=documento, so shared entity policy
does not promote these technical documents to evidenced administrative activity.

## Extraction contract and validation

The scraper first discovers the annual archive from the actual inventory. It fails
if the latest project year differs from 2024, markup disappears, the reviewed
physical-works title pattern changes, or a viewer loses PDF metadata. It follows
next-page links to exhaustion and rejects cycles/unreviewed pagination targets.
No page-count cap silently drops results. Redirects are limited to the official
municipal host and reviewed public Drive viewer paths; no authentication is used.
Responses have timeout and size bounds that fail explicitly. Stable IDs derive
from document viewer paths, with repeated municipal links grouped into one record.
Update refreshes the complete scoped snapshot atomically.

Runtime: /home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python.
`-m unittest municipio.test_almacelles -v`: 5 tests passed, covering navigation
exclusion, pagination and duplicate grouping, null date semantics, closed viewers,
new-year review and manifest constraints. Live extraction through the manifest and
shared registry: 3 records. Local uncommitted evidence/proyectos.jsonl,
evidence/validation.json and HTML captures retain the actual result, source URLs,
limitations and retrieval time. No dependencies or shared source files changed.
