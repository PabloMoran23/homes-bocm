# Ulldecona — INE 43156, Tarragona, Catalunya

Verified live on 2026-11-09 using the preinstalled batch virtualenv. This adapter
extracts a **partial municipal planning inventory**, not granted licences or a
complete works register. Scheduling and coordinate jitter are disabled. Records
have null geometry and `publication_ready: false`.

## Official source discovery

- Municipal urbanism landing page:
  https://ulldecona.cat/ajuntament/urbanisme/ — HTTP 200. Links directly to the
  municipality's urban planning inventory on its official transparency site,
  the UA4 modification in public exposure, and application forms. Forms such as
  major/minor works licences are excluded: they do not evidence grants.
- Inventory used for extraction:
  https://www.seu-e.cat/web/ulldecona/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/normativa-d-urbanisme
  — HTTP 200, redirects to the `seu-e.cat/ca/web/ulldecona/` equivalent. Article
  footer says `Actualització: 24/05/2024 | Font: Propi ens`. This is an inventory
  update date, never an approval or publication date. The article is a complete
  static list without next-page controls; the footer class `paginacio_footer`
  contains only source/update information. No result/page limit is applied.
- Public exposure link:
  https://www.seu-e.cat/web/ulldecona/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/modificacio-de-normes-subsidiaries-d-ulldecona-en-tramit-i-exposicio-publica-173
  — HTTP 404 after redirect. Not emitted from its navigation label alone.
- Older municipal page https://ulldecona.cat/urbanisme-2/ — HTTP 200, explanatory
  text and an old RPUC search URL, not an extractable register. It explicitly
  warns that municipal copies are informative and certification requires the
  originals approved by the urbanism commission. No full RPUC history is claimed.

## Coverage and provenance

The live adapter emits **16 instruments with 28 document links**: one grouped
Normes Subsidiàries record; four partial plans (Molí de l'Om and Valldepins
I/II/III); UA6; Mangraners; Antic Molí; TUC; Luyflex; PMU El Castell; Deixalleria
dels Terrers; Coveta dels Gats; Les Moles; Lo Tractant; and Lo Pantanet. Noise
capacity regulation is excluded from the physical-project/planning scope.

The first five inventory sections are chapters of the same Normes Subsidiàries,
not five separate projects. Their 13 text/map/chapter links remain grouped.
Subsequent instruments retain every linked PDF under `documentos`, with original
link text, original URL and inventory provenance. Original HTTP document URLs
are preserved rather than silently rewritten. Revisions described within Antic
Molí and Les Moles remain grouped with their instrument and source narrative.
The stale inventory repeated in the page's `accessdirecte_element` header widget
is deliberately excluded; the main article includes later instruments absent
from that widget. IDs use the instrument title, not changing PDF filenames or
crawl timestamps. A title rename can therefore change identity.

Agreement dates and DOGC publication dates are parsed separately. Multiple dates
remain arrays, accompanied by exact narrative context; singular fields are null
when ambiguous. The Les Moles publication array includes its expressly described
correction publication; the context distinguishes that from the original act.
`fecha` and `fase` are null; no approval phase is inferred from instrument type.
Chapter-specific NSU modification dates and page-update dates are not assigned
as dates of the whole NSU. No absent expediente number is synthesized.

Two document spot checks returned genuine PDFs with HTTP 200:

- https://ulldecona.cat/urbanisme/PEU_LoPantanet_CUTE.pdf — title and municipal
  certificate identify Lo Pantanet; commission signature references definitive
  approval on 20/07/2023, consistent with inventory narrative. The municipal
  verification on 27/06/2023 is a separate act, not substituted for that approval.
- https://ulldecona.cat/urbanisme/PEU_Moles.pdf — identifies Les Moles and includes
  municipal initial/provisional certifications and commission definitive approval
  on 10/02/2023. These distinct dates are not collapsed into a new synthetic date.

PDF text spot checks substantiate document identity only. The adapter parses the
HTML inventory, not PDF bodies; not every linked historical PDF was downloaded
or certified as legally current. No parcel geometry, geocoding or municipal
centroid is substituted for project geometry.

## Implementation and validation

The adapter follows `AyuntamientoAdapter` and is loaded through the manifest's
`portal.adapter`. Both update and backfill refresh the complete static snapshot;
state timestamps do not suppress older instruments. Requests have a 45-second
timeout and a 3 MB HTML limit that raises rather than truncating. Ambiguous main
articles, changed NSU grouping, unknown sections, unexpected document hosts,
missing narratives/documents, empty responses and detected pagination fail
explicitly. Licences methods return disabled and no rows.

Command executed:

```
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_ulldecona -v
```

Six tests pass: grouping and date semantics; stale widget exclusion and stable
identity; multiple dates; missing/ambiguous/changed/paginated sources; exclusion
of noise regulation; manifest and disabled-licence contract. Tests use small
inline fixtures and do not require the evidence directory or network.

Real extraction used `load_manifest('ulldecona')`, `load_portal_adapter(...)`,
and `backfill_proyectos(Path('evidence/proyectos.jsonl'))`. The shared entity
policy annotates all 16 records as pending and reports `unknown_entity_spike`:
the inventory lacks official dossier numbers recognized by that classifier.
This remains an explicit review limitation; no shared policy edits or invented
references were used to bypass it. The extractor itself successfully returns
real instruments; it does not claim ingest/publication eligibility.

Local evidence (not source files): `evidence/proyectos.jsonl`, `validation.json`,
`inventory_live.html`, discovery HTML captures, two PDF captures and their text
spot checks. Validation records live count, source URLs, limitations, test result
and document checks. No production, credentials, deployment or publication tools
were used.
