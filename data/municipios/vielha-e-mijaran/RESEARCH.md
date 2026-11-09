# Vielha e Mijaran — INE 25243, Lleida

Live verification: 2026-11-09. Implemented a deliberately partial municipal
planning-document inventory. Scheduling, granted licences and missing-coordinate
jitter are disabled. This is extractable planning documentation, not a claim of
complete municipal coverage, current legal validity or publication readiness.

## Official source discovery

- Municipal homepage: http://www.vielha-mijaran.org/ redirects to `/ar/` and
  links to the municipal Urbanisme and Servicis tecnics sections.
- Inventory actually extracted:
  http://www.vielha-mijaran.org/ar/menu/er-ajuntament-/14/gestion-municipau-/23/urbanisme/28/
  — HTTP 200, fourteen heading groups and seventeen detail links. Twelve heading
  groups describe instruments; the consolidated urban fabric and acoustic maps
  are excluded. The remaining fifteen detail pages contain 28 PDF document links.
  This inventory has no pagination controls in the captured response.
- Detail pages: `/fitxaUrbanisme/{12,18,20,45,47,49,53,55,63,64,65,66,72,74,77}`
  on the same official host. Their tables expose document titles and direct PDF
  links under `/public/vielha/ftp/urbanismoarchivos/`.
- Municipal transparency planning inventory:
  https://seu-e.cat/ca/web/vielhaemijaran/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  — HTTP 200. It links the municipality-filtered RPUC search
  `https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=25243`
  and MUC viewer. The RPUC link redirects to
  https://planejamenturbanisme.territori.gencat.cat/rpucportal/index.html
  (application shell); no complete RPUC dossier/geometry enumeration is claimed.
- Technical-services index:
  http://www.vielha-mijaran.org/ar/menu/er-ajuntament-/14/gestion-municipau-/23/servicis-tecnics-/26/
  links `/fitxaServei/32` as municipal projects. That page's fetched response
  has the heading “Projèctes” but no labelled project document table. It supplies
  no records to this adapter.
- https://vielha-mijaran.eadministracio.cat/info.0 exposes a procedure catalogue,
  including Urbanisme i obres. Forms are not granted licences and are excluded.
- HTTPS on `www.vielha-mijaran.org` failed certificate verification (self-signed
  certificate). The municipal site's own public links use HTTP and work; the
  adapter uses those links and never disables TLS verification.

## Records and provenance

The complete selected inventory yields **13 instruments and 28 PDF links**:
NNSS modifications 71 and 72; modification 68 at Gausac; modification 69 at Mont;
NSCP 1/2016 PMU 2.1; NSCP 2/2015 Plaus; La Closa; recreational uses 3_2017;
partial-plan modification for Mijaran; tourist-housing modification; PAU 3
boundary/equidistribution at Arròs; PAU 11 Solan de Naut; and the separate PAU 3
reparcel·lació project. These last two PAU 3 instruments share an area but serve
different purposes and have distinct municipal headings.

Four tourist-housing document pages (63–66: summary, unitary document,
provisional-approval announcement and consolidated text) become one instrument.
The combined heading NNSS 71–72 becomes two instruments, assigning documents by
the explicit numbered table labels. Unassignable documents cause failure.
All detail-page URLs and each document's original title, URL and referring page
are retained. Stable identities derive from municipal detail URLs and, for the
combined heading, the explicit modification number; no expediente is fabricated.

Three PDFs were also downloaded for manual provenance checks and captured locally:
NNSS 71's summary identifies the municipality and planning modification; PAU 11's
announcement names the urbanistic action; PAU 3's PDF names the reparcel·lació
project and municipality. Captures and extracted first-page text are in evidence/.
These checks verify that the selected packages contain actual instruments, rather
than treating a procurement notice, application form or general news as a project.

## Date semantics and limits

The adapter extracts inventory metadata and document links, not PDF body fields.
It leaves `fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` and `fase`
null. The inventory exposes no reliable dated event fields. Filename numbers,
plan-reference years, crawl dates and document labels are never used as dates.
For example, the sampled PAU 11 announcement separately states an agreement of
28 March 2023 and an electronic signature of 8 May 2023, and refers to a future
BOP publication. Neither the signature nor the filename proves publication.
Those PDF dates are not extracted by this inventory-only adapter. Document labels
such as “aprobacion provisionau” are retained verbatim, without claiming that
this is the instrument's latest legal phase. The legacy inventory can include
superseded proposals; no current-validity inference is made.

No geometry is extracted, even where linked PDFs contain plans. Coordinates and
geometry remain null, `publication_ready` false. This covers neither every RPUC
instrument nor all physical public works, grants or licences.

The shared entity policy labels all 13 entries `pendiente`, with reason
`insufficient_identity_evidence`, and reports `unknown_entity_spike`. The municipal
inventory identity is not a municipal expediente number, and the adapter does not
invent one to bypass that guard. Records remain ineligible for activity/publication;
this is a usable source scraper with an explicit downstream identity limitation.

## Validation and operation

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_vielha_e_mijaran`: 7 tests passed. They check
  grouped documents, separation of NNSS 71/72, dates/coordinates left unknown,
  rejected forms/maps/navigation, pagination failure, document provenance,
  stable identity, disabled licences and full-refresh update delegation.
- Live extraction through `load_manifest` and `load_portal_adapter`, calling only
  `backfill_proyectos`: 13 records, 28 linked documents. Each selected detail
  page was fetched live. Local `evidence/proyectos.jsonl`, `validation.json`,
  source HTML, three PDF samples and text captures support this result.
- `validation.json` retains source URLs, live count, limitations and the shared
  entity-policy incident; extraction success does not imply publication approval.

Fetches have 30-second timeouts and a 4 MB HTML limit; HTTP errors, unexpected
hosts, missing document tables, ambiguous grouping and detected pagination raise
errors before the output snapshot is replaced. Backfill and update refresh the
whole unpaginated inventory. If the site introduces pagination, the adapter fails
explicitly pending a traversal update rather than silently truncating results.
PDF contents are linked, not downloaded during normal adapter execution.
Evidence is local and must not be committed. No shared sources, dependencies,
credentials, database, deployment or git metadata were changed.
