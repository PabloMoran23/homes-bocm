# Quatretonda — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `quatretonda` |
| Provincia | Valencia (Comunitat Valenciana) |
| INE municipio | 46214 |
| Boletín | DOGV (`dogv`) |

## URLs base y semillas

| Fuente | URL | Uso |
|--------|-----|-----|
| Web municipal | https://quatretonda.es | WordPress Themify Ultra; noticies i documentació |
| Tabló (web) | https://quatretonda.es/ajuntament/tauler-danuncis/ | Enllaç a seu + anuncis locals |
| Documentació tràmits | https://quatretonda.es/teleadiministracio/documentacio/ | PDFs llicències/obres (formularis) |
| Pla general estructural | https://quatretonda.es/pla-general-estructural-de-quatretonda/ | Notícies i decret adjudicació |
| Seu electrònica | https://quatretonda.sedelectronica.es/board | Tabló espublico gestiona (Wicket) |
| Inici seu | https://quatretonda.sedelectronica.es/info | Extracte tabló + catàleg (si disponible) |
| Mancomunitat | https://portadelavall.sedelectronica.es/info.1 | Porta de la Vall (referència; no ingestat) |
| API WP | https://quatretonda.es/wp-json/wp/v2/posts | Noticies filtrades urbanisme |

## Expedientes / proyectos

- **Tabló espublico**: taula HTML amb `preview-document/{uuid}`; procediment, categoria i data DD/MM/YYYY. Actualment predomina personal/subvencions; entrades d'urbanisme apareixen puntualment.
- **Noticies WP**: posts sobre pla general estructural, camins rurals, rehabilitació casc antic, informes inundabilitat/sísmic, etc.
- **ICV planeamiento**: capes SU/SUZ del municipi amb polígons WGS84.

## Licencias

No hi ha registre públic de concessions de llicència (només edictes puntuals al tabló). Formularis PDF a documentació:

- `SOL·LICITUD-LLICENCIA-OBRES-PER-IMPRIMIR.pdf`
- `solicitudcompatibilidadurbanistica.pdf`
- `declaracioresponsable1aocupacio.pdf`, ocupació, obres menors, etc.

L'adapter ingesta aquests com **tràmits informatius** (`nota` en registre).

## Geometría / visor

- **geometry_status:** `available`
- **Fuentes:**
  - WFS ICV: `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Capa: `ms:InventarioSuSuz`
  - Filtre client: `cod_ine_mun=46214` (el WFS ignora `CQL_FILTER`)
  - Format: GeoJSON `EPSG:4326` (`MultiPolygon` / `Polygon`)
  - Camps: `pp`, `ue`, `clasificacion`, `f_aprob`
- **Estrategia:** descàrrega paginada WFS → files `proyectos.jsonl` amb `geom_geojson`; enriquiment per títol (tokens UE/SECTOR) en noticies/tablon.
- **Limitaciones:** el tabló no enllaça geometria per expedient; visor web municipal sense API pública directa. PDFs sense georeferència.

## Limitaciones generales

- `/dossier` de la seu redirige en bucle (no usable); catàleg via `/info` o PDFs web.
- `curl` sense UA de navegador pot fallar en algunes URLs de la seu; l'adapter usa `insecure_ssl` + cookie jar com altres municipis espublico.
- GVA `mediambient.gva.es` índex de planeament: timeout des de CI; no bloqueja (WFS ICV cobre geometria).

## Patrón adapter

WordPress + espublico (`pelabravo`) + ICV WFS CQL (`onil`/`picassent`).
