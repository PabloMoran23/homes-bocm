# Premià de Dalt — INE 08230, Barcelona

Verified live on 2026-11-07 with the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
The adapter extracts a partial municipal planning/project inventory: **36 actual
instruments or physical projects, retaining 153 document links**. This is a code
candidate for independent review, not approval to publish. `publication_ready`
is false because no verified project geometry was extracted.

## Official source discovery

- [Municipal planning service](https://www.premiadedalt.cat/per-temes/territori/urbanisme/planificacio-urbanistica)
  responds HTTP 200 and explicitly links its “PLANIFICACIÓ VIGENT” to the
  municipal inventory below. It also links the regional RPUC search using
  `municipiSel=08230`, independently corroborating municipality identity.
- [Municipal planning inventory](https://www.premiadedalt.cat/ajuntament/normativa/planificacio-urbanistica)
  responds HTTP 200. Its complete HTML accordion embeds document links and nested
  folders. It includes the POUM, amendments, special plans, partial plans and
  physical projects: Ronda Pirineu/Pompeu Fabra urbanisation (heading May 2026),
  Santa Anna-Tió POUM amendment (heading September 2026), Pedra Blanca detention
  basin, water-network renewal, Mas de la Cisa roof reform, Espai Respir reform,
  Torrent Castells drainage and others. These are named technical-document
  dossiers, not generic service descriptions, tender notices or unrelated news.
- [Other planning](https://www.premiadedalt.cat/ajuntament/normativa/planificacio-urbanistica/altres-planejaments-1)
  responds HTTP 200 but only points to the regional RPUC search. No regional
  register completeness is claimed; its pointer is not emitted as an instrument.
- [Licences service](https://www.premiadedalt.cat/per-temes/territori/urbanisme/llicencies)
  responds HTTP 200 with explanatory text and a procedures link. This is not a
  verified register of granted licences. `licencias.enabled=false`.

The service, other-planning and licences discovery pages were captured locally.
One representative inventory-linked agreement PDF concerning the hostelry-use
POUM amendment was independently retrieved (HTTP 200, PDF signature, 114041
bytes); its exact URL and SHA256 are in `evidence/validation.json`, with the file
at `evidence/sample-agreement.pdf`. This verifies a real linked document, not
availability or contents of all 153 links. The adapter parses HTML metadata and
retains PDFs; it does not extract PDF text, personal data or geometry.

## Deliberate partial coverage

All top-level accordion entries are examined. The POUM-amendments and
heritage-amendments containers are split into their separately named instruments.
A plan's nested approval folder remains part of the same record. The repeated
Can Verboom heritage amendment appears at two inventory locations with different
PDF URLs: it becomes one instrument, retaining both links and inventory references.
All document labels and source anchors are preserved in `documentos` and
`referencias_inventario`. Documents are never emitted as separate projects.

Six reviewed folders are explicitly excluded, with reasons returned by every
extraction and recorded in the validation report:

- Can Nolla: mixes partial plan, urbanisation, reparcelling and agreements.
- Cal Rei: mixes urbanisation and reparcelling.
- Can Costa: mixes POUM amendment, urbanisation and reparcelling stages.
- Can Botey: mixes technical documentation and heritage amendment. Its separately
  indexed heritage amendment is included through the heritage container.
- Pistes de vòlei, carrer Montseny: mixes urbanisation and provisional land use.
- Habitatges d'Ús Turístic: not verified as a distinct instrument for this adapter.

The seventh exclusion is the “Altres planejaments” register pointer. These are
scope exclusions, not pagination truncation. The live inventory has no pagination
controls; the adapter rejects pagination markup, next links and known pagination
query parameters rather than silently ingesting a first page. It also rejects
missing accordion markup, unreviewed groups, unexpected links, empty instruments,
redirects and oversized responses. No successful empty placeholder is produced.

## Date semantics, identity and refresh

Dates in headings, folder slugs and PDF filenames may denote publication,
document drafting, amendment or agreement dates. Some even conflict (the La Suïssa
heading says 2011 while linked agreement/publication labels mention 2012). None
are promoted into a legal event date. `fecha`, `fecha_publicacion`, `fecha_acuerdo`
and `fecha_aprob` remain null, as does `fase`. The exact heading is preserved in
`titulo` and `fecha_texto_fuente`; original document labels retain their dates and
approval wording. No crawl date becomes a project date.

IDs hash the actual source inventory anchor; document order changes do not change
identity. Exact repeated document sets or repeated normalized instrument titles
are merged, retaining document links. A source reorganisation or renamed anchor
could change IDs; this is a current snapshot rather than a legal history ledger.
Update refreshes the entire reviewed snapshot, without a date cursor, and writes
atomically only after successful parsing. No invented dossier identifiers,
approval dates, coordinates, centroids or jitter are used. `lat`, `lon` and
`geometry` are null; `schedule.enabled=false`, `geocode.jitter_missing=false`.

## Validation

- `python -m unittest municipio.test_premia_de_dalt -v`: **9 tests passed**.
  Tests cover grouped/nested documents, separate instruments inside containers,
  duplicate inventory references and relocated documents, stable identity,
  untyped dates, explicit exclusions, licence disabling, source/form rejection,
  pagination rejection and preservation of previous output on parse failure.
- Live `PremiaDeDaltAyuntamientoAdapter.backfill_proyectos`, loaded with the
  manifest configuration and a local capture directory: **36 records, 153 links**.
- `evidence/proyectos.jsonl`: actual live records, unique IDs, INE 08230.
- `evidence/validation.json`: live count, source URLs, runtime, limitations,
  exclusion reasons, sample PDF provenance and inventory SHA256.
- `evidence/planning-index.html`: exact HTML fetched by the live adapter.

Evidence is local and is not part of the four source files. No dependencies,
shared source, credentials, databases, deployment tools or git metadata were
modified; no publishing or pipeline-wide ingestion was performed.
