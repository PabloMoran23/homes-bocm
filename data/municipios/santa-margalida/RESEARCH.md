# Santa Margalida — INE 07055, Illes Balears

Verified live on 2026-11-07 with the preinstalled Python runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
This adapter covers a **partial historical planning inventory**, not all municipal
projects or a register of granted licences. It does not establish the instruments'
current legal validity. Scheduling and coordinate jitter are disabled.

## Official source discovery

The municipal [planning category](https://ajsantamargalida.net/es/taxonomy/term/327)
returns HTTP 200 with seven legacy entries: four external-link entries and three
document folders. The [legacy links inventory](https://ajsantamargalida.net/ca/enllacos/planejament-urbanistic)
returns HTTP 200 but includes old HTTP news URLs and a Dropbox catalogue link.
These are not treated as actual instrument records or followed for extraction.
The municipal sidebar links directly to the current
[official planning transparency folder](https://ajsantamargalida.sedelectronica.es/transparency/42167d6c-2f17-4f87-b936-65b9efc7aa78/).
This folder is anonymously readable, HTTP 200, and contains six document entries
in one HTML table, with no pagination controls in the verified response.

The six preview pages also return HTTP 200, document metadata and an embedded PDF
URL without authentication. The adapter extracts the full folder and visits every
preview. Source previews are stable document identities; embedded PDF delivery
URLs are retained as supplementary links and may change between requests.

| Instrument represented | Official document previews |
| --- | --- |
| Normes Subsidiàries de Santa Margalida de1986 | [Normes](https://ajsantamargalida.sedelectronica.es/preview-document/f559a3c8-65f2-42aa-930f-458d4c92b5f6) |
| Modificació de 2013 de NNSS 1986: construcció piscines | [BOIB document](https://ajsantamargalida.sedelectronica.es/preview-document/5daf45af-75a7-4107-9e42-fa854bedf1a8) |
| Modificació 2014–2015: zonificació esportiva sector 7 | [Initial approval documentation](https://ajsantamargalida.sedelectronica.es/preview-document/8ba3ef40-5567-4035-9258-fec507188c51), [publication edict](https://ajsantamargalida.sedelectronica.es/preview-document/98003572-bd4e-49e2-a3a3-3433078acbe6) |
| Modificació 2016 continued/corrected in 2017: sistema general sanitari-assistencial i aparcaments públics | [Edicte 1](https://ajsantamargalida.sedelectronica.es/preview-document/ca2769fa-a662-4daf-9523-77a3c301906d), [Edicte 2](https://ajsantamargalida.sedelectronica.es/preview-document/b0ce67b7-2170-4464-8717-e7e197036b0c) |

These are actual named planning instruments, not licence applications,
procurement announcements or general news. The inventory itself explicitly says
that the second 2016 edict continues the same modification in 2017 because of an
error, so those two documents remain together. Initial documentation and edict
for the sports zoning modification similarly form one record. The 1986 norms and
2013 amendment are distinct instruments. Original document titles and URLs are
preserved in `documentos`; group identifiers are scraper keys, never invented
municipal expediente numbers.

## Dates, status and limits

Only the pools amendment has an explicitly labelled publication date in its
inventory title: `BOIB 1 08 2013`, parsed as `fecha_publicacion=2013-08-01` with its
source preview URL. This is not an agreement/approval date. All `fecha_acuerdo`,
`fecha_aprob` and generic `fecha` fields are null. Preview metadata says `Data de
creació 14-oct-2020`; that is repository document creation metadata, never used
as a publication or decision date. The current clock displayed by the sede is
also ignored. Years/ranges in titles are not converted to exact dates.

An initial approval label is preserved as `fase_documento` on the document that
actually bears it. Instrument-level `fase` remains null because the latest
procedural state is not established. PDF contents are linked, not parsed to infer
decisions. No claim of definitive approval or present legal validity is made.
No granted-licence inventory was verified; licence methods are disabled and emit
zero rows without network calls. There are no extracted coordinates or geometry;
`lat`, `lon`, `geometry` are null and `publication_ready` is false.

## Implementation and verification

The adapter uses the existing requests/BeautifulSoup dependencies. It parses the
specific transparency table and groups all supported document rows. Unknown
rows, conflicting titles, malformed/external document URLs, an empty or changed
inventory, missing PDF previews, HTTP errors and responses exceeding 4 MB raise
errors before replacing output. Detected pagination (including AJAX controls)
raises an explicit error rather than silently taking page one. If pagination is
introduced, crawler work is required. Backfill and update both refresh the entire
folder; missing dates cannot cause incremental omissions. Preview requests use
40-second timeouts. Output is replaced only after all previews validate.

Validation performed:

- `.../venv/bin/python -m unittest municipio.test_santa_margalida -v`: six tests
  pass. Tests cover grouping, whitespace variation, date semantics, invalid/login
  sources, unknown records, pagination, complete refresh and preserving prior
  output on preview failure, manifest identity and disabled licences.
- Real live extraction through `load_manifest` and `load_portal_adapter`, including
  the shared entity-policy wrapper: **4 records, 6 document links**, seven source
  requests. Policy reports four `unknown` classifications; the shared policy does
  not establish an activity identity from these planning titles. This limitation
  is preserved, not bypassed or replaced by fabricated expediente references.
- `evidence/proyectos.jsonl` contains the real extracted rows;
  `evidence/validation.json` contains count, URLs, limitations and policy report.
  `evidence/captures/` holds all seven source responses under URL-hash filenames;
  discovery and preview captures are also retained locally in `evidence/`.

Evidence is local and is not part of the four source files to commit. No shared
source changes, dependency changes, database access or publication operations
are needed for this adapter.
