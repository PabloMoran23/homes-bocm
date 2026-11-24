# Palafrugell — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web corporativa | https://palafrugell.cat |
| Expedients en tramitació | https://palafrugell.cat/serveis-ciutadania/urbanisme/expedients-urbanistics-en-tramitacio |
| Paginación (p.2) | https://palafrugell.cat/serveis-ciutadania/urbanisme/expedients-urbanistics-en-tramitacio/2 |
| Geoportal urbanístic | https://mapes.palafrugell.cat/geoportal/ |
| Fitxes planejament (ex.) | https://mapes.palafrugell.cat/documentacio/planejament/PlanejamentDerivat/Vigent/P/P56/P56.htm |
| Seu electrònica | https://seu.palafrugell.cat |
| Tràmits urbanisme i obres | https://seu.palafrugell.cat/tramits/urbanisme-i-obres |
| e-TAULER (idEns) | https://tauler.seu.cat/inici.do?idens=1711750006 |
| Config geoportal | https://mapes.palafrugell.cat/geoportal/assets/applicationProperties/config.json |

## CMS y listado de expedientes

- **Joomla + YOOtheme + ZOO**: cada expedient en tramitació es un `<h2>` amb enllaç «Accés a la fitxa» cap a `mapes.palafrugell.cat/documentacio/planejament/.../{L}/{code}/{code}.htm`.
- Codi intern de planejament derivat en la URL (p. ex. `P56`, `T120`, `M27`).
- Fitxes HTML (Word) amb enllaços a PDFs al CD (`.../CD/P56_1.pdf`).
- Paginació manual (`/2`, …) detectada des del llistat.

## Licencias de obra

- **No** hi ha registre públic de llicències concedides amb coordenades.
- Catàleg de tràmits a la seu (`urbanisme-i-obres`) i pàgina informativa de tramitació de llicències al web municipal.
- **e-TAULER** per edictes/exposició pública (SPA, sense API estable).
- Alguns expedients del llistat són llicències d'activitat (p. ex. Cap Roig); es mantenen com a projectes del llistat d'urbanisme.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Geoportal NexusGIS (Angular + OpenLayers): WMS MapServer `Planejament_deriv` i GeoServer `palafrugellgis/wms`.
  - **API de cerca** `https://mapes.palafrugell.cat/cercagis_suggest/simple/all/{query}` retorna candidats amb `category: Planejament Derivat` i `bbox` WKT en **EPSG:25831**.
  - Fitxes amb plànols PDF (delimitació documental, no vector enllaçable per codi).
- **Estrategia:** Emparellar títol de l'expedient del llistat ZOO amb el millor candidat «Planejament Derivat» del suggest; convertir `bbox` WKT → GeoJSON WGS84 (`pyproj` + `shapely`).
- **Limitaciones:** Coincidència per text (no hi ha camp `P56` directe al suggest); alguns expedients (mesures de suspensió, convenis) poden no tenir polígon al índex GIS; WMS sense WFS públic per planejament derivat.

## Limitaciones generales

- Sense boletí regional associat a la cola (`bocm_count: 0`).
- `seu.palafrugell.cat` pot ser lent; s'usa timeout 90s.
- Geoportal intern (`GIS Intranet`) no accessible públicament.
