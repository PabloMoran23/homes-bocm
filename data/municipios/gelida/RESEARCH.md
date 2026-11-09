# Gelida — INE 08091, Barcelona, Catalunya

Verified live on 2026-11-08 using the preinstalled batch virtual environment.
This adapter covers **13 planning instruments**, with **58 document links** grouped
under their municipal instrument fiches. It is a partial municipal snapshot, not
an inventory of granted licences or all physical works, and not a determination
of which plans remain legally in force. Scheduling and coordinate jitter are off.

## Official inventory and scope

- [Municipal planning and project inventory](https://www.gelida.cat/ajuntament/urbanisme-i-territori/planejament-urbanistic-i-projectes):
  HTTP 200, five pages. The live adapter traverses every linked pagination page,
  including `?pag=2` through `?pag=5`, before fetching selected instrument fiches.
  All 67 inventory entries were inspected during discovery. The inventory also
  contains works projects, conventions, statutes, inventories and other studies.
- [Urbanism and territory](https://www.gelida.cat/ajuntament/urbanisme-i-territori)
  identifies the municipal inventory. The separate urbanism topic page mixes news,
  procedures and documents and is not used as a project register.
- The inventory links the official RPUC municipal query with `municipiSel=08091`.
  RPUC is a further source of planning dossiers; this implementation does not
  extract that register or claim complete municipal planning history.

Scope is the base POUM, POUM/PGOM modifications, special plans and partial plans
identified by their inventory titles. Works and reparcellation projects, statutes,
conventions, studies and commissioning/redaction announcements are excluded.
AGROPARC's POUM modification is a planning instrument even though its title also
mentions the underlying project. No licence application or procurement notice is
converted into a granted licence or project. Source title spelling is retained.

## Documents, identity and dates

A municipal fiche is the instrument identity, hashed from its canonical URL.
The scraper groups all document-panel attachments and official municipal OAC
links in the fiche body into `documentos`, deduplicated by target URL. Each link
retains its title, fiche provenance and original hyperlink. Outlook Safe Links
are decoded to the municipal target while preserving the original URL. This
produces one record for the renewable-energy modification with its 19 documents,
not 19 instruments. Municipal PDFs are linked rather than downloaded or parsed;
attachment availability and the contents of large PDF files have not been audited.

The base [POUM fiche](https://www.gelida.cat/ajuntament/urbanisme-i-territori/planejament-urbanistic-i-projectes/poum.html)
provides an explicit approval date of 2015-01-29 and DOGC publication date of
2015-06-05. These are separate from its municipal fiche publication date of
2015-02-12. The fiche has no downloadable document links in its current HTML;
it remains a genuine named instrument supported by the explicit approval narrative.
Its generic RPUC and Adobe Reader links are not plan documents.

All municipal publication dates come from the inventory's `.date` field.
Filename/title prefixes and page-update dates are never used as agreement or
approval dates. Other approval dates and agreement dates remain null. Their
source titles and document captions retain the published approval wording, but
phases are not normalized: in particular, modification 2 has provisional approval
in its title and initial approval in its introductory text. No precedence between
those claims is invented. The base POUM alone has a normalized definitive phase
supported by its narrative. No inferred coordinates or municipal centroids are
provided; geometry is null and `publication_ready` is false.

## Robustness and validation

Pagination is discovered rather than fixed at five pages. The number of visited
pages must match the site's reported total. Repeated page contents, conflicting
duplicate dates, unexpected URLs, missing headings, empty inventories, missing
documents for non-base plans, and changed POUM date narratives fail extraction.
A safety bound of 100 pages raises an error rather than truncating output.
HTTP requests have timeouts and a 5 MB response limit. All detail requests must
succeed before the JSONL snapshot replaces an existing output. Updates refresh
the full snapshot; they do not append duplicate instruments.

Validation command:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_gelida -v
```

Six tests cover dates, grouped attachments, exclusions, schema/markup failures,
full pagination, ignored/incomplete pagination, atomic output preservation and
manifest identity. A real `GelidaAyuntamientoAdapter.backfill_proyectos` run
returned 13 records from all five inventory pages. Local, uncommitted evidence
contains `proyectos.jsonl`, `validation.json`, discovery HTML and the live
adapter's HTML captures. No shared code or dependencies were changed.
