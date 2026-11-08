# Caldes de Malavella — INE 17033, Girona

Verified live on 2026-11-08 with the preinstalled Python runtime. This adapter
extracts **one genuine planning instrument**, the original municipal POUM. It is
an intentionally partial snapshot of the plan linked under current planning,
not a consolidated version of all subsequent amendments, a comprehensive works
inventory, or a granted-licence register. Scheduling and coordinate jitter are
disabled. `publication_ready` is false because no verified geometry is extracted.

## Official source discovery

- Municipal Urbanisme inventory, HTTP 200:
  https://caldesdemalavella.cat/index.php/ca/viure-caldes-ca-es/viure-caldes-serveis-ca-es/serveis-de-poble/urbanisme
  The `Accés al planejament vigent` section links the POUM, a separate amendment,
  urban agreements, RPUC, the POUM normative PDF, consolidated urban fabric and
  acoustic map. Only the original POUM is in this adapter's scope. The acoustic
  map, administrative service descriptions and licence application links do not
  become projects. The selected list is a single, unpaginated HTML list; the
  parser rejects article pagination if it appears.
- Municipal works/instruments entry, HTTP 200:
  https://www.caldesdemalavella.cat/index.php/ca/2120-instruments-urbanistics-que-estan-en-tramit
  It links the current transparency inventory, RPUC search with `municipiSel=17033`,
  and SITMUN. This page contains navigation, not actual works records.
- Current transparency inventory, HTTP 200:
  https://caldesdemalavella.eadministracio.cat/transparency/675dede8-03e9-4f52-a1fb-eb453a31af0e/
  Public root labels show 61 entries under planning in progress, 61 under planning
  in force and 155 under public works/infrastructure. These are portal labels,
  not verified counts of distinct projects. Folder links use session-bound Wicket
  callbacks. One anonymous public-works callback, requested in the same session,
  returned HTTP 200 with whitespace only. Its response is captured locally. This
  observation does not establish that all browser access is blocked. No inventory
  completeness is claimed and these folders are not silently truncated into the
  one-record output. The licence section describes public information, not proof
  of granted licences; it is excluded.
- Municipal normative PDF, HTTP 200, `application/pdf`, 1,353,388 bytes:
  https://caldesdemalavella.cat/images/Normativa_POUM.pdf
  This is actual DOGC edict and normative content, not a form or a procurement
  notice. Its opening page names Caldes de Malavella and planning dossier
  `2010 / 042682 / G`, explicitly approves the POUM definitively and provides
  independently labelled dates. The file has 165 pages.
- RPUC source links retained exactly as published by the municipality:
  http://ptop.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=veureDocument&codintExp=254386&fromPage=load
  and the matching `reqCode=veure` link. Their `codintExp=254386` identifies the
  same original plan. The separate amendment (`270446`) and agreements (`254390`)
  are not merged into this plan.
  A checked HTTPS equivalent at
  https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=veureDocument&codintExp=254386&fromPage=load
  redirects to the current RPUC JavaScript application shell at
  https://planejamenturbanisme.territori.gencat.cat/rpucportal/index.html#/consulta/cercaPublic?reqCode=veureDocument&codintExp=254386&fromPage=load
  No RPUC dossier contents or geometry are claimed from that shell.

## Record semantics and extraction

The adapter fetches the live municipal article and the normative PDF it actually
links, with HTTP errors, response size bounds (2 MB HTML, 10 MB PDF), connection
and read timeouts. Existing system `pdftotext` extracts the PDF text; no dependency
or software installation was performed. Only the opening edict page is used for
record semantics, preventing unrelated dates in the annex from becoming plan
approval dates. The parser requires the exact municipality and plan title,
definitive-approval text, explicit agreement date, DOGC header publication date
and dossier number. Invalid content fails before replacing the output snapshot.

- `fecha_acuerdo` and `fecha_aprob`: **2013-10-09**, the dated Commission session
  adopting definitive approval, as stated in the edict.
- `fecha_publicacion`: **2014-01-28**, from the DOGC issue header (no. 6549).
- The edict's own date, 2014-01-21, is neither the approval nor publication date.
- Generic `fecha` remains null. Crawl/page timestamps are not event dates.
- One stable ID comes from RPUC dossier identity. All three selected POUM source
  links are grouped in `documentos`; the PDF is also `url_documento`. It is not
  one output row per attachment. `date_provenance` points to the actual edict PDF.
- `lat`, `lon` and `geometry` remain null. No municipal centroid or jitter is used.
- Updates refresh this complete, deliberately narrow snapshot. `state_path` is
  unused because the source is a current single-page listing, not an event feed.
- Licence methods return disabled with zero rows; no grant status is inferred.

## Validation and evidence

Executed with:

```
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_caldes_de_malavella -v
```

Seven tests passed: grouping related documents while excluding amendments/maps;
distinct publication/agreement semantics and null geometry; stable identity;
rejection of login/navigation/form/pagination/foreign-host content; missing or
incorrect PDF semantics; failed extraction preserving previous output; and
manifest loading through the shared adapter registry with licences disabled.

A real `load_portal_adapter(load_manifest('caldes-de-malavella'))` extraction,
with the local capture directory supplied in adapter configuration, returned
`status=ok`, **one live project**. The shared entity-policy annotation reported
zero unknown records. Nothing was published or sent to a database.

Local uncommitted evidence under `evidence/` includes `proyectos.jsonl`,
`validation.json`, `urbanisme.html`, `Normativa_POUM.pdf`, extracted PDF text,
`inventory.html`, `transparency.html`, `works-ajax.xml`, and `rpuc.html`.
`validation.json` records the runtime test command, live count, source URLs and
coverage limitations. Evidence is not part of the four source-file deliverables.
