# El Casar — Guadalajara — INE 19071

Verified live on 2026-11-07 using the preinstalled Python runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
This adapter covers the current municipal planning-document inventory only.
It does not claim complete coverage of projects, public works or granted licences.

## Official source and document provenance

The current [municipal Urbanismo inventory](https://elcasar.es/areas-municipales/urbanismo)
returns HTTP 200 and explicitly identifies the **PLAN DE ORDENACIÓN MUNICIPAL
VIGENTE EL CASAR**. Its `.cuerpoInterior` contains the actual documents rather
than application forms or procurement notices. The live inventory has 75 PDF
links and no pagination controls. All 75 links are retained, without a row limit:

- One POM record with 74 documents: memory, urban rules, protected-property and
  public-residential-land catalogues, environmental and hydrological studies,
  information and ordering plans. These are components of the same instrument,
  not 74 different projects. Mesones plans belong to this municipal POM.
- One modification n.º 1 record with its own PDF. The adjacent municipal text
  identifies **BOP de Guadalajara de 23 de julio de 2014**, parsed as
  `fecha_publicacion=2014-07-23`, never as approval or agreement date.

The [POM memory PDF](https://elcasar.es/media/ze0brx52/documento-i-memoria_ad.pdf)
was downloaded successfully (HTTP 200, application/pdf, 11,261,340 bytes).
The first two pages were captured as text; the large PDF was then removed from
local evidence because workspace disk space was exhausted. No unrelated files
were removed.

The [modification PDF](https://elcasar.es/media/onnjjco5/modificaci%C3%B3n-n%C2%BA-1-del-plan-de-ordenaci%C3%B3n-municipal-de-el-casar.pdf)
was downloaded successfully (HTTP 200, application/pdf, 654,212 bytes) and is
retained locally. Its first page reproduces a provincial bulletin announcement
with the date 23 July 2014 and refers to definitive approval and a DOCM
publication of 1 July 2014. Its print footer has a separate 2018 date; that is
not used as the instrument date. The parser does not extract dates or phase from
PDF content, so the modification's approval date and phase remain null.
The dates of these two bulletin publications are not interchangeable.

The inventory also contains an interpretation of POM roofing provisions,
explicitly labelled **Acuerdo del Pleno 30/03/2016**. This is retained with its
verbatim description, source URL and `fecha_acuerdo=2016-03-30` in
`acuerdos_vinculados` on the POM record. It is not a third project and does not
supply the approval date of either instrument. No page update time, document
filename year or crawl timestamp is used as a planning decision date.

## Extraction behavior and limits

The adapter implements the existing `AyuntamientoAdapter` interface and loads
through the registry using the municipality-specific manifest. Both project
methods refresh the complete single-page snapshot. No state cursor or date
filter excludes old instruments. Licences return an explicitly disabled empty
result; no granted-licence inventory was established by this investigation.

Grouping uses the municipal heading and numbered modification sections. Each
instrument has a stable identifier derived from its source URL and instrument
key, independent of document count or ordering. Document titles, absolute links,
and inventory provenance are retained. Duplicate document links within an
instrument are collapsed. The parser rejects missing POM core documents,
unrecognized modification links, duplicate instrument sections, unexpected link
origins, changed nested document layouts and pagination controls. Those cases
require review instead of returning a silently incomplete snapshot. HTTP errors,
redirects away from the municipal host and responses over 5 MB also fail.
Output is replaced only after successful extraction and parsing.

This is a narrow inventory, not a search across all municipal news, the electronic
noticeboard, procurement, the regional register or the provincial bulletin.
Only two selected PDFs were fetched to check provenance; the other 73 document
URLs were retained from the live official inventory but not individually fetched
or parsed. Link retention is not a guarantee that every PDF is currently readable.
No project coordinates or vector geometry were verified. `lat`, `lon`, `geometry`
and unverified approval dates remain null; `publication_ready=false`.
The manifest sets `schedule.enabled=false`, `geocode.jitter_missing=false` and
`licencias.enabled=false` and identifies El Casar, Guadalajara, INE 19071.

## Validation and local evidence

- `python -m unittest municipio.test_el_casar -v`: 10 offline tests passed.
  They check date semantics, document grouping and deduplication, 130 additional
  plan documents without truncation, stable identity, rejection of forms/login
  pages, pagination, unexpected origins, duplicate instruments, changed nesting,
  absent publication dates, disabled licences and full-snapshot updates.
- Live `load_portal_adapter(load_manifest('el-casar')).backfill_proyectos(...)`:
  status `ok`, **2 real instruments, 75 document links (74 + 1)**. Assertions compare
  the output document count with every link in the captured live inventory and
  check separate date meanings and missing coordinates.
- `evidence/proyectos.jsonl`: actual registry-loaded adapter output, including
  shared entity-policy annotations.
- `evidence/validation.json`: live record count, source URLs, limitations, runtime,
  capture provenance, inventory SHA-256 and test result.
- `evidence/urbanismo.html`, `evidence/modificacion.pdf`,
  `evidence/memoria-primeras-paginas.txt`, `evidence/tests.txt`: local captures.

Evidence is local and is not part of the four source files. No credentials,
databases, deployment tools, publishing or repository writes to `.git` were used.
