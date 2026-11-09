# Collbató — INE 08069, Barcelona

Verified live 2026-11-09 with the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
This adapter extracts a partial municipal snapshot, not a comprehensive dossier
register. Schedule, licences and missing-coordinate jitter are disabled.

## Official current source discovery

Municipal Urbanisme navigation was inspected at
https://www.collbato.cat/ajuntament-seu-electronica/urbanisme/ordenanca-reguladora-terrasses-de-bar-i-mobiliari.htm
(local capture: `evidence/discovery.html`). It links the PGOU, RPUC, Avanç POUM
2025, projects, Bosc del Misser, the sports-zone modification and other sections.

Implemented inventories, both fetched live with HTTP 200:

- https://www.collbato.cat/ajuntament-seu-electronica/urbanisme/projectes.htm
  contains eleven list entries representing eight named physical works. These
  include pool electrical installation, Casinet ventilation, sports-court enclosure,
  Casinet access/toilets, sports-centre bar/terrace, town-hall ground-floor premises,
  water-supply pipe duplication, and Can Dalmases drinking-water tank rehabilitation.
  Four entries for the sports-court enclosure (original notice, correction, initial
  and definitive approval labels) are grouped into one work, retaining every link
  and original label. Seven e-Tauler references and three PDFs remain linked.
  The tank work is explicitly named but has no attached link: it is included on
  the authority of the inventory text, with empty document/reference lists.
- https://www.collbato.cat/ajuntament-seu-electronica/urbanisme/pla-general-ordenacio-urbana.htm
  contains the PGOU consolidated text, normative chapters and plans. All 37
  documents are grouped in one planning instrument, not 37 projects. This is the
  posted consolidated PGOU document set, not a claim to incorporate all subsequent
  modifications or to represent a newly approved POUM.

Additional official inventories inspected but outside implemented coverage:

- https://www.collbato.cat/ajuntament-seu-electronica/urbanisme/avanc-poum-2025.htm
  describes the Avanç and links to the transparency portal document collection.
  It is distinct from the PGOU and is not merged into that instrument.
- https://www.collbato.cat/ajuntament-seu-electronica/urbanisme/projecte-d-urbanitzacio-del-bosc-del-misser.htm
  links an urbanisation project PDF.
- https://www.collbato.cat/ajuntament-seu-electronica/urbanisme/modificacio-puntual-del-pla-general-d-ordenacio-de-la-zona-esportiva-de-collbato.htm
  links a notice, initial planning document and licence-suspension area PDF.
- https://www.seu-e.cat/ca/web/collbato/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  points to RPUC/MUC; the regional dossier inventory is not crawled.
- https://www.collbato.cat/ajuntament-seu-electronica/atencio-al-ciutada/tramits-i-gestions.htm
  offers licence application procedures. These are not granted licences and are
  excluded. No public granted-licence register was verified.

## Provenance and semantics

Every record includes the municipal source URL. Document/reference objects retain
source URL, original title and resolved URL. Original HTTP document links remain
as published; relative links resolve against the municipal page. The sports-court
work uses a stable subject identity across its notice variants; PGOU uses one
instrument identity. Other work identities use normalized source subject text.
No generated records represent licence forms, procurement announcements or news.

All date fields are null. Dates embedded in PDF filenames, retrieval timestamps
and unverified document text are not substituted for publication/agreement dates.
Original approval labels are preserved in description/provenance, while `fase`
is null because the present legal phase and notice chronology were not verified.
There is no coordinate inference, municipal centroid or jitter: coordinates and
geometry are null, and `publication_ready` is false.

The seven e-Tauler URLs are references from the municipal inventory, not verified
notice-body extractions. A sample request to
https://tauler.seu.cat/pagDetall.do?idEdicte=352667&idens=806920002 returned a small
HTTP 200 shell (1,656 bytes), saved as `evidence/tauler.html`. Historic notices may
expire. Municipal PDFs for the bar and sports court were separately requested
over HTTPS and returned HTTP 200 application/pdf (140,489 and 163,028 bytes),
saved as `evidence/bar.pdf` and `evidence/pista.pdf`. Not every linked document
was downloaded or checked; links do not assert ongoing document availability.

## Extraction and validation

Both unpaginated source inventories are completely scanned on each backfill or
update; no date cutoff or row limit silently truncates them. Pagination controls
raise an error so a changed inventory cannot silently lose further pages.
Missing headings, empty inventories, unexpected document hosts, redirects,
non-project list entries and oversized responses fail closed. Downloads have
35-second timeouts and a 3 MB decompressed response limit. Output is replaced
only after both source parses succeed. `capture_dir` optionally saves the exact
source bytes during extraction.

- `python -m unittest municipio.test_collbato -v`: five tests passed, covering
  work grouping with retained notices, document grouping, null semantics,
  changed/missing sources, form/procurement rejection, pagination, and disabled
  licences/manifest loading.
- Direct live `CollbatoAyuntamientoAdapter.backfill_proyectos`: nine records
  (eight works plus one PGOU), 40 PDF links and seven notice references.
- Local evidence: `evidence/proyectos.jsonl`, `evidence/validation.json`, exact
  extraction HTML (`projectes.htm`, `pla-general-ordenacio-urbana.htm`), discovery
  HTML and sampled PDFs. Evidence is local and is not source to commit.

No dependencies, shared sources, credentials, databases, deployment services or
publication operations were used or changed.
