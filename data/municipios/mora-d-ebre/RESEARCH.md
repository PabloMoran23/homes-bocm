# Móra d'Ebre — INE 43093, Tarragona

Verified on 2026-11-09. One adapter extracts the municipal **Modificació Normes
Subsidiàries** inventory. Live result: **2 planning instruments**, with 4 document
links grouped under their respective instruments. This is partial municipal
coverage, not a licence register or an exhaustive RPUC history. Scheduling and
coordinate jitter are disabled. No coordinates or geometry are inferred.

## Official source discovery

- Municipal urbanism service and navigation:
  https://www.moradebre.cat/serveis/urbanisme-i-patrimoni/ — live HTTP 200.
  Links to NNSS, their modifications, planning and licence procedures.
- Selected inventory:
  https://www.moradebre.cat/serveis/urbanisme-i-patrimoni/modificacio-normes-subsidiaries/
  — live HTTP 200 with a browser User-Agent. Initial requests with the default
  requests User-Agent returned 403. Two accordion panels, no pagination. Adapter
  parses every panel and fails on unexpected panels, absent documents or new
  pagination. No first-page or date cutoff is applied.
- https://www.moradebre.cat/serveis/urbanisme-i-patrimoni/normes-subsidaries-i-de-plantejament/
  — resolves to the RPUC application shell, not an HTML instrument inventory.
- The municipal planning navigation also points to an old RPUC dossier URL
  (`codintExp=242541`). Navigation alone is not emitted as an instrument.
- Transparency planning page:
  https://seu-e.cat/ca/web/moradebre/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  — live HTTP 200, delegates to RPUC; no individual records in its HTML.
- https://www.moradebre.cat/ajuntament/notificacions/exposicio-publica/
  — live HTTP 200; mixed inventory of concessions, public-information documents,
  agreements and other notices. Not included in the selected coverage. In
  particular, concessions/procurement for bars are not building licences.
- https://www.moradebre.cat/serveis/urbanisme-i-patrimoni/tramits-i-llicencies/
  — navigation identifies procedures, not a register of grants; direct follow-up
  encountered a connection reset. No claim of granted-licence coverage.

## Extracted instruments and document provenance

1. Modification of NNSS for various municipal systems. The index explicitly says
   approved by the Pleno on **2026-04-30**. `fecha_acuerdo` and `fecha_aprob` carry
   this date; publication date stays null. All three linked documents are retained:
   - https://www.moradebre.cat/wp-content/uploads/MPNNSS-Diversos-sistemes-municipals-Abril-2026_anonim.diligenciat.pdf
   - https://www.moradebre.cat/wp-content/uploads/Certificat_acord_plenari.pdf
   - https://www.moradebre.cat/wp-content/uploads/Anunci.pdf
   The latter two were fetched live as PDFs (HTTP 200) and locally inspected with
   `pdftotext`. The certificate identifies expediente **86/2026**, an **initial**
   approval, and the same session date. Its May signature dates are not publication
   dates. The adapter deliberately extracts only index metadata, so the phase and
   expediente remain unset in the output rather than hard-coding PDF observations.
2. Modification of NNSS sector 19. The heading explicitly identifies **initial
   approval** and references November 2025, without an exact day. Its document:
   http://eseu.moradebre.cat/EXPOSICIÓ%20PÚBLICA/03112025ModifNNSSsector19.pdf
   — live HTTP 200, PDF, approximately 12.5 MB. The filename is never parsed as an
   approval date. Local text inspection distinguishes the agreement of 2025-10-30
   from the BOPT publication of 2025-11-03 (CVE 2025-09964). The adapter does not
   parse PDF contents, so both exact dates remain null in its index-only record;
   the original month reference and PDF link remain available.

No claim is made that either modification is definitively approved or is current
consolidated law. These are real published planning instruments at the stages
evidenced by their municipal listing and documents, not procurement announcements
or generic forms. Physical scopes occur in the documents, but no verified vector
geometry is exposed in the index. `lat`, `lon`, `geometry` are null and
`publication_ready` is false.

## Implementation and validation

Uses existing requests and BeautifulSoup dependencies. Registry-compatible
`MoraDEbreAyuntamientoAdapter` implements all four portal methods. Updates refresh
the complete selected inventory. Licence methods write no records and explicitly
return disabled. Writes replace the output atomically after successful parsing.
Identities derive from normalized instrument titles excluding parenthetical date
references. Duplicate panels merge their document links; conflicting phases/dates
raise an error. Renaming an instrument can change its ID; a future cross-inventory
RPUC/expediente reconciliation is outside this coverage.

Validation command (preinstalled runtime, no installation):

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_mora_d_ebre -v
```

Six tests pass: document grouping, distinct date semantics and missing dates,
stable identity across month references, rejection of forms/news/empty content,
pagination detection, invalid dates, manifest/registry integration, disabled
licences and complete-snapshot updates.

Real extraction used `load_manifest('mora-d-ebre')`, `load_portal_adapter(...)`,
then `backfill_proyectos(evidence/proyectos.jsonl)` with `evidence_dir` configured
locally. Result: 2 records. The shared entity policy conservatively marks both
`pendiente/insufficient_identity_evidence`, because the index lacks a numeric
expediente in its extracted metadata. This limitation is disclosed, not overridden.

Local evidence includes `proyectos.jsonl`, `validation.json`, the captured source
HTML, source checks, certificate/notice PDFs and local text extracts. These files
are not source changes and must not be committed. No shared code, dependencies,
credentials, database, deployment or Git mutation is needed for this adapter.
