# Santa Margarida de Montbui — INE 08250, Barcelona

Verified live on 2026-11-07. This adapter extracts **one real planning instrument**,
its POUM, from the complete document inventory on the dedicated portal linked by
the municipality. Live result: **1 instrument, 31 distinct PDF links**, including
previous stages. Coverage is deliberately partial. This is an initially approved
plan, not a claim that the new POUM is definitively approved or currently in force.
No granted licences, general news, procurement notices or application forms are
emitted. Scheduled execution and missing-coordinate jitter are disabled.

## Source discovery and provenance

- Municipal POUM page, HTTP 200:
  https://www.montbui.cat/lajuntament/informacio-oficial/normativa/urbanisme/pla-dordenacio-urbanistica-municipal-poum
  explicitly directs users to `http://www.poummontbui.com`. The adapter verifies
  this municipal link on each extraction. Its page-update timestamp (2024-04-26)
  is not a plan approval/publication date.
- Dedicated POUM document inventory, HTTP 200:
  https://www.poummontbui.com/documentacio/
  supplies the actual plan volumes, agreement certificates and gazette notices.
  The latest page update is an information-session entry in January 2026; it is
  not a later approval. The initial-approval section reports the municipal plenary
  agreement of **2025-11-27**. A separately linked BOPB notice reports publication
  on **2025-12-12**. There are also July 2025 reports, the 2024 advance-plan
  documents and notices, and preparatory/participation PDFs. All are retained
  within this single instrument, with the source section's update date labelled
  `seccion_actualizacion`, never used as an agreement date.
- Official transparency urbanism inventory, HTTP 200:
  https://seu-e.cat/ca/web/santamargaridademontbui/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme
  links to planning and territorial-plan information. Its planning page,
  https://seu-e.cat/ca/web/santamargaridademontbui/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  links directly to RPUC with `municipiSel=08250`, corroborating municipality
  selection. This is a source pointer, not a set of extracted project records.
- The linked register URL,
  https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=08250
  redirects to
  https://planejamenturbanisme.territori.gencat.cat/rpucportal/index.html#/consulta/cercaPublic?reqCode=cerca&municipiSel=08250
  and returns HTTP 200 with the JavaScript application shell, not dossier rows.
  No RPUC completeness or geometry is claimed. No authentication was attempted.

## Agreement and publication corroboration

These municipal-hosted PDFs were actually downloaded, with copies under local
`evidence/`. The initial agreement and BOPB were also converted to text with the
preinstalled `pdftotext` executable for verification:

- [Initial-approval certificate](https://www.montbui.cat/media/repository/NewFolder/20251128_Certificat_Certificat_d_acords_39_Certificat_d_acord_PLE_ORDINARI_27_11_2025__VALORAR_positivament_i_APROV._INICIAL_POUM_sense_fiscalitzacio__2_.pdf):
  session 27/11/2025, expediente 95/2024, explicitly initial approval. Signature
  dates on the certificate are not the agreement date. The adapter does not
  hardcode the expediente from this manually inspected PDF.
- [BOPB initial-approval notice](https://www.montbui.cat/media/repository/NewFolder/20251212_40.1_PUBLICACIo_BOP_12_12_2025.pdf):
  CVE 202510191433, publication 12/12/2025, explicitly identifies the agreement of
  27 November 2025 and the initially approved POUM. This confirms the inventory's
  two separate dates, rather than deriving dates from PDF filenames.
- [Advance-plan certificate](https://www.montbui.cat/media/repository/20240626_Certificat_Certificat_ple_12_Certificat_d_acords_PLE_20_06_2024_Aprov._Avanc_Planejament_POUM_sense_fiscalitzacio__1_.pdf)
  and [advance-plan BOPB](https://www.montbui.cat/media/repository/PUBLICACIo_BOP_4.7.2024.pdf)
  also return HTTP 200 PDF. They remain attachments of this POUM, not separate
  current approvals or duplicate project rows.

## Extraction rules and limits

The parser requires the article's POUM identity, a unique initial-approval
narrative, a matching date in the certificate-link paragraph, a certificate link,
and actual plan documents. A later definitive-approval narrative, missing identity,
conflicting agreement dates or pagination causes an error requiring review. It
parses the entire single-page inventory without a document-count cap. HTTP errors
and responses above 3 MB fail explicitly before replacing output. Each refresh
writes a complete snapshot atomically; the incremental method uses the same
snapshot, rather than filtering out older attachments.

Every PDF link inside the inventory is grouped by canonical URL and retained in
`documentos` with its title/context, exact original href and inventory provenance.
Two hrefs contain literal TAB characters; the fetchable link removes those TABs.
Municipal HTTP document links use HTTPS, verified with the certificates and BOPB
PDFs. `url_original` preserves the original value. Not every plan-volume PDF has
been downloaded or checked for accessibility. Forms (`.docx`), short links to
appointments/instances and surrounding news/sidebar links are excluded.

`fecha_acuerdo` and `fecha_aprob` refer to the explicit **initial** agreement;
`fecha_publicacion` refers specifically to BOPB. Generic `fecha` remains null.
The descriptive source paragraph is retained. Stable identity is the municipal
POUM instrument, so its many attachments and earlier stages are not individual
projects. No instrument geometry was extracted from map PDFs or RPUC; `lat`,
`lon` and `geometry` remain null, `publication_ready` false. The shared entity
policy currently annotates POUM as unknown; this does not expand coverage or
supply geometry. Other instruments, public works and licence grants require
additional verified sources and are outside this adapter's coverage.

## Validation and local evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_santa_margarida_de_montbui -v`: 5 tests pass,
  covering date semantics, grouping/deduplication across stages, original/corrected
  URLs, excluded forms, absent publication dates, invalid/changed inventories,
  pagination rejection, manifest loading, snapshot refresh and preservation of
  existing output on source failure.
- Real live `backfill_proyectos` through `load_portal_adapter(load_manifest(...))`:
  status `ok`, 1 instrument, 31 linked documents. No fixture data used for output.
- Local `evidence/proyectos.jsonl` contains the actual record;
  `evidence/validation.json` records count, source URLs, tests and limitations.
  HTML source captures, initial and advance-stage certificate/BOPB PDFs and the
  initial-stage text extractions provide inspection evidence. Evidence is local
  and is not part of the four source files.
