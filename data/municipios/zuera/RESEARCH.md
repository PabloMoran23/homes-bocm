# Zuera — Zaragoza — INE 50298

Verified 2026-11-08 using the preinstalled Python 3.12 virtual environment.
This adapter covers the municipal **planning document inventory**, not the entire
municipality's historical planning, public works or granted licences. It is a real
inventory extraction, with seven instruments and 96 distinct document links in the
live snapshot. Scheduling and licence extraction are disabled; missing geometry is
never replaced with a centroid or jitter.

## Official sources discovered

- Municipal urbanism landing page:
  https://www.ayunzuera.com/areas/urbanismo/
  links to Planeamiento, Ordenanzas and urban history. Its news feed is not the
  planning inventory and is excluded by the parser.
- Source actually fetched by the adapter (HTTP 200):
  https://www.ayunzuera.com/areas/urbanismo/planeamiento/
  The current page includes 2026 uploads alongside older plans, so it is treated as
  a presently published inventory, not as evidence that every instrument is legally
  current. Its heading says “Texto refundido 2014”, whereas the norms link names
  May 2023; the adapter preserves the source heading and all versions/corrections.
- https://www.ayunzuera.com/areas/urbanismo/planeamiento/pgou/
  is a related municipal PGOU page discovered through search; it is not a second
  source of records and is not needed to complete the selected inventory.
- https://www.ayunzuera.com/tramites/
  lists applications and administrative forms; it is not evidence of licences
  granted and does not supply records to this adapter.
- Municipality identity independently corroborated by Aragón's official data:
  https://opendata.aragon.es/describe/?url=http%3A%2F%2Fopendata.aragon.es%2Frecurso%2Fsector-publico%2Forganizacion%2Fmunicipio%2F50298
  and the official 2026 territorial valuation table:
  https://www.aragon.es/documents/d/guest/anexo_valoracion_territorial_aso_2026
  (ZUERA, 50298, Zaragoza).

## Inventory and grouping

| Instrument | Documents |
| --- | ---: |
| PGOU, municipal heading “Texto refundido 2014” | 81 |
| PGOU modification 5, supresión ZUA2 | 2 |
| PGOU modification 8, varios objetos | 2 |
| PGOU modification 9, entorno C/ San Juan | 2 |
| Plan Parcial Zuera Sur | 5 |
| Plan Parcial Zuera Sur modification 6 | 2 |
| Plan de Movilidad Urbana Sostenible | 2 |

The PGOU group retains its texts, map sheets, corrections, execution-unit sheets
and linked ZUA7 management agreement as associated documents, rather than creating
an independent project for each attachment. Each modification is a distinct
instrument linked to its parent plan. Every document retains its title, actual URL
and inventory provenance (`url_origen`). Stable record IDs use instrument identity,
not attachment order or mutable PDF URLs. No standalone records are invented for
the empty Estudios de detalle and Planes especiales headings.

The page is a single non-paginated inventory. Every PDF between the PGOU heading
and Noticias Urbanismo is accounted for. There is no row limit or pagination slice.
Detected pagination causes an explicit error. Documents under an unrecognized
heading, unknown document hosts, empty groups, a missing content boundary or a login
page also fail explicitly. Newly added instruments with supported headings are
parsed dynamically; changed layouts require review. Updates refresh the full snapshot;
`state_path` is deliberately not a date cursor.

## Dates and document checks

Four agreement PDFs were downloaded directly during research (HTTP 200), captured
locally and inspected using the already installed `pdftotext`:

- `acuerdo-0.pdf`: PGOU modification 5. Inventory label says `(18072021)`;
  the document says the CPUZ session was **18 June 2021**, and its municipal entry
  stamp is 23 August 2021. Neither date is inferred from its upload path.
- `acuerdo-1.pdf`: modification 8. Document identifies a CPUZ session on
  **10 May 2023**. That session's compliance decision is not automatically equated
  with every earlier approval discussed in the document.
- `acuerdo-2.pdf`: modification 9. Again the label says `(18072021)` but the
  PDF states **18 June 2021**; an entry stamp is a separate event.
- `acuerdo-3.pdf`: modification 6 of Zuera Sur. BOPZ no. 90, page 110, dated
  **22 April 2023**, reports a Pleno approval agreement of **13 April 2023**.
  The label “ACUERDO ... (22042023)” therefore names the publication date.

These checks demonstrate why link-label dates cannot be normalized blindly.
The adapter inventories HTML, not PDF contents; `fecha`, `fecha_publicacion`,
`fecha_acuerdo`, `fecha_aprob` and `fase` remain null in every automated record.
Labels are retained verbatim in `documentos`. The manually observed PDF dates above
are research findings, not hardcoded dates in the scraper. There is no invented
approval status or project geometry.

## Limits and validation

The inventory is partial: no claims of exhaustive historical amendments, regional
register coverage, procurement coverage or a complete public-works inventory.
Embedded corrections are retained as documents rather than consolidated into a new
legal text. Only four representative agreements were downloaded; all 96 URLs are
retained, but all PDF endpoints are not individually validated by the adapter.
There is no verified geometry, so `publication_ready` is false. The shared registry
annotation reports all seven entities as category `unknown`; the adapter does not
alter shared classification policy or treat that annotation as publication approval.

Validation commands used the exact runtime:

```text
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_zuera -v
```

Seven parser/contract tests passed: grouping and parentage, duplicate documents,
publication/agreement ambiguity, stable IDs, pagination rejection, changed/empty
sources, external document rejection and disabled licences. Live extraction used
`load_manifest('zuera')`, `load_portal_adapter(...)`, then `backfill_proyectos(...)`,
including the shared registry's entity annotation. It returned 7 records / 96 links.
Initial Python requests had transient connection closures; subsequent browser-agent
requests succeeded. The adapter uses bounded retries, timeouts and a 3 MB response
limit; a failure cannot silently return empty success or overwrite prior output.

Local uncommitted evidence in `evidence/`: `proyectos.jsonl`, `validation.json`,
`planeamiento.html`, four agreement PDFs and their extracted text. The adapter's
optional `capture_dir` enables exact HTML capture without writing into the source
folders. No credentials, external workspace contents, database, deployment, publish,
push or repository mutation was used.
