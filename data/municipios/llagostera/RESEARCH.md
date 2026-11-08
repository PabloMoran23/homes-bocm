# Llagostera — Girona — INE 17089

Verified live on 2026-11-07 with the preinstalled batch Python runtime. This
adapter covers the official **municipal works project inventory**, as a complete
snapshot of its currently published single page. It is partial municipal coverage,
not a historical archive, a granted-licence register or comprehensive planning
coverage. Scheduling, licence extraction and missing-coordinate jitter are disabled.

## Official discovery

The municipal Urbanisme page, https://www.llagostera.cat/pagina.php?id=98,
links its Normativa/Urbanisme information to the municipal transparency portal:
https://www.seu-e.cat/web/llagostera/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme .
Both returned HTTP 200. That index links three actual inventories (all fetched
successfully and captured locally):

- **Implemented source:** https://seu-e.cat/ca/web/llagostera/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/projectes-d-obra-municipal-227 .
  Fifteen genuine physical works projects, including the Deixalleria emergency
  area/paving, plaça Barceloneta improvements, sports pavilion flooring,
  carrer Girona reurbanisation and Selva Brava water distribution renewal.
  The inventory says `Actualització: 06/11/2026 | Font: Propi ens`; this is page
  maintenance metadata, not publication or approval of every project.
- https://seu-e.cat/ca/web/llagostera/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic .
  POUM and special-plan documents, SUD-10 modification, SUD-11 modification and
  Font Bona SUD-9 urbanisation modification. Discovered but outside this adapter's
  municipal-works scope; these are not silently counted as extracted projects.
- https://seu-e.cat/ca/web/llagostera/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/projectes-d-actuacio-especifica-231 .
  Four specific-action dossiers, including archived cases and public-information
  projects. Outside extraction scope; public information is not licence concession.

The general service page, application procedures, procurement notices and news
search results are not used as project records or granted licences.

## Record identity, dates and provenance

The works page has fifteen project headings followed by attachment lists, without
pagination in the verified response. Each project is one row, retaining **81 total
links**, including initial/final certificates, project documents, plans, safety
studies and BOP notices. A project is never emitted once per attachment or stage.
The adapter verifies every document link in the content article belongs to a
parsed group and checks official document-host and municipality folder provenance.

Fourteen headings show actual municipal expediente references, used as stable
identities. The social-services office refurbishment heading has no expediente;
its stable identity uses the actual official document folder `19334401`, stored
as `source_dossier_id`, with `expediente: null`. It is not invented as a municipal
reference. The shared entity policy marks this one row `pendiente`; the fourteen
referenced projects are eligible, with policy status `ok`.

Certificate link labels establish initial/definitive phase and explicit agreement
dates. Both stages remain in `eventos`, with direct supporting document URLs.
The definitive stage takes precedence, even when its date is absent: carrer
Girona, caseta de la Guardessa and theatre motorised bars have undated definitive
certificate labels. Their current `fecha_acuerdo` stays null rather than inheriting
an earlier initial-approval date. `fecha_publicacion` and generic `fecha` remain
null throughout. PDF contents and document publication dates are not parsed.
No approval date comes from a filename, crawl time or page-update timestamp.

No verified coordinates or feature geometry were extracted. `lat`, `lon` and
`geometry` are null and `publication_ready` is false. This work does not establish
construction commencement or completion merely from project approval.

## Extraction and validation

Backfill performs one live HTTP request to the exact works inventory URL and
parses its current HTML. Update refreshes that same complete snapshot; it does
not claim an incremental historical feed. HTTP failures, oversized responses,
missing or ambiguous content, pagination, missing project/certificate documents,
foreign provenance, mixed document folders, duplicate identities and unassigned
documents raise errors before output replacement. Responses are streamed with a
4 MB bound and 40-second request timeout. Explicit next links or page parameters
cause failure rather than silent first-page truncation.

Validation used:

```
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_llagostera -v
```

Nine tests passed: grouping and distinct date semantics, undated final approval,
missing expediente identity, multiple independent projects, form/incomplete source
rejection, pagination/orphan/duplicate rejection, provenance checks, manifest
loading with disabled licences, and full-snapshot update delegation.

A real extraction through `load_portal_adapter(load_manifest('llagostera'))`
returned 15 rows and 81 document links. Local, uncommitted evidence is in
`evidence/proyectos.jsonl`, `evidence/validation.json`,
`evidence/live-projectes-obra-municipal.html` and the discovery HTML captures.
The validation records source URLs, limitations and the shared policy result.
Document URLs are retained as provenance; individual PDFs have not all been
fetched or checked. No shared sources, dependencies or Git metadata were changed;
no publication, database access or deployment was performed.
