# Redován — Alicante — INE 03111

Verified live on 2026-11-08 using the preinstalled batch virtual environment.
This adapter extracts a **partial snapshot of the municipal planning inventory**:
nine genuine planning/management instruments, with 141 linked documents grouped
under their corresponding instrument. It does not claim an exhaustive inventory
of recent works, amendments, or granted licences. Scheduling and coordinate
jitter are disabled; every record has `publication_ready: false`.

## Official source discovery

- Municipal urbanism index (HTTP 200):
  https://www.redovan.es/ayuntamiento/estructura-municipal/concejalias-2/urbanismo/
  describes the planning inventory as PGOU and current planning and links to it.
- Planning inventory (HTTP 200), used by the adapter:
  https://www.redovan.es/ayuntamiento/estructura-municipal/concejalias-2/urbanismo/planeamiento-municipal-vigente/
  is a complete server-rendered page of collapsible sections, including all the
  document links without opening the sections in a browser. No pagination was
  exposed. The adapter rejects detected pagination rather than silently taking
  the first page. The Catalan translation is not a second inventory to ingest.
- Administrative forms (HTTP 200):
  https://www.redovan.es/ayuntamiento/tramites/
  explicitly provides applications for submission to the register, including
  building, segregation and occupation licence forms. These are not granted
  licences. It links to https://redovan.sedelectronica.es/info.5 for submission;
  that destination was not used as a project source or verified as a public
  granted-licence register. `licencias.enabled` remains false.

## Extracted instruments and date semantics

Dates below are the **approval and gazette publication dates asserted by the
municipal inventory**, respectively. No approval is inferred from a page update,
upload directory, news date or crawl time. Gazette originals have not been
independently reconciled. The source does not consistently specify the legal
approval stage, so `fase` says only “aprobado según inventario municipal”.
`fecha_acuerdo` and `fecha_aprob` carry the explicitly stated approval date;
generic `fecha` is null.

| Instrument | Approval | Gazette publication | Documents |
| --- | --- | --- | ---: |
| PGOU | 2007-05-11 | 2008-02-13 | 93 |
| PGOU modificación puntual 1 | 2011-07-22 | 2011-08-09 | 1 |
| PGOU modificación puntual 2 | 2011-11-28 | 2011-12-21 | 1 |
| B-4 homologación modificativa y pormenorizada | 1998-06-08 | 1999-06-29 | 5 |
| B-4 proyecto de reparcelación | 1999-02-02 | 1999-06-07 | 3 |
| B-7 plan parcial Polígono Industrial San Carlos | 1996-10-08 | 1998-03-09 | 4 |
| B-7 proyecto de urbanización | 2004-03-01 | 2004-04-13 | 20 |
| B-7 proyecto de reparcelación | 2004-03-01 | 2004-04-13 | 7 |
| B-7 proyecto modificado nº1 de urbanización | 2008-01-28 | 2008-05-28 | 7 |

The inventory has five top-level collapsible sections, but B-4 and B-7 include
additional instruments with separate approval paragraphs. These are segmented
before assigning their following document links. Plans, annexes, budgets,
notices and maps belonging to one instrument are not emitted as separate
projects. The modified urbanisation project is a separately named revision
under the same B-7 sector. Identity derives deterministically from source URL,
instrument title and sector, not document count or extraction time. Source
headings and approval narrative are retained, and each document records the
inventory URL as provenance. Case-sensitive URLs are preserved: `MEMORIA.pdf`
and `Memoria.pdf` are different links belonging to different instruments.

## Availability and limitations

A live sample of 11 document URLs returned nine genuine PDF responses (HTTP 200
and `%PDF` signature), including at least one document for each of the nine
instruments. Two published links returned HTTP 404:

- Original B-7 urbanisation: https://www.redovan.es/wp-content/uploads/2011/12/MEMORIA.pdf
- Modified B-7 urbanisation: https://www.redovan.es/uploads/2011/12/Memoria-2-de-3.pdf

These links remain exactly as published; no guessed replacement is introduced.
The original urbanisation's `A05.-PLAN-DE-OBRA.pdf` was additionally checked and
is available. The full set of 141 links was not downloaded or availability
checked; document contents and parcel geometry were not parsed. The municipality
provides PDF plans, but no verified coordinates or vector geometry have been
extracted. `lat`, `lon` and `geometry` remain null; no municipal centroid or
synthetic location is substituted. The inventory's currency is the municipality's
presentation, not a legal certification that no later amendment exists. This
adapter does not crawl procurement announcements or the general news feed.

## Implementation and validation

The adapter implements the shared `AyuntamientoAdapter` contract and is loaded
through the manifest's `module:Class` specification without shared source edits.
Backfill and update both refresh the complete page. HTTP failures, oversize
responses (4 MB maximum), missing content/documents/dates, unrecognised sections,
duplicate instruments, unsegmented approval paragraphs and pagination raise
errors before replacing output. Requests use a 40-second timeout. A successful
snapshot is written through a temporary file. Licences produce a disabled,
empty result. No state watermark can hide edits to older instruments.

Run from the repository root:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_redovan -v
```

Nine offline tests passed: instrument boundaries (including reparcelación and
modified urbanisation), date semantics, two-digit year in modification 1,
link grouping/case/deduplication, stable identity, missing/invalid source rejection,
pagination rejection, manifest loading, disabled licences and snapshot update.
Live extraction used `load_manifest`, `load_portal_adapter` and
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, with `capture_dir` set to
`evidence`. It returned status `ok`, nine records and 141 document links.
The shared entity policy reports nine `unknown` classifications, status `ok`;
no physical use category is inferred from planning titles.

Local, uncommitted evidence:

- `evidence/proyectos.jsonl`: actual live records through the manifest-loaded adapter.
- `evidence/validation.json`: live count, source URLs, timestamp, runtime,
  source SHA-256, document sample checks and coverage limitations.
- `evidence/planeamiento.html`, `evidence/urbanismo.html`,
  `evidence/tramites.html`: source captures.

Only the four requested source files are added. No installation, credentials,
production, deployment, database, publishing or git mutation is required.
