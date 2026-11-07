# La Ràpita — INE 43136, Tarragona

Verified 2026-11-07 using the preinstalled Python runtime:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Official inventory discovery

- https://seu.larapita.cat/urbanismeCategoriaPublic/listCategories redirects to
  category 5 (Planejament urbanístic). Local capture: `evidence/categories.html`.
- https://seu.larapita.cat/urbanismeCategoriaPublic/listPublicacionsAmbCategoria?categoria.id=5&multiseu=
  is the extraction source. HTTP 200, one publication explicitly titled POUM,
  43 attached document links. Capture: `evidence/planejament.html`.
- https://seu.larapita.cat/urbanismeCategoriaPublic/listPublicacionsAmbCategoria?categoria.id=6&multiseu=
  (Instruments de gestió urbanística) returns HTTP 200 and explicitly zero results.
  Capture: `evidence/gestio.html`. This is an empty category, not evidence that
  there are no urban-management instruments in the municipality.
- http://poum.larapita.cat/ is linked from the official inventory. HTTP 200,
  historical plan-preparation site, with 2010 participation items. It is not
  substituted for a current consolidated instrument inventory. Capture:
  `evidence/poum.html`.
- https://seu-e.cat/ca/web/larapita/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  was discovered through web search; its indexed text refers to Generalitat
  RPUC/MUC. No RPUC dossier or geometry was extracted.
- https://cido.diba.cat/normativa_local/7035205/planejament-urbanistic-ajuntament-de-sant-carles-de-la-rapita
  was discovered through web search and lists subsequent amendments, including
  entries in 2026. It is not an extraction source for this adapter. Its existence
  is additional reason not to describe the base POUM snapshot as comprehensive
  or consolidated planning coverage.

## Provenance and semantics

Exactly one real planning instrument is extracted, with stable ID derived from
its official publication-register link:
https://seu.larapita.cat/registrePublic/registrePublicacio/53 . This register ID
is not represented as a municipal expediente number. All 43 attached catalogues,
normative documents and map sheets remain together in `documentos`, each with
its original label, absolute URL and inventory provenance. The primary document
URL is the first source attachment, not a fabricated consolidated plan PDF.
The PDFs have not been downloaded or interpreted, and availability is unverified.

The source states initial approval by Ple on 2012-07-12, provisional approval by
Ple on 2013-09-26, definitive approval by CTUTE on 2014-02-04, and publication of
the rules in DOGC on 2014-05-12. These are separate fields. The earlier
2012-01-24 14:33 publication-register timestamp is retained separately, with its
raw source text, and never used as DOGC publication or approval. Generic `fecha`
is null. Dates are parsed from the source, not supplied from this research file.

The inventory gives no verified feature coordinates or geometry. `lat`, `lon`
and `geometry` remain null, `publication_ready` is false, and jitter is disabled.
No granted-licence inventory has been verified; licence forms, procurement
announcements, news and navigation links are not records. Licences and scheduled
execution are disabled in the manifest.

## Transport and completeness limitations

The municipal seat's TLS certificate is expired: both urllib and requests reject
it with certificate verification enabled. The manifest explicitly enables
`allow_expired_certificate` for the fixed, public, read-only inventory endpoint.
The adapter defaults to verification when this setting is absent, refuses all
redirects, preserves urllib3's warning and reports `tls_verified: false`.
Consequently transport authenticity could not be verified. No authentication,
credentials or private endpoints were used. The general municipal website also
failed local TLS verification and is not used by the adapter.

This is deliberately partial coverage of the base POUM currently exposed by the
seat, not a guarantee of its current consolidated legal text. Later modifications,
other instruments, public works and licences are outside coverage. The single
publication count must match exactly one POUM block; nonempty pagination or a
changed count raises an explicit error instead of silently truncating. The
observed pagination widget is empty. Update refreshes the complete snapshot and
does not filter by an artificial date watermark. Responses over 2 MB, missing
identity, changed structure and missing document provenance also fail explicitly.

## Validation

- `python -m unittest municipio.test_la_rapita -v`: eight tests passed, covering
  date distinctions, missing dates, grouping and stable identity, document
  deduplication, rejection of forms/navigation/wrong municipalities, pagination
  and changed totals, transport defaults and disabled licences.
- Real live run via `load_manifest('la-rapita')`, `load_portal_adapter`, and
  `backfill_proyectos`: one record, 43 linked documents. Evidence includes
  `evidence/proyectos.jsonl`, `evidence/validation.json` and the HTML captures.
- Shared entity policy annotates the instrument as unknown (one record) because
  there is no verified expediente reference; no false expediente number was
  invented to make it activity eligible. This record remains non-publication-ready.
- Only the four requested source files are added. Evidence remains local and
  uncommitted. No shared source, dependency or deployment changes are required.
