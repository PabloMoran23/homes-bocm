# La Pobla de Mafumet — INE 43109, Tarragona

Verified live on 2026-11-09 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Implemented one municipal adapter. Coverage is deliberately partial: POUM
modifications explicitly listed with an approval phase in the current municipal
public-exposure inventory. This is not the complete planning history or a public
register of granted licences. Schedule and missing-coordinate jitter are disabled.

## Official source discovery

- Municipal home: https://www.poblamafumet.cat/ — HTTP 200. Its navigation links
  directly to “Exposició pública”, the electronic noticeboard, transparency and
  the legacy RPUC POUM dossier `codintExp=230661`.
- Current municipal document inventory:
  https://www.poblamafumet.cat/documents-subjectes-a-exposicio-publica — HTTP 200.
  One supported planning instrument: “Aprovació inicial de la modificació puntual
  núm.6 del POUM”, linked document titled “Modificació puntual del POUM de La Pobla
  de Mafumet Àmbit del PAU‐I”. Other entries concern environmental authorisations
  for Dow, Carburos Metálicos and Repsol, some spanning neighbouring municipalities;
  these are excluded rather than inferred to be projects or building licences.
  The current response has no pagination. The adapter checks for pagination and
  raises rather than silently extracting only the first page.
- Planning transparency inventory:
  https://seu-e.cat/ca/web/lapoblademafumet/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  — HTTP 200. Links the official RPUC municipality search with `municipiSel=43109`
  and MUC; it is a referral page, not individual project records.
- Municipality RPUC search:
  https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=43109
  — redirects to the Angular application at
  `https://planejamenturbanisme.territori.gencat.cat/rpucportal/index.html#/consulta/cercaPublic?reqCode=cerca&municipiSel=43109`.
  HTTP 200 delivers the application shell. Its complete inventory was not
  extracted; the adapter does not claim RPUC completeness.
- Urban regulations page:
  https://seu-e.cat/ca/web/lapoblademafumet/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/normativa-d-urbanisme
  — HTTP 200. Links RPUC dossier 230661 and a municipal PDF for modification 1.
  This separate regulations resource is outside the implemented current-exposure
  snapshot. Its 15/12/2016 update timestamp is not an instrument approval date.

## Extracted instrument and document provenance

The municipal heading and adjacent links establish modification 6 as one
instrument. All adjacent links are retained, and duplicate headings for the same
modification merge their documents; conflicting phases fail closed. Identity uses
municipality + inventory URL + modification number, independent of link order.
No municipal expediente number is invented from a modification number or a BOPT
publication identifier.

Municipally published plan link:
https://drive.google.com/file/d/1EPBqfejSp8q9ZhDoRUAv1KdTYloqiV3E/view?usp=drive_link
returned HTTP 404 (also checked without the query string). It remains in the
record with municipal provenance. It is not presented as a successfully downloaded
technical plan.

Supplemental official notice, HTTP 200:
https://aplicacions.dipta.cat/bopt/web/anunci/351869/modificacio-puntual-num-6-del-pla-d-ordenacio-urbanistica-municipal-poum-aprovacio-inicial-ajuntament-pobla-de-mafumet-la

Accessible notice PDF, HTTP 200, verified PDF signature:
https://aplicacions.dipta.cat/bopt/web/anunci/descarrega-pdf/351869

The adapter checks the BOPT heading, modification number, initial-approval phase,
municipal advertiser, registration 2025-09478 and download URL before joining this
supplement to modification 6. The labelled publication date is **2025-10-22**.
The notice PDF explicitly links back to the municipal inventory and describes
modifying the ordering and regulatory parameters of PAU-I, confirming this is an
actual planning instrument rather than a procurement announcement or a form.
The PDF is the notice, not the complete technical plan.

Manual inspection of `evidence/bopt-351869.txt` (generated with installed
`pdftotext -layout`) distinguishes the plenary agreement **2025-10-09**, electronic
signature **2025-10-14**, and bulletin publication **2025-10-22**. The adapter parses
HTML only, so `fecha_acuerdo` and `fecha_aprob` remain null; it never substitutes
publication or signature dates. Generic `fecha` also remains null. Initial approval
is the phase evidenced by the listing and notice, not a claim about subsequent
legal developments or definitive approval.

## Extraction and validation

Requests use anonymous public HTTP GET, a 35-second timeout and a 5 MB response
bound. Oversized responses, missing inventory markup, missing planning documents,
conflicting phases, pagination and invalid supplemental notice identity raise
errors before output replacement. Updates refresh the entire supported current
inventory; they do not append stale records or promise historical completeness.
The parser only supports headings explicitly identifying initial, provisional or
definitive approval of numbered POUM modifications. Other instrument types need
future parser work. Licence methods return disabled and empty output.

Six parser/contract tests passed:

```text
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_la_pobla_de_mafumet -v
```

Tests cover exclusions, date semantics, instrument/document grouping, stable IDs,
pagination and malformed-source rejection, BOPT identity checks, full extraction
flow with fixtures and manifest loading. A separate real live extraction used
`load_manifest`, `load_portal_adapter` and `backfill_proyectos`, yielding **1 real
record**, with the municipal plan link and BOPT PDF grouped together.

Local uncommitted evidence under `evidence/` includes `proyectos.jsonl`,
`validation.json`, discovery HTML, the broken Drive response, live inventory and
BOPT captures, and the notice PDF/text. Validation records source URLs, live count,
tests and limitations. The shared entity policy conservatively annotates this
unreferenced planning instrument as `pendiente / insufficient_identity_evidence`;
no fictitious expediente is inserted to override that decision.

No project geometry was obtained. `lat`, `lon`, and `geometry` are null and
`publication_ready` is false. No centroid, random coordinates, forms, unrelated
news, procurement items or environmental authorisations become project records.
No shared files, dependencies, credentials, production services, git metadata or
publishing operations were changed or used.
