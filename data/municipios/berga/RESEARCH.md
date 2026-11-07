# Berga — Barcelona — INE 08022

Verified live on 2026-11-07. Implemented one municipal adapter with deliberately
partial coverage: the official base POUM document archive. One genuine planning
instrument contains 103 distinct document links. This is not a complete current
consolidated planning register, a public-works inventory or a granted-licence
register. `publication_ready` is false because verified geometry is unavailable.
Scheduling, coordinate jitter and licence extraction are disabled.

## Official sources discovered

- https://ajberga.cat/ajuntament/govern/regidories/urbanisme — HTTP 200.
  The municipal urban-planning service identifies current planning and links
  both its POUM archive and the Generalitat RPUC search filtered to `08022`.
  It also describes the rural-building catalogue in preparation. Its explanatory
  text and presentation links are not treated as approval records.
- https://ajberga.cat/temes/380-urbanisme — HTTP 200. Topic inventory includes
  POUM and mobility-plan links, consultation news and RPUC navigation.
  News, consultations and navigation are discovery material, not emitted records.
- https://ajberga.cat/pla-dordenacio-urbanistica-municipal-de-berga-poum —
  HTTP 200. Dedicated municipal plan page links the archive below. The adapter
  rechecks this provenance link on each extraction. The page's last-update date
  (2023-02-13) is not an approval or project-publication date.
- https://ajberga.cat/media/import/poum/poum/index.htm — HTTP 200, legacy
  ISO-8859-1 HTML. Actual document inventory: approval-publication notice,
  memories, PMU/PAU/SUD sheets, norms and annexes, heritage catalogue, economic
  agenda, and A4/A3 plans. All 103 unique PDF links are retained in `documentos`,
  with their source anchor labels, table-row context and inventory URL. The map
  links often have only a file-size label, so row context and the original URL
  are preserved rather than inventing a document title.
- https://ajberga.cat/media/import/poum/poum/altres/dogc_4341-comp.pdf —
  HTTP 200, captured as supporting evidence. DOGC 4341 was published 2005-03-11.
  Its first page distinguishes the September 2004 definitive-approval agreement
  and December 2004 conformity to the revised text. The adapter does not parse
  PDF content, so it leaves agreement and approval dates null. It extracts only
  the explicitly labelled DOGC publication date from the HTML index. It does not
  confuse the date with an agreement, the edict date, or the website update.
- https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=08022
  — HTTP 200 after redirect to
  `https://planejamenturbanisme.territori.gencat.cat/rpucportal/index.html#/consulta/cercaPublic?reqCode=cerca&municipiSel=08022`.
  The captured response is a JavaScript application shell, not an extracted
  dossier inventory. Later amendments are outside this adapter's coverage.

## Extraction and limits

The adapter implements the `AyuntamientoAdapter` contract and is loaded through
the existing manifest registry, without changes to shared code or dependencies.
Identity derives from the canonical archive URL. All archive documents are
components of a single POUM, including sector sheets and annexed planning;
they are not emitted as separate approved projects or licences.

Each run requests the official plan landing page and then the complete archive.
Requests have a 30-second timeout and a streamed 2 MB limit; an oversized response,
HTTP error, redirect, missing heading/sections or changed provenance aborts before
writing records. This is an unpaginated single-plan archive. There is no page or
record cap. Unexpected continuation, form, frame, external link or non-PDF archive
link raises an error rather than silently reducing coverage. Updates refresh the
whole snapshot; no date cursor is used. Duplicate document URLs are deduplicated.

Retrieval timestamps and SHA-256 digests are recorded separately from project
dates. With `config.evidence_dir`, raw responses are also captured. Individual
PDF availability/content is not checked by the adapter: these are documented
source links, not a claim that all attachments were downloaded or interpreted.
Only the DOGC PDF was separately downloaded during research. PDF maps are not
converted into geometry; no centroid, geocoded guess or random coordinates are
substituted. `lat`, `lon` and `geometry` remain null.

## Validation

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Parser and integration tests:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_berga -v
```

Ten tests passed, covering document grouping and context, publication versus
agreement dates, missing dates, legacy multiline whitespace, stable identity,
duplicates, incomplete inventories, conflicting notices, invalid dates,
pagination/external-link rejection, exclusion of forms/news/navigation, full
snapshot updates, changed landing pages and manifest/disabled-licence behavior.

Real network extraction was run through `load_manifest('berga')` and
`load_portal_adapter(manifest).backfill_proyectos(Path('evidence/proyectos.jsonl'))`,
with `evidence_dir` configured to the local evidence directory. Result: status
`ok`, **1 live record, 103 document links**. An independent inventory comparison
confirmed that every unique link on the captured archive is in the output.
Municipality identity and null coordinates/geometry were also checked.

Local evidence, excluded from version control:

- `evidence/proyectos.jsonl`: actual live record, with document links and source
  hashes/timestamps; shared entity policy reports category unknown, retained
  without fabricating a category or geometry.
- `evidence/validation.json`: live count, source URLs, test command/results,
  pagination accounting, date semantics and coverage limitations.
- `evidence/poum-landing-live.html`, `evidence/poum-index-live.html`: exact
  adapter response captures.
- `evidence/urbanisme.html`, `evidence/temes.html`, `evidence/poum-page.html`,
  `evidence/poum-index.html`, `evidence/rpuc.html`,
  `evidence/dogc_4341-comp.pdf`: discovery/supporting captures.

No credentials, other workspaces, databases, publishing or deployment operations
were used. Independent acceptance remains pending.
