# Vila de Cruces — INE 36059, Pontevedra

Verified live on 2026-11-09. Adapter:
`municipio.adapters.vila_de_cruces:VilaDeCrucesAyuntamientoAdapter`.
Inspected the shared portal contract, manifest loader, adapter registry and existing
Manlleu/Chipiona implementations before implementation. No shared files or dependencies changed.

## Official sources and actual coverage

- [Urbanismo](https://viladecruces.es/urbanismo/): municipal narrative identifies
  the Plan Xeral de Ordenación Municipal (PXOM) and explicitly attributes its
  initial approval to the plenary agreement of **17 February 2014**. The separate
  **19 May 2014** date closes the objections period; it is not an approval date.
  The adapter emits one PXOM instrument with `fecha_acuerdo` and `fecha_aprob`
  from that explicit narrative, and no publication date. The page names a PXOM
  document link but currently provides no actual hyperlink in its article body.
  No document URL is invented. The page also describes the subsidiary norms as
  applicable pending PXOM approval; the adapter does not expand that reference
  into a separate detailed instrument or assert independently verified currency.
- [Ordenanzas inventory](https://viladecruces.es/ordenanzas/): current municipal
  listing contains three posts, of which one is a planning instrument. Its widget
  specifies 16 posts per page, pagination enabled, offset zero; only three posts
  and no pagination links are currently exposed. The parser follows every explicit
  numbered/next pagination link, deduplicates URLs, handles cycles and fails rather
  than silently truncating at its safety bound or known dynamic pagination controls.
  The other entries concern a timber removal communication form and a civil
  ceremony regulation, and are excluded.
- [Cumeiro initial approval](https://viladecruces.es/2025/10/15/aprobacion-inicial-da-modificacion-puntual-da-normas-subsidiarias-de-planeamento-para-a-delimitacion-do-nucleo-rural-de-cumeiro/):
  a concrete modification of subsidiary planning norms delimiting the rural nucleus
  of Cumeiro. Article `datePublished` is **15 October 2025**, retained exclusively as
  `fecha_publicacion`. One instrument groups the following two supporting links;
  the duplicate PDF download button does not create a second document or project:
  - [Plenary certificate PDF](https://viladecruces.es/wp-content/uploads/2025/10/20250929_Certificado_Certificado-de-acordos_CERTIFICADO-ACORDO-PLENARIO.pdf).
  - [Municipal Nextcloud documentation share](https://nextcloud.viladecruces.gal/s/6oNB3PwpCFjB9XK).

Both supporting links returned HTTP 200 during research. The PDF was captured and
inspected with the existing `pdftotext` utility: its first page identifies expediente
**663/2022**, plenary session **29/09/2025** and the initial approval of the Cumeiro
modification. This confirms that the instrument is real and publication and agreement
are different events. The adapter deliberately does not parse PDFs or infer dates from
filenames: Cumeiro agreement/approval dates remain null in its machine output. The
Nextcloud share HTML was captured, but its internal files are not enumerated or parsed;
the share URL is retained as a document collection, not presented as an individually
verified file inventory.

[Administración local](https://viladecruces.es/administracion/) was also inspected as
a discovery surface. Its descriptive links to procurement are not project evidence.
No verified public register of granted licences was found in these surfaces. No
licence application, contract announcement, unrelated news or blank placeholder is emitted.

## Limits and semantics

This is a partial inventory of the two selected official municipal planning surfaces,
not an exhaustive municipal project, public works, historical planning or licence
register. It does not crawl all news, the electronic headquarters, regional registries
or procurement platforms. The dated planning phases describe what each source
reports; they do not establish the current legal status in 2026. Discovery is limited
to named planning titles and supporting documents on the selected inventory. Future
unsupported markup fails explicitly. Updates refresh the complete selected snapshot;
there is no date cutoff or pagination truncation in a successful result.

No coordinates or geometry were verified. All geometry remains null and
`publication_ready=false`. Scheduling, licence extraction and missing-coordinate
jitter are disabled in the manifest. Document links preserve provenance via
`documentos[].source_url`; the PXOM description preserves its source paragraphs.

## Reproduction and local evidence

Use the preinstalled runtime, with the repository as working directory:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_vila_de_cruces -v
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python - <<'PY'
import json
from pathlib import Path
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter
m = load_manifest('vila-de-cruces')
m.portal.config['capture_dir'] = 'evidence/live'
a = load_portal_adapter(m)
result = a.backfill_proyectos(Path('evidence/proyectos.jsonl'))
print(json.dumps(result, ensure_ascii=False, indent=2))
PY
```

Six offline tests passed: agreement vs. objection/publication dates, grouped documents,
excluded forms/procurement/news, changed markup and external-link rejection,
multipage traversal with cycles/deduplication and failure preserving the previous
snapshot, plus manifest loading and disabled licences.

The real extraction through the manifest/registry returned **2 actual instruments**
from **1 inventory page** plus Urbanismo and the Cumeiro detail page. Local evidence:
`evidence/proyectos.jsonl`, `evidence/validation.json` (runtime, live count, exact source
URLs, limitations, timestamp and parser-test result), `evidence/live/*.html` (adapter
captures), and named discovery HTML/PDF/text captures under `evidence/`.
Evidence is local and must not be committed.
