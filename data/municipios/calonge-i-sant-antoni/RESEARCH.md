# Calonge i Sant Antoni — INE 17034, Girona

Verified live on 2026-11-07. This adapter extracts the municipal POUM inventory,
not a complete inventory of municipal development activity. One real instrument
is emitted, grouping 76 municipal document links. It is not a granted-licence
register. Scheduling, licences and missing-coordinate jitter are disabled.

## Official source discovery

- [Municipal planning transparency page](https://seu-e.cat/ca/web/calonge/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic)
  returns HTTP 200 and links directly to the municipal POUM section.
- [Municipal POUM page](https://www.calonge.cat/ajuntament/poum) returns HTTP 200
  with a React shell. Its public JavaScript bundle
  `/static/js/main.abae6d23.chunk.js` specifies `https://api.calonge.cat` as the
  backend and requests `/node/poum?include=catalogs_files,gc_files,gq_files,regulations_files`
  through the `/jsonapi/` base. This is the actual public data source used by
  the website; HTML navigation alone is not interpreted as a project.
- [Official POUM JSON:API inventory](https://api.calonge.cat/jsonapi/node/poum?include=catalogs_files,gc_files,gq_files,regulations_files)
  returns HTTP 200: one `poum` node, UUID
  `26fc4b7f-da0a-40c3-ba9c-8457f6bc3524`, and 76 included files.
  Relationships contain 6 catalogue/path documents, 9 classification map sheets,
  58 qualification map sheets and 3 regulatory documents. They belong to the
  same instrument and are not 76 projects.
- [Definitive approval agreement PDF](https://api.calonge.cat/sites/default/files/files/poumdef.pdf)
  is explicitly labelled `Acord d'aprovació definitiva` in the relationship.
  A separate live GET verified HTTP 200, PDF signature and 1,598,679 bytes.
  This capture is evidence of document availability, not automated date extraction.
- The node's related links identify the actual plan's public RPUC dossier
  `2009/39204/G`. This reference is parsed from `codiPublic` in the linked URL,
  rather than invented from the municipal UUID. The related amendment and
  litigation links are also retained, without emitting unverified extra records.

## Semantics and coverage

The inventory title and attached regulatory documents identify the real POUM.
Its generic description also mentions dates of legislation regulating planning;
those are not plan approval dates. All generic, publication, agreement and
approval dates remain null. The existence of an approval document does not
establish the instrument's current legal status, so `fase` remains null too.
The adapter does not claim that the original POUM is an up-to-date consolidated
version or that every later amendment is represented here.

Every attachment retains its source file UUID, filename, relationship label,
relationship section(s), MIME type, absolute municipal URL and inventory
provenance. Related RPUC URLs are preserved after HTML entity decoding. Maps
are PDF documents; no verified project geometry has been extracted. Latitude,
longitude and geometry remain null, and `publication_ready` is false. No
municipal centroid, random jitter, inferred parcel, or map-sheet coordinate is
substituted.

Coverage is deliberately partial: the dedicated POUM section, including its
catalogues, maps, regulatory attachments and related reference links. Other
planning modifications, public works, procurement, news and licence applications
are outside this adapter. The transparency landing page is a source locator,
not an inventory row. No verified public granted-licence register was established.

## Runtime and validation

Uses existing requests and BeautifulSoup dependencies; no shared source or
dependency changes. `backfill_proyectos` and `update_proyectos` both refresh the
complete inventory. Top-level JSON:API `next` links are followed until exhausted;
there was no `next` link in the live response. Cycles, foreign pagination URLs,
excessive responses/pages, incomplete attachment includes, conflicting nodes,
unexpected instruments and attachment-relationship pagination fail explicitly.
No existing output snapshot is replaced on extraction failure. Safety limits
are errors, not silent truncation. Licence methods return disabled and no rows.

Executed with `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`:

- `-m unittest municipio.test_calonge_i_sant_antoni -v`: 5 tests passed.
  Covers grouping/provenance, legislative-date isolation, rejection of forms and
  missing documents, multi-page traversal, update snapshot refresh, cycle/foreign
  URL failures preserving existing output, manifest resolution and disabled licences.
- Live extraction via `load_manifest` / `load_portal_adapter` and
  `backfill_proyectos`: 1 actual record, 76 document links; entity-policy check
  reports 0 unknown records.

Local, uncommitted evidence under `evidence/`: `proyectos.jsonl`,
`validation.json` (counts, source URLs, limitations, test result, PDF checksum),
`poum-page-1.json` (adapter's raw live response), `poum-discovery.json`,
`discovery-0.html` / `discovery-1.html` / `discovery-2.html` (source discovery),
`main.js` (public website bundle) and `poumdef.pdf`. Evidence is not source code
and must not be committed. No publish, deployment, database or credential access
is involved.
