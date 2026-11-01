# Pineda de Mar — investigación portal ayuntamiento

Municipio: **Pineda de Mar** (`pineda-de-mar`) — Barcelona, Catalunya. INE `08175`.

## URLs base y semillas

| Recurso | URL | Notas |
|---------|-----|--------|
| Web municipal (Plone) | https://www.pinedademar.cat | Urbanisme, planejament, tràmits |
| Urbanisme | https://www.pinedademar.cat/serveis/urbanisme | Minisite |
| Planejament vigent | https://www.pinedademar.cat/serveis/urbanisme/plantejament-i-gestio-urbanistica-vigent | PDFs PGMO, planols, fitxes tècniques |
| Llicències (info) | https://www.pinedademar.cat/serveis/urbanisme/llicencies-dobres-activitats-i-ocupacions-de-via-publica | Enllaços tràmits (SIAC legacy en enllaços) |
| Seu electrònica (eAdmin) | https://seu.pinedademar.cat/eAdmin/ | Tablón Tablon.do, tràmits Registrar.do |
| Tablón anuncios | https://seu.pinedademar.cat/eAdmin/Tablon.do?action=verAnuncios | HTML per grups; detall `verAnuncio&id=` |
| Geoportal (enllaç web) | https://sig2.pinedademar.org/pinedagis/visor/geoportal | Enllaç des de Plone |
| SIAC antic | https://seu.pinedademar.org/siac/ | Migrat a seu.pinedademar.cat (oct 2026); `.org` no respon des de cloud |
| GestDoc | https://gestdoc.pinedademar.cat/ | Consulta expedients amb credencials |

## Listado de expedientes / proyectos

- **Tablón eAdmin:** taules dins `toggle` per tipus d'anunci. Grup *Actes de publicació preceptiva d'Urbanisme, Llicències i disciplina…* amb títol, període i enllaç `Tablon.do?action=verAnuncio&id=<hex>`. Document PDF via `abrirOriginal('…')`.
- **Plone planejament:** PDFs estàtics (PGMO, planols zones/sistemes, fitxes tècniques FT-01…).
- **GestDoc / carpeta ciutadana:** sense accés públic batch.

## Licencias de obra

- No hi ha registre obert de concessions (només tràmits telemàtics i taxa fiscal n.8 publicada al tabló).
- Pàgines informatives Plone + seu eAdmin; edictes de llicències al tabló quan es publiquen.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Geoportal municipal `sig2.pinedademar.org/pinedagis/visor/geoportal` (enllaç des de https://www.pinedademar.cat/adreces-i-planol/geoportal-urbanistic-1).
  - Metadades IDE «planol-pineda-mar» (https://catalegs.ide.cat/geonetwork/api/records/planol-pineda-mar) — plànol informatiu, EPSG:3857, sense enllaç a expedient.
  - Mapa Urbanístic de Catalunya (territori.gencat.cat) — consulta per punt, no per codi d'expedient municipal.
- **Estrategia:** sense MapServer/FeatureServer REST estable ni WFS per àmbit d'expedient; l'adapter no omple `geom_geojson`. Orquestrador: `centroid` manifest + jitter.
- **Limitaciones:** Host `sig2.pinedademar.org` retorna 404 des de l'entorn cloud de l'agent; PDFs del tabló sense georeferència; SIAC legacy inaccessible.

## Limitaciones generales

- Codificació ISO-8859-1 al tabló eAdmin.
- `bocm_count: 0` (sense boletí regional associat a la cua).
- Sync Supabase requereix `SUPABASE_DB_URL` a l'entorn d'execució.
