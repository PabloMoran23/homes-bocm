# La Seu d'Urgell — INE 25203, Lleida

Verified live on 2026-11-07 using the preinstalled batch virtualenv. This adapter
extracts genuine municipal planning instruments, not licence applications,
procurement announcements or news. Coverage is a snapshot of the municipal
planning website, **not** an assertion that every historical document remains
legally effective. No granted-licence inventory was verified. Scheduling,
licence extraction and coordinate jitter are disabled.

## Official inventory and traversal

Discovery entry point:
https://www.laseu.cat/tramits-i-serveis/ordenances-i-normatives/urbanisme

The municipal index links these three implemented sources:

- [Planejament general](https://www.laseu.cat/tramits-i-serveis/ordenances-i-normatives/urbanisme/planejament-general):
  PGOU consolidated text 2002 and 33 separately published modifications. Missing
  sequence numbers are not filled in. The consolidated text retains its updated
  norms, annex and maps as one record.
- [Planejament derivat](https://www.laseu.cat/tramits-i-serveis/ordenances-i-normatives/urbanisme/planejament-derivat):
  partial plans, urban improvement plans, special plans, and the PAU/UA folder.
  The latter explicitly reports no items. The Centre Històric PMU has further
  nested folders for its consolidated text and modification; both are traversed.
- [PMUS](https://www.laseu.cat/tramits-i-serveis/ordenances-i-normatives/urbanisme/pla-de-mobilitat-urbana-sostenible-de-la-seu-durgell):
  one mobility planning instrument, including analysis, maps, action proposals,
  environmental documents and monitoring indicators. Its explicit narrative
  states definitive approval on 2012-06-11 and BOP publication on 2012-06-21.

The air-conditioner placement criteria link is outside these source inventories
and is excluded. The adapter does not scrape navigation, procurement or news.
No claim is made about complete public-works, RPUC or municipal licence coverage.

The live traversal fetched 55 pages and produced **45 records with 371 document
links and 8 RPUC references**. All listed child folders are followed, not just the
first level or the newest records. The current inventory exposed no pagination;
the crawler follows forward pagination when present. Cycles, unsupported entries,
missing document bodies, HTTP failures, oversize responses and the 200-page
safety bound cause an error before replacing output, not a partial success.
Updates refresh the same complete scoped snapshot; the state file is unused.

## Identity, grouping and provenance

Each municipal detail URL identifies one instrument bundle, with a stable hash
ID. Its documents are grouped in `documentos` with visible labels, original
resolved links and the municipal `source_url`. Exact duplicate links on the same
page are removed. A page can include the parent instrument and embedded historic
versions/amendments: these remain together, preserving the entire body text in
`descripcion`. Separately published municipal modification pages remain separate
records. No document, archive, map or DOGC link becomes an extra project.

RPUC links remain in `referencias`, including old AppJava URLs. The municipal
pages for PGOU modification 035 (Museu Diocesà, URL ending `/ffff`) and 037
(Estació d'Autobusos) both link RPUC identifier 291476. This is a source
inconsistency: the records are not merged on that identifier and it is not
presented as a verified municipal expediente number. Their municipal DOGC PDFs
were both downloaded successfully and have different SHA-256 hashes.

Page timestamps such as 2010-11-09 are **not** interpreted as instrument approval
or bulletin publication. Only explicit complete dates in visible agreement or
publication link labels are assigned to those individual documents (6 agreement
and 21 publication dates in the live result). Multiple, missing, malformed or
invalid dates stay null. Dates are never extracted from filenames. The PMUS
narrative is the only source here used for record-level approval/publication;
other record-level dates and phases remain null. No generic date or instrument
type is repurposed as a phase. No coordinates or vector geometry were verified;
all records have null `lat`, `lon`, `geometry` and `publication_ready: false`.

## Validation and limits

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_la_seu_d_urgell`: 7 tests passed. These exercise
  document grouping, date scope and distinction, rejection of unusable sources,
  forward pagination, ambiguous/invalid dates, atomic failure and manifest loading.
- A real extraction through `load_portal_adapter(load_manifest('la-seu-d-urgell'))`
  wrote `evidence/proyectos.jsonl` (45 records) and `evidence/validation.json`.
  Validation records every fetched source URL, capture hash, limitations and
  extraction timestamp. `evidence/captures/` contains all 55 live HTML responses.
- `evidence/document_checks.json` records HTTP 200 and PDF signature checks for
  the PMUS monitoring indicators and the DOGC PDFs for modifications 035 and 037;
  those three PDFs are saved locally. Remaining linked files are retained as
  provenance but were not individually downloaded or parsed. Document contents,
  vector geometry and legal validity are outside this extraction.
- The shared entity policy reports `adapter_incident / unknown_entity_spike`:
  all 45 records are `pendiente / insufficient_identity_evidence`. Its rules
  require an expediente reference or another supported identity category. The
  municipal detail URLs establish scraper identity but do not satisfy that
  policy. No municipal expediente numbers were fabricated to bypass this guard.
  These records require independent review and are not ready for publication.

Evidence is local and is not part of the four source files. No shared code,
dependencies, credentials, databases or deployment operations were used.
