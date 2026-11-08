# Ripoll — INE 17147, Girona

Verified 2026-11-07. One adapter covers the current municipal works-project
inventory. It does not claim complete municipal planning, historical works or
licence coverage. Scheduling, licence extraction and coordinate jitter are disabled.

## Discovery and selected source

- https://ripoll.cat/servei-durbanisme/ — official municipal urbanism landing
  page. Identifies the works inventory as projects approved or under approval,
  and separately links POUM, rural-building catalogue and online procedures.
- https://ripoll.cat/projectes-obres/ — selected official inventory, HTTP 200 in
  the live adapter run. One static four-column table; 12 project rows and 15 PDF
  links. No pagination on the captured page. All rows are processed; there is no
  record cap. Added pagination causes an explicit failure instead of a partial
  successful extraction.
- https://ripoll.cat/poumripoll/ — additional official planning inventory,
  inspected and captured but outside this adapter's scope. Includes the base
  POUM, consolidated regulations and plans, and links to separate inventories
  of amendments, special plans, urban improvements, reparcelling and specific
  actions. Its documents must not be counted as individual independent projects.
- The urbanism landing page's rural-building catalogue points to
  https://ripoll.cat/wp-content/uploads/2022/09/MOD-CATALEG-MASIES-Refos-2022.pdf
  (large PDF). Not extracted. Online application procedures and general news
  are excluded; they are not evidence of granted licences.

The selected table contains genuine physical works: pavilion water infiltration
repair, biomass heating networks, solar installation, roof replacement,
rehabilitation of municipal buildings and spaces, wildfire protection strips,
and building demolition. Supplemental reports and plans stay attached to the
same table-row project: biomass project 5 has two documents; wildfire project 9
has three. Every document retains its exact source label, source page and URL
(with spaces/non-ASCII URL characters percent-encoded). Document availability
and PDF contents have not been individually verified: these are links attested
by the official inventory, not claims of PDF-content extraction.

## Semantics and limitations

The three source columns are initial approval, public information and definitive
approval. Their original strings are retained in `date_provenance`; ISO dates
are emitted in separate explicitly named fields. `fecha_aprob` is definitive
approval when supplied, otherwise initial approval; stage is explicit. Neither
public-information dates nor PDF upload paths are promoted to publication dates.
`fecha`, `fecha_publicacion` and `fecha_acuerdo` are null. Underlying agreement
texts have not been independently checked. A dash means unknown, never inferred
approval. In particular, projects 3 and 9 have no definitive date, and project 12
only has initial approval. Approval stage does not imply construction completion.

Identity derives from the project title without the display row number; it is
stable across renumbering and document changes. A title change can change identity.
Each update refreshes the entire available inventory. This is not a history of
removed entries. Duplicate identities, malformed dates, changed table structure,
unexpected documents, empty results and pagination fail without replacing output.

The source provides no verified geometry for these records. Coordinates and
geometry remain null; `publication_ready` is false. No centroid or random point
is substituted. This is a usable extraction candidate for independent review,
not authorization to publish.

## Network and reproducibility

The runtime's DNS-selected Cloudflare addresses (188.114.96/97.*) timed out.
The manifest supplies an explicit alternate Cloudflare edge, 104.21.32.1, used
only after direct connection failure. The request remains HTTPS to ripoll.cat:
SNI, HTTP Host and certificate hostname verification remain enabled. The live
result records which edge was used and the preceding connection error. This
routing workaround may need revision if Cloudflare routing changes. There is
no cached-data fallback or TLS-verification bypass.

Run with the preinstalled interpreter:

```
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_ripoll -v
```

Four parser/workflow tests passed: dates and document grouping; stable identity
and definitive approval; rejection of malformed/nonproject/paginated responses;
and manifest loading, full refresh and preserving output on parser failure.

Live extraction used `RipollAyuntamientoAdapter.backfill_proyectos` with the
manifest configuration plus `capture_dir=evidence`. Result: HTTP 200, 12 real
projects, 15 attached document links. Local, uncommitted evidence:

- `evidence/proyectos.jsonl`: all 12 extracted records.
- `evidence/validation.json`: live count, source URL, limitations and transport.
- `evidence/projectes-obres.html`: original live response parsed by the adapter.
- `evidence/servei-durbanisme.html`, `evidence/poumripoll.html`: discovery captures.

Only the four requested source files are added; no shared code or dependencies
were changed. No publication, database, deployment or git mutation was performed.
