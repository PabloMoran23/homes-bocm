# Valga — Pontevedra — INE 36056

Verified on 2026-11-09 using the preinstalled Python 3.12 runtime at
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
This adapter covers Valga-named planning instruments in the Xunta's current
strategic environmental assessment (AAE) running-plan inventory. It does not
claim a complete municipal planning history or a granted-licence register.

## Official source discovery

- Municipal Urbanismo page:
  https://www.valga.gal/departamentos/urbanismo-e-medio-ambiente/urbanismo
  responds HTTP 200. It describes office functions and classes of works and
  licences, without individual project records. These service descriptions are
  excluded.
- Municipal electronic headquarters: https://valga.sedelectronica.gal/.
  Public home HTML lists SL-001 licence applications and CP prior-communication
  forms, and links to the notice board, transparency and procurement portals.
  These forms do not prove any granted licence. Exploratory retrieval required
  disabling TLS verification on that host; it is not a trusted extraction source
  for this adapter. No authenticated expediente access was attempted.
- Current official AAE inventory: https://medioambiente.xunta.gal/en-curso.
  The entire unpaginated HTML table is read, not just recent results. Matching
  titles must contain the word Valga and describe a plan/PXOM. Every matching
  instrument is followed to its official detail page and checked against its
  inventory title and code. Municipality-specific titles without the word Valga
  are outside this matching strategy.
- A historical municipal planning PDF was also discovered:
  https://valga.gal/images/Mercedes/MODIFICACION_PUNTUAL_N%C2%BA_3_DO_PXOM_DE_VALGA_NA_NORMATIVA.pdf.
  It is not incorporated into the running-inventory snapshot. The adapter does
  not mix historical plan versions or infer their present legal force.
- Procurement and general news are not used as granted licences or projects.

## Live results and provenance

Two genuine planning instruments were extracted, with nine attached document
links grouped into two records:

1. `2312/2020`, expediente `2020AAE2452`: Plan especial de infraestruturas e
   dotacións para o desenvolvemento do SX-SU03 do PXOM, Valga. Six documents:
   consultation document, draft, environmental document, environmental report,
   DOG publication of that report and scoping document. Consultation dates are
   2020-05-04 to 2020-07-06. The promoter field is empty in the source and remains
   null. Municipal association comes from the inventory and detail title.
2. `2886/2026`, expediente `2026AAE3144`: MP nº5 do Plan xeral de ordenación
   municipal no núcleo rural da Gándara, Valga. Three documents: consultation
   document, draft-plan ZIP and strategic environmental document. Source
   promoter is Concello de Valga. Consultation dates are 2026-10-23 to 2026-12-04.

Exact detail and document URLs are preserved in `evidence/proyectos.jsonl` and
`evidence/validation.json`; they are taken from the inventory and detail links.
The record identity uses the actual AAE expediente. Documents retain their own
titles, source-displayed dates and detail-page provenance; they are not emitted
as separate projects. Document dates are labelled `fecha_fuente`, because the
page does not establish whether each is a document date or upload date.

Both fichas report `En curso`. This is preserved as the source's environmental
assessment registry status, including the older 2020 dossier. It is not evidence
that a plan is approved, construction is underway, or the 2020 consultation is
still open. No plan approval or agreement date is exposed in the parsed fields.
`fecha`, `fecha_publicacion`, `fecha_acuerdo` and `fecha_aprob` remain null.
The DOG publication date on an attached environmental report is not promoted to
a publication or approval date of the planning instrument.

## Retrieval and coverage limits

Requests use verified HTTPS, 40-second timeouts and a 5 MB HTML/issuer response
limit. Xunta currently omits its intermediate certificate, causing standard TLS
validation to fail. The adapter fetches the public GlobalSign RSA OV SSL CA 2018
intermediate from
https://secure.globalsign.com/cacert/gsrsaovsslca2018.crt over verified HTTPS,
then adds it to a default trust context. Root-chain and hostname verification
remain enabled. The adapter never uses `verify=False` or an unverified context.

The current inventory has no pagination. Detected pagination controls cause an
explicit error for crawler review. Missing tables, changed fields, absent
documents, mismatched detail identities and unexpected document hosts fail the
snapshot. A completed snapshot replaces the output atomically; failures retain
the previous output. Incremental updates refresh this same complete inventory
snapshot. There is no fixed record limit or first-page truncation.

Coverage excludes completed AAE cases, other official planning registers,
municipal physical works and granted licences. AAE is an environmental procedure,
not a licence-granting inventory. Source documents are linked, but their PDF/ZIP
contents and geometry are not parsed. No coordinates, parcel centroids or
municipal centroid are substituted. Geometry and latitude/longitude remain null,
and `publication_ready` is false. Scheduling, licence extraction and missing-point
jitter are disabled in the manifest. The manifest uses the repository's
`ayuntamiento` project-pipeline selector; each extracted record explicitly marks
the actual publishing source as `xunta`.

## Validation and local evidence

- `python -m unittest municipio.test_valga -v`: eight tests passed. They check
  document grouping and date semantics, municipality filtering, deduplication,
  pagination rejection, form/login rejection, document identity and host checks,
  failed-refresh preservation and manifest guards. Fixtures do not need network
  access or local evidence files.
- Direct live `ValgaAyuntamientoAdapter.backfill_proyectos` invocation using the
  manifest: status `ok`, two records and nine document links.
- `evidence/proyectos.jsonl`: actual extracted records.
- `evidence/validation.json`: count, exact source URLs, limitations and document
  reachability results. Document checks sample headers and initial bytes, rather
  than downloading all large files; this is stated explicitly in the evidence.
- `evidence/en-curso.html`, `plan-2312.html`, `plan-2886.html` and the public CA
  certificate are captured by the live adapter. `2020AAE2452-1.pdf` is a complete
  consultation-document capture. Other large document contents are not captured
  in full. `sede.html` is an exploratory, TLS-unverified capture, not extracted
  project evidence.

Evidence is local and excluded from the source changes. No shared source files,
dependencies, credentials, database, deployment or publishing operations are
needed for this adapter.
