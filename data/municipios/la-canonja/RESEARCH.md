# La Canonja — INE 43907, Tarragona

Verified on 2026-11-09 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Official source discovery

- Municipal department catalogue:
  https://www.lacanonja.cat/ova_dep/urbanisme-i-territori/
  returned HTTP 200. It explicitly identifies the municipality's definitively
  approved POUM and associates it with a direct official RPUC dossier link.
  This is the extraction source, rather than news, application forms or tenders.
- Linked dossier:
  https://planejamenturbanisme.territori.gencat.cat/rpucportal/index.html#/consulta/detallExpedient/259094
  returned HTTP 200 with the JavaScript application shell. The municipal link is
  retained as document provenance; the shell is not represented as parsed dossier
  content. The public application bundle was inspected during discovery, but no
  authenticated service or underlying document API is used by this adapter.
- Transparency planning inventory:
  https://seu-e.cat/ca/web/lacanonja/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  returned HTTP 200 and links to the RPUC municipality search with
  `municipiSel=43907`, plus the MUC viewer. It does not itself expose instrument
  rows. These external application inventories are outside the extraction scope.
- The department also links https://gis.lacanonja.cat/canonjagp . No project
  geometry was verified from this viewer; no geometry claim is made.
- The current home page https://www.lacanonja.cat/ returned HTTP 200. Search also
  surfaced legacy municipal PDFs and news. They are not assumed to be a complete
  current inventory and are not converted into extra records.

## Implemented coverage and semantics

Exactly one genuine planning instrument is extracted from the current municipal
catalogue: the POUM, associated with RPUC dossier 259094. Its identity is derived
from that dossier, not its display order or crawl time. The source heading
explicitly says definitive approval, so `fase` records that status. It gives no
approval, agreement or publication date: `fecha`, `fecha_aprob`, `fecha_acuerdo`
and `fecha_publicacion` remain null. Dates mentioned in search snippets, image
paths or page metadata are not substituted.

The source is one non-paginated catalogue entry, not a paginated search. All links
inside the entry are examined and official dossier references are deduplicated
into one instrument's `documentos` list. Links outside the entry cannot supply a
missing dossier. Ambiguous dossier identifiers, a missing heading/dossier, changed
structure, or pagination controls in the catalogue container raise errors instead
of emitting a partial or placeholder record. The internal RPUC document list is
not fetched: the retained URL is a registry dossier link, not a claim that its
PDFs have been downloaded. This is deliberately partial coverage, excluding other
POUM amendments, derived plans, historical instruments and physical works.

Backfill fetches the live catalogue with a 30-second request timeout and a 2 MB
response limit. Unexpected redirects and HTTP failures abort extraction. Update
refreshes the same full snapshot; it does not infer incremental changes from
missing dates. Existing requests/BeautifulSoup dependencies are used unchanged.

No licences are extracted. A licence request is not evidence of a grant. No
coordinates, municipal centroid, jitter or project geometry are fabricated;
`publication_ready` remains false. Scheduling, licences and coordinate jitter are
disabled in the manifest. The existing registry entity-policy annotation marks
this planning record as `pendiente` / `insufficient_identity_evidence`; this does
not establish a licence grant or a publishable physical work.

## Validation and local evidence

- `python -m unittest municipio.test_la_canonja -v`: 7 tests passed. Tests cover
  municipal identity, missing dates/geometry, link deduplication and stable
  identity, exclusion of forms/news/navigation, dossier provenance and ambiguity,
  pagination rejection, manifest adapter loading and snapshot-update delegation.
- Live extraction through `load_manifest`, `load_portal_adapter` and
  `backfill_proyectos`: 1 real record, status `ok`.
- `evidence/proyectos.jsonl`: actual extracted record including the shared entity
  policy annotation.
- `evidence/validation.json`: live count, source URLs, limitations, test result
  and timestamp. Captures include `urbanisme-live.html`, `urbanisme.html`,
  `planejament.html`, `rpuc.html` and `home.html`.

Evidence is local and is not part of the four source files. No shared code,
dependencies, git metadata, credentials, databases or publishing systems were
changed or used. Independent review is still required (`accepted=false`).
