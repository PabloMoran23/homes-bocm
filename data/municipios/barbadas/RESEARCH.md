# Barbadás — INE 32008, Ourense, Galicia

Verified live on 2026-11-07 using the preinstalled batch Python runtime.
This adapter covers the municipal general and development planning inventory
published by SIOTUGA, linked from the Concello's Urbanismo page. It does not
claim complete coverage of public works, planning proceedings or granted licences.

## Official source discovery

- https://www.barbadas.es/concellerias/urbanismo-gl/ — HTTP 200, municipal
  department page. Its Urbanismo link points to the former
  `http://www.planeamentourbanistico.xunta.es/siotuga/inventario.php` address.
  The working HTTPS SIOTUGA inventory is used below. The department's service
  description and application procedures are not extracted as records.
- https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=32008 — HTTP
  200, official Xunta inventory; selector explicitly identifies `32008` as
  `Barbadás`. Detail responses independently identify `Barbadás` / `BARBADAS`.
- https://siotuga.xunta.gal/siotuga/assets/inventario/controls.min.js?2.5.0 —
  official public browser client inspected to establish request semantics.
  It submits the selected municipality to `query_document.php` with `idclase`
  14 (general), 13 (development), 16 (historical), and 18 (rural delimitations).
  These return complete JSON arrays, subsequently paginated locally by
  DataTables. No server page or limit is supplied by the official client.
- https://siotuga.xunta.gal/siotuga/assets/inventario/query_document.php —
  read-only POST query with `id=32008`, `idclase=14` or `13`, and the anonymous
  public form token acquired in the same session. Not a login or private API.
- https://siotuga.xunta.gal/siotuga/assets/inventario/getIOTPU.php — read-only
  POST detail query with the discovered `iddoc`, `idp=0`, `lang=gl_ES` and the
  public form token. Returns metadata and every grouped document component.
- https://www.barbadas.es/transparencia/ — HTTP 200, investigated as an
  alternative inventory; no additional extraction implemented from this page.
- https://barbadas.sedelectronica.gal/ — discovered official procedures catalogue;
  urbanism application forms do not establish licences granted. Disabled.
- Xunta's environmental assessment search identified modification no. 1 of the
  PXOM, reference `2024AAE2880` / `2763/2025`, on the official
  `https://medioambiente.xunta.gal/programas-con-periodo-de-consulta-aberto`
  detail page (query parameter `_aaeOpen_WAR_aae_id=2763`). Direct requests from
  this runtime fail certificate-chain verification. TLS verification was not
  disabled. This separate environmental proceeding is excluded from extraction;
  its environmental report is not treated as planning approval.

Historical class 16 returned seven entries; class 18 returned JSON null.
The territorial `assets/iot/queryIotInv.php` query returned five regional or
supramunicipal instruments, including Galicia-wide plans. These are excluded
from this municipal planning snapshot. Captures of discovery responses are local.
The adapter itself deliberately requests only classes 14 and 13.

## Live extracted coverage

| SIOTUGA ID | Instrument | Definitive approval | DOG publication | BOP publication | Document links |
| --- | --- | --- | --- | --- | --- |
| 22572 | Plan Xeral de Ordenación Municipal | 2002-07-19 | 2002-08-09 | 2002-08-14 | 66 |
| 24359 | Plan Parcial — Sector J | 2001-08-08 | 2001-09-17 | 2001-08-24 | 33 |
| 24361 | Plan Parcial — Sector I | 1993-05-19 | unavailable | unavailable | 27 |
| 24360 | Plan Especial de mellora do núcleo rural dos Muíños | 2004-07-29 | 2004-09-02 | 2005-02-01 | 14 |
| 25294 | Plan Especial de reforma interior no AR-1 | 2004-04-26 | 2004-05-26 | 2004-05-26 | 27 |

Five actual instruments, 167 retained document URLs. Raster plans, regulations,
memorias and annexes remain children of their instrument, not separate projects.
Titles and IDs are discovered from the live inventory, not hardcoded records.
The old approval dates reflect the currently published inventory and are not
crawl dates. Being in these inventory sections is not independent confirmation
of present legal validity; source legal-incidence metadata is retained.
No procurement announcements or general news are converted into projects.

`fecha_aprob` comes only from `fechaaddef`. DOG, BOP and normative BOP dates
are separate explicit fields. `fecha`, `fecha_publicacion` and `fecha_acuerdo`
remain null because there is no single generic date or independently labelled
agreement date. Missing source dates remain null. Each document retains its
label, group, component ID, file URL and detail-query provenance. Query tokens
are ephemeral and not part of record identity or provenance parameters.

## Extraction safeguards and limitations

The adapter fetches the entire supported arrays and all their detail responses.
It rejects unexpected JSON envelopes (including a future pagination envelope),
malformed IDs, missing titles, conflicting duplicates, inconsistent detail dates,
wrong municipality, missing documents and unexpected document paths. Response
size limits fail explicitly; they do not produce partial output. HTTP errors,
empty combined inventories and login/changed markup fail before replacing an
existing output. Updates refresh the full supported snapshot atomically.

The public pages have no verified vector geometry in these responses. Raster
plan links are retained without deriving coordinates or substituting a municipal
centroid: `lat`, `lon`, `geometry` are null and `publication_ready` is false.
Manifest scheduling, coordinate jitter and licence ingestion are disabled.

Only one linked PDF per instrument was sampled: all five samples returned HTTP
200 with a PDF signature and were captured. The other 162 links are preserved
as listed, without asserting that every file is currently downloadable. An
initial PXOM memoria sample exceeded the 10 MB local evidence capture cap; the
subsequent sample uses its smaller linked index. The inventory and document
lists were never truncated.

## Validation and evidence

Command:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_barbadas -v
```

Eight offline tests passed: grouping/provenance, distinct dates, missing dates,
identity/date mismatches, invalid dates, absent/unsafe documents, complete-array
handling/pagination rejection, full refresh/failure preservation, manifest and
disabled licences (some cases share tests).

Live extraction used `load_manifest('barbadas')`, `load_portal_adapter(manifest)`
and `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, with local capture
configuration pointing to `evidence/live`. Result: 5 records, 167 document links.
The shared entity policy labels these planning records `unknown` (5/5); this is
retained transparently and does not imply fabricated business entities.

Local, uncommitted evidence: `evidence/proyectos.jsonl`, `evidence/validation.json`,
`evidence/live/inventory-page.html`, the two inventory arrays, five detail JSON
responses, five sampled PDFs, municipal discovery HTML and the official JS.
`validation.json` includes live count, source URLs, checks and limitations.
No shared source or dependencies changed; no publication or deployment run.
