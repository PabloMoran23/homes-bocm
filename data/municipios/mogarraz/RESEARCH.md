# Mogarraz — investigación portal ayuntamiento

**Municipio:** Mogarraz (Salamanca, Castilla y León)  
**INE:** 37194 · **PlanPublica:** provincia `37`, municipio `194`  
**BOCYL:** 1 referencia en cola (`bocyl`)

## URLs base y semillas

| Recurso | URL | Notas |
|---------|-----|--------|
| Web municipal | https://www.mogarraz.es | WordPress (tema Parabola), REST `/wp-json/` |
| Normas urbanísticas | https://www.mogarraz.es/normas-urbanisticas/ | Listado de PDFs (`/_mgz_pdf/PI-*-37194.pdf`, PO-*, plan especial protección) |
| Trámite licencias (informativo) | https://www.mogarraz.es/solicitud-de-licencia-de-obras-y-declaracion-responsable/ | Sin tablón de concesiones |
| PlanPublica PLAU | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=194 | 5 documentos (NUM, PORN regional) |
| PlanPublica PLAI | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=194 | Información pública asociada |
| IDECyL WFS | https://idecyl.jcyl.es/geoserver/urbanismo/wfs | Capas `plau_cyl_instrumentos_ambito`, sectores/parciales |
| Sede electrónica | https://mogarraz.sedelectronica.es | **No resuelve** (sin DNS / sin servicio público en el momento de la investigación) |

## Cómo se listan expedientes / planeamiento

- **Web WP:** página estática con enlaces directos a PDF de normas y plan especial de protección; no hay listado de expedientes IP ni visor propio.
- **PlanPublica:** tabla HTML con `doGoBoletin` / `openDocumento.do?cDocId=`; scrape determinista de filas `<tr>`.
- **IDECyL WFS:** GeoJSON por municipio (`n_mun = 'Mogarraz'`); 1 instrumento de ámbito (NUM) con geometría; 0 sectores ni planes parciales desglosados.

## Licencias de obra

No hay tablón de anuncios accesible (sede inexistente). Solo página informativa de solicitud de licencia/declaración responsable en la web municipal. El adapter devuelve filas de **trámite informativo** (patrón Pozuelo/Valverdón sin tablón).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` filtrado `n_mun='Mogarraz'` (polígono del instrumento NUM municipal); sin visor ArcGIS municipal ni WFS de expedientes.
- **Estrategia:** ingestar geometría del instrumento WFS; enriquecer filas PLAU tipo NUM vía `_attach_geometry`; PDFs sin georef.
- **Limitaciones:** sin sede/tablon de licencias; sin sectores WFS; PDFs del ayuntamiento sin coordenadas; sede espublico no accesible.

## Limitaciones generales

- SSL sede: N/A (host no resuelve).
- Paginación: no aplica (pocos documentos).
- Dependencia de PDFs históricos en dominio `mogarraz.es` (algunos paths `/ayuntamiento/_mgz_pdf/`).
