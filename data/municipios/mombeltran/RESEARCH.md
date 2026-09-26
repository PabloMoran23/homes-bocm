# Mombeltrán — investigación portal ayuntamiento

**Municipio:** Mombeltrán (`mombeltran`) — Ávila, Castilla y León  
**BOCM/BOCYL:** 3 entradas (`boletin_source_id: bocyl`)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa | https://www.mombeltran.es | HTML estático (.shtml), Bootstrap + menú desplegable |
| Planeamiento | https://www.mombeltran.es/planeamientourbanistico.shtml | Enlaces a SiuCyL, PlanPublica PLAU y PLAU-i (vacío) |
| Trámites / licencias | https://www.mombeltran.es/tramites.shtml | Acordeón Spry con trámites informativos (licencia obras, vados) + PDFs descargables |
| Sede electrónica | https://mombeltran.sedelectronica.es | espublico gestiona (Apache Wicket) |
| Tablón anuncios | https://mombeltran.sedelectronica.es/board | Tabla HTML con `preview-document/` (actualmente **0 filas**) |
| Trámites sede | https://mombeltran.sedelectronica.es/dossier | Catálogo de trámites electrónicos |
| PlanPublica JCyL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlauPrint.do?provincia=05&municipio=132&bInfoPublica=N | 1 documento vigente (modificación NUM) |
| SiuCyL visor | https://idecyl.jcyl.es/siur/index.html?id=05132 | Visor cartográfico provincial |

## Cómo se listan expedientes / planeamiento

- **PlanPublica (JCyL):** tabla HTML con `doOpen(docId, codigo)` → PDF vía `openDocumento.do?cDocId=…`. Campos: instrumento, tipo trámite, fechas, título.
- **IDECyL WFS:** capas `plau_cyl_instrumentos_ambito`, `plau_cyl_planes_parciales`, `plau_cyl_sectores` filtradas por `n_mun = 'Mombeltrán'`.
- **Web ayto:** página de planeamiento solo enlaza a servicios autonómicos; no hay listado propio de expedientes.
- **Tablón sede:** patrón espublico estándar (`<tbody>` + `preview-document`), pero sin anuncios publicados en el momento de la investigación.

## Licencias de obra

- No hay registro público de concesiones de licencia (ni tablón ni dataset).
- `tramites.shtml` documenta procedimientos (licencia municipal de obras, alta/baja vados) con formularios PDF en `/pdf/tramites/`.
- La sede permite solicitar trámites vía `/dossier`, pero no expone histórico de concesiones.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL `https://idecyl.jcyl.es/geoserver/urbanismo/ows` — capas PLAU con polígonos por sector/instrumento
  - SiuCyL visor `https://idecyl.jcyl.es/siur/` (consulta cartográfica; no API directa por expediente)
- **Estrategia:** query WFS `GetFeature` con `CQL_FILTER n_mun='Mombeltrán'` en 3 capas; enriquecer proyectos PlanPublica por coincidencia de título/instrumento.
- **Limitaciones:**
  - Tablón sede vacío → sin geometría por anuncio individual
  - Licencias sin georreferenciación pública
  - PLAU-i sin documentos en información pública
  - 1 doc PlanPublica vs 19 features WFS (mayoría sectores NUM)

## Limitaciones generales

- Web estática sin CMS dinámico ni API
- Tablón espublico sin contenido urbanístico actual
- Licencias: solo páginas informativas de trámites
- SSL sede válido (no requiere `insecure_ssl`)
