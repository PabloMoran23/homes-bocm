# La Garriga — INE 08088, Barcelona

Verified live on 2026-11-07 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
This adapter extracts **22 real instrument entries with 92 document links** from
two public municipal planning inventories. Coverage is partial, schedules and
licences are disabled, and `publication_ready` is false because there is no
verified project geometry. This is not a register of granted licences.

## Source discovery

The canonical municipal Urbanisme index returned HTTP 200 and links to the two
planning inventories, the separate works inventory and POUM documentation:

- https://www.lagarriga.cat/ajuntament-seu-electronica/informacio-oficial/2181-urbanisme
- https://www.lagarriga.cat/ajuntament-seu-electronica/informacio-oficial/2181-urbanisme/planejament-i-gestio-urbanistica-en-tramit
  — HTTP 200; seven named groups in a complete HTML table, five supported
  instruments after excluding compensation-board statutes/administrative groups.
  Includes the A11 PGOM amendment, Can Luna frontage urbanisation, UA6
  reparcelling, UA6 urbanisation and La Sorrera Bike Park planning project.
- https://www.lagarriga.cat/ajuntament-seu-electronica/informacio-oficial/2181-urbanisme/planejament-i-gestio-urbanistica-aprovada-definitivament
  — HTTP 200; twenty named groups in a complete HTML table, seventeen supported
  instruments after excluding three compensation-board groups. Includes B5/B3/B4
  amendments, the funeral-home special plan, the heritage plan, Radio Silenci at
  Can Luna, UA3 reparcelling/urbanisation/detail study, Moranta 27, and UA33.
- https://www.lagarriga.cat/ajuntament-seu-electronica/informacio-oficial/2181-urbanisme/projectes-dobres
  — HTTP 200, 26 links to works-detail pages. Discovered and captured but outside
  this adapter's planning-table coverage. These are not silently reported as
  extracted works. In particular, there are similar PCA1 Calàbria titles whose
  detailed documents would need reconciliation before expanding coverage.
- https://www.lagarriga.cat/ajuntament-seu-electronica/informacio-oficial/2181-urbanisme/poum/
  — HTTP 200, separate POUM documentation, outside the selected tables.
- https://lagarriga.ecityclic.com/ajuntament/informacio-municipal/planejament-urbanistic/planejament-i-gestio-urbanistica-en-tramit
  — HTTP 200, a municipal-branded alternate host found by search. Its inventory
  differs: it includes additional entries, notably initial approval of a new POUM
  with a certificate label dated 24-09-2025. No canonical linkage to this host was
  verified in this run. Its HTML is retained as discovery evidence, not combined
  with the canonical site's records. Thus the adapter does not claim to cover the
  new POUM or every instrument visible on alternate municipal hosts.

No usable public granted-licence inventory was verified. Forms, procurement
announcements, news and compensation-board statutes are not licence/project
records. Planning of private developments is included as planning, not asserted
to be physical public works or granted building licences.

## Grouping, provenance and date semantics

Each nonempty first table cell opens an instrument group; subsequent blank title
cells append documents to that group. Every distinct document URL and its source
label are retained, including certificates, notices, plans, reports and earlier
procedural stages. The source's heritage-plan bundle also contains a link to a
related amendment: this remains a labelled related document, not a claim that
all links describe the same approval event. Reparcelling and urbanisation for the
same UA are separate instruments. IDs derive from normalized published titles,
not row position or crawl date; source title changes can change IDs.

The canonical tables currently have no overlapping supported headings or
document URLs. Duplicates across groups trigger an error for reconciliation
instead of being overwritten or emitted twice. The source `inventario_fuente`
preserves its category. Only an explicit approval phrase in the instrument title
sets `fase`; neither the category nor `tipo` supplies a phase. For example, the
A3.1 title says initial approval despite appearing in the definitive inventory.
The inventory is evidence of publication, not proof of current legal validity.

Explicit publication labels such as `Publicació BOPB 05-12-2024` are parsed into
the corresponding document's `fecha_publicacion`. Instrument-level
`fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` and generic `fecha` remain
null: a bundle may contain several distinct publication/approval events. Dates
in filenames, page-update timestamps and certificates of earlier stages are not
promoted to instrument approval dates. PDF bodies are not parsed. This leaves
some dates unknown even when a human could recover them from an attachment.

Source links are retained exactly after resolving relative URLs. This includes
legacy HTTP RPUC links and a few published paths without conventional `.pdf`
suffixes. Their validity is not inferred or repaired. Independent checks of the
funeral-home edict and UA3 reparcelling edict returned HTTP 200 and genuine PDF
signatures; both are captured locally. The other 90 targets have not all been
downloaded or validated. No parcel, centroid, coordinates or geometry are
invented; `lat`, `lon` and `geometry` remain null and jitter is disabled.

## Fetching and validation

Both selected inventories are fetched completely with no record cap. The adapter
requires the expected heading and table shape, rejects orphan documents, missing
links and empty supported inventories, and fails if pagination appears. HTTP
requests have connect/read timeouts and a 3 MB decompressed response limit;
oversized responses fail rather than truncate. Updates refresh the complete
two-page snapshot. Output is replaced atomically only after both inventories
parse and overlap checks succeed; the state argument does not represent a
historical change feed.

`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_la_garriga -v`
passed six tests: document grouping/date provenance, category versus phase,
administrative/form exclusion, pagination and invalid-content rejection, stable
IDs/link preservation, and manifest loading with preservation of existing output
on a failed fetch. The adapter's actual `backfill_proyectos` then returned
`status=ok`, 22 records (5 in trámite, 17 in the definitive-category inventory),
92 document links and no coordinates or inferred approval dates.

Local, uncommitted evidence under `evidence/` contains `proyectos.jsonl`,
`validation.json` (live count, source URLs, limitations, checks and HTML hashes),
the exact adapter-fetched source HTML, discovery captures and two PDF samples.
Only this municipality's four source files are added. No shared modules,
dependencies, credentials, databases, deployment or publishing tools are used.
