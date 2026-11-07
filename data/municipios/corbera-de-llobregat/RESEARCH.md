# Corbera de Llobregat — INE 08072, Barcelona

Verified live on 2026-11-07 using the preinstalled Python environment. This
adapter covers the **current municipal Urbanisme i territori section**, not the
whole municipality's historical planning, public works or granted licences.
Scheduling and missing-coordinate jitter are disabled. `publication_ready` is
false; no project geometry has been verified.

## Official source discovery

- Municipal homepage: https://www.corberadellobregat.cat/ links directly to
  https://www.corberadellobregat.cat/ajuntament/urbanisme-i-territori . The latter
  is the extraction inventory, HTTP 200, with three unique entries duplicated in
  desktop/mobile menus. All three are traversed, not just the first result.
- The inventory's **Can Margarit reparcellation** detail has six municipal PDF
  links (report, memory, annexes and subarea volumes). Its actual heading states
  definitive approval by the Local Government Board on **22 June 2026**. This is
  the agreement/approval date, not a publication date. The page's **23 July 2026**
  timestamp is explicitly a last-update date and is stored separately.
- Its **initial approval of executive forest-fire prevention projects** entry
  has eleven linked neighbourhood detail pages, all fetched: Ca n'Armengol,
  Can Canonge, Can Coll, Can Llopard, Can Margarit, Can Palet, El Bon Repòs,
  La Creu de l'Aragall, La Creu de l'Aragall Junior, Les Cases Pairals and
  Santa Maria de l'Avall. The detail pages expose **19 actual technical projects**:
  external protection strips and/or vegetation reduction on municipal parcels.
  Each named project groups its own memory, specifications, budget, safety study
  and drawings. These are physical vegetation-management projects, not building
  permissions. Initial-approval phase comes from the parent heading; its URL and
  exact wording are retained. No agreement date appears in the parsed headings.
- Its **La Servera reparcellation and urbanisation** detail exposes six PDFs:
  joint definitive-approval edict, registry certifications, separate project
  approval certificates and both project documents. The adapter retains the
  municipality's combined dossier as **one record**, with all six links. The
  definitive-approval phase is evidenced by document labels. Approval dates
  inside PDFs are not parsed and remain null, rather than using the page's
  22 October 2025 update timestamp or a year in a filename.
- https://www.corberadellobregat.cat/ajuntament/govern/regidories-organitzacio-municipal/area-durbanisme.html
  was also fetched (HTTP 200). It describes departmental responsibilities and
  links to a works procedure; that text is not a licence register or project.
- Discovery also located the official transparency urbanism directory at
  https://seu-e.cat/ca/web/corberadellobregat/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme
  and the AMB planning inventory at
  https://www.amb.cat/s/web/territori/urbanisme/planejament-urbanistic.html . These
  are **outside this adapter's extraction scope**. No claim is made that the
  three-entry municipal section covers those inventories. Procurement notices,
  general news and licence application forms are not ingested.

Exact live detail URLs are recorded in `evidence/validation.json` and each
record's `url`, `fase_url` where applicable, and `documentos[].pagina_origen`.
No dates, municipal expediente references, coordinates or geometries are
synthesized from filenames, crawl time, neighbourhood names or municipal centres.

## Extraction and failure handling

The adapter implements the existing AyuntamientoAdapter contract and loads via
its manifest's module/class spec without registry changes. Updates refresh the
entire current-section snapshot; they do not claim incremental historical
coverage. Requests are anonymous, use connection/read timeouts and stream HTML
with a 4 MB limit. Only official municipal child-page links are crawled. HTML
captures can be enabled with `portal.config.capture_dir`.

Responsive duplicate links are deduplicated. Pagination links cause an explicit
error, so a future paginated inventory cannot silently produce a partial first
page. Empty inventories, unexpected entry types, absent technical headings,
missing PDFs, orphaned project documents, error/login markup and duplicate
identities also fail before replacing output. The live CMS has a trailing empty
heading on Can Coll; it is ignored only while verifying that every PDF in the
technical body belongs to an extracted project. PDF links are retained, not
expanded into separate records. The adapter does not fetch/parse every PDF or
resolve geometry embedded in drawings.

## Validation and limitations

Run from the repository root:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_corbera_de_llobregat -v
```

Eight offline tests passed: agreement/update/publication semantics, document
label phase without invented dates, grouping distinct fire projects, duplicate
menus, empty headings/orphan documents, pagination rejection, rejection of
forms/login/missing documents, and preservation of an existing snapshot when
fetching fails (also disabled licences).

A real live extraction used `load_manifest('corbera-de-llobregat')` and
`load_portal_adapter(...).backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
It fetched 15 inventory/detail pages, producing **21 records with 146 document
links**, all with null coordinates/geometry. One Can Armengol memory and the
La Servera edict were additionally downloaded: HTTP 200 with PDF signatures,
483110 and 175382 bytes respectively. Other document links are retained from
municipal HTML but their HTTP availability was not individually checked.

The shared entity policy annotates all 21 rows as `unknown` and reports
`adapter_incident / unknown_entity_spike`. This is a downstream acceptance
limitation, retained in local validation; the adapter does not invent municipal
expediente numbers or alter shared classification to avoid it. The records are
real source-backed projects, but acceptance/activity eligibility and map
publication remain subject to independent review.

Local uncommitted evidence includes `proyectos.jsonl`, `validation.json`,
`parser-tests.txt`, discovery HTML, two PDF samples and `captures/`. Capture
filenames are the first 20 hexadecimal SHA-256 characters of the request URL,
followed by `.html`; `source_urls` permits replay/mapping. No shared sources,
dependencies, credentials, databases, deployment tools or git metadata were
modified.
