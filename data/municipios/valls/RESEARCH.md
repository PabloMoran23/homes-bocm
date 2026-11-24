# Valls — investigación portal ayuntamiento

Municipio: **Valls** (`valls`), Tarragona, Catalunya. INE **43161**. idEns e-TAULER **4316130008**.

## Fuentes

| Canal | URL | Contenido |
|-------|-----|-----------|
| Web municipal | https://www.valls.cat | Joomla: Territori → Planejament / Urbanisme |
| Seu electrònica (Drupal) | https://seu.valls.cat | Tràmits per ordre alfabètic, instàncies PDF, enllaç e-TAULER |
| Transparència (seu-e / Liferay) | https://seu-e.cat/ca/web/valls | Urbanisme, planejament, info geogràfica |
| e-TAULER | https://tauler.seu.cat/inici.do?idens=4316130008 | Edictes i anuncis (SPA React; sense API HTML estable) |
| GeoValls POUM | https://geo.valls.cat/vallsgp/ | Visor Angular/OpenLayers del POUM |
| GeoServer | https://geo.valls.cat/geoserver/wms | WMS/WFS públic (capas `valls:*`) |
| RPUC Gencat | https://dtes.gencat.cat/rpucportal/...&municipiSel=43161 | Expedients planejament registrats |
| Tràmits en línia | https://tramits.valls.cat/impulsa/ | Impulsa — llicències amb certificat |

## Proyectos / planeamiento

- **POUM** aprovat i publicat DOGC **11/08/2021** (pàgines transparència + notícia municipal).
- No hi ha llistat HTML d’expedients en tràmit com Pozuelo; la informació és **referencial** (POUM, RPUC, visor) + paràgrafs transparència.
- **Registre RPUC** enllaçat des de planejament urbanístic (seu-e).

## Licencias

- No s’han trobat **resolucions de llicència** en obert (només tràmits i formularis).
- Catàleg seu.valls.cat: comunicacions d’obres (Annex I–III), certificat urbanístic, consultes urbanístiques, pròrrogues.
- Catàleg seu-e `/tramits-i-gestions` sovint protegit per **Cloudflare** des d’entorns cloud → adapter usa sobretot seu Drupal.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** GeoServer WFS `valls:sect_plan_a` (52 polígons, camps `codi_ajt`, `desc_ajt`, `doc`) i `valls:qual_urb_a` (61 polígons). CRS resposta `EPSG:4326`.
- **Estrategia:** cache WFS al backfill; enriquir files si el títol conté tokens del `codi_ajt` (p.ex. plans parcials PPU) o referències POUM/GeoValls (mostra un sector).
- **Limitaciones:** e-TAULER i seu-e tràmits sense llistat scrapeable; WFS no enllaça expedients administratius per número; licències sense geometria.

## Adapter

`municipio.adapters.valls:VallsAyuntamientoAdapter` — urllib, sense LLM.
