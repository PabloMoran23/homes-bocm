# Sant Vicenç de Montalt — INE 08264, Barcelona

Verified live on 2026-11-09 using the preinstalled batch virtualenv Python.
This adapter deliberately covers one real planning instrument: the new POUM at
initial approval. It does not claim complete municipal planning or works coverage.

## Official source discovery

- https://www.svmontalt.cat/urbanisme — municipal urban-planning inventory.
  It distinguishes the existing subsidiary rules (1986), the consolidated rules
  (2005), later modifications and the new POUM. It links to the POUM landing page,
  the existing-rules document inventory and the official RPUC for other planning.
  Highlighted news, service contacts and application forms are not records.
- https://www.svmontalt.cat/pagina.php?id=22105 — existing-rules inventory,
  reviewed separately: consolidated 2005 rules and four ordinance maps. The page
  explicitly says the consolidated document omits subsequent amendments. This
  instrument is outside the implemented snapshot, not represented as the new POUM.
- https://www.svmontalt.cat/ambit.php?id=71 — implemented new-POUM landing page.
  Its substantive presentation states that the extraordinary municipal plenary
  initially approved the POUM with its strategic environmental study on
  **2026-06-29**. It also says that the existing 1986 rules remain applicable until
  definitive approval. No definitive approval is inferred from the elapsed public
  consultation period or from the existence of downloadable documents.
- https://www.svmontalt.cat/pagina.php?id=24146 — linked initial-approval technical
  document inventory: **13 PDF links**, all retained. These include the report,
  rules, development-area sheets, information and ordinance maps, social report,
  environmental study, mobility study, economic assessment, rural-building and
  heritage catalogues, processing report and summary document.
- https://www.svmontalt.cat/pagina.php?id=24145 — linked announcement inventory:
  **5 distinct PDF links**, retained with their index provenance. The introductory
  summary gives separate publication dates: electronic headquarters and BOPB
  **2026-07-16**, El Punt Avui **2026-07-24**, DOGC **2026-07-28** and La Vanguardia
  **2026-07-29**. These are publication dates, not five approvals or five projects.

All five municipal HTML pages above returned HTTP 200 during discovery. Local
captures are under `evidence/`. The adapter fetches the POUM page and follows its
two explicitly labelled current indexes rather than treating the highlighted news
list as an exhaustive inventory. Earlier advance-phase links are not additional
records; advance-phase attachments and the RPUC inventory are outside coverage.

## Implementation and semantics

One stable record uses the municipal POUM landing-page identity (`ambit=71`).
Technical documents and announcements belong to this same instrument; all 18
unique URLs are retained with title, document kind and originating index URL.
PDF contents are not parsed, and the links do not assert individual parcel or
project geometry. `descripcion` retains the source approval narrative.

`fecha_acuerdo` and `fecha_aprob` mean the explicitly stated initial approval,
2026-06-29; `fase` identifies that stage. `fecha_publicacion` means BOPB publication
2026-07-16, with its medium specified. Other explicit publication dates remain in
`publicaciones`. Generic `fecha` is null. No page-refresh timestamp, consultation
end date, filename year or crawl time is used as an approval date.

No pagination was present in these three implemented dossier pages. The adapter
reads every PDF anchor within each document body and deduplicates repeated preview
and filename anchors. Recognized next-page controls trigger an error; there is no
record-count slice or silent page limit. Missing dossier indexes, approval text,
publication dates, PDF lists or changed external document provenance fail closed.
Requests have a 30-second timeout and a 3 MB HTML bound. The portal's declared
ISO-8859-1 encoding is respected. Updates refresh the complete scoped snapshot;
this is not a historical event archive.

No verified vector geometry or project coordinates were found in the implemented
HTML sources. `lat`, `lon` and `geometry` are null, `publication_ready` is false,
`geocode.jitter_missing` is false, and scheduling is disabled. The map PDFs are
linked without inventing a centroid. Licence application forms and licence
suspension language do not establish granted licences; `licencias.enabled` is
false. Existing planning, amendments, other physical works and granted licences
remain outside this adapter's coverage.

## Validation

- `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_sant_vicenc_de_montalt`
  — **7 tests passed**: grouped documents and date semantics, exclusion of
  navigation/news-only content, absent publication dates, invalid dates, missing
  documents and changed provenance, pagination rejection, snapshot update and
  disabled licences.
- Live extraction through `load_manifest` and `load_portal_adapter`, invoking
  `backfill_proyectos`: **1 actual record**, **18 document links**, status `ok`.
  Registry entity annotation completed; its category remains `unknown` and is
  not substituted for the explicitly sourced POUM type or phase.
- `evidence/proyectos.jsonl` contains the live record;
  `evidence/validation.json` contains the live count, retrieval time, source URLs,
  captures, limitations and registry result. Evidence remains local, outside the
  four source deliverables.
