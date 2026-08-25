# Sevilla — portal Gerencia de Urbanismo

**Slug:** `sevilla`  
**Comunidad:** Andalucía (`andalucia`)  
**Provincia:** Sevilla  
**Boletín:** BOJA (`boja`)

## URLs base y páginas semilla

| Recurso | URL | Tecnología | Uso |
|---------|-----|------------|-----|
| Portal urbanismo | https://www.urbanismosevilla.org | Plone (THEME Urbanismo Sevilla) | Planeamiento, trámites, GEO-info |
| Planeamiento NN.DD | https://www.urbanismosevilla.org/areas/planeamiento-desarrollo-urbanistico/planeamiento-en-tramite-segun-nn-dd-de-la-documentacion-electronica-de-los-instrumentos-de-ordenacion-urbanistica-de-andalucia/ | Plone categoría | **Proyectos en trámite** (8 fichas al 2026-08) |
| Índice NN.DD (atajo) | https://www.urbanismosevilla.org/planeamiento/planeamiento-en-tramite-nn-dd-junta-de-andalucia | Plone | Enlaces a mismas fichas |
| Oficina virtual | https://extranet.urbanismosevilla.org/Extranet/ | ASP.NET | Consulta expedientes, DR obra, listado aprobaciones |
| Consulta expedientes | https://www.urbanismosevilla.org/oficina-virtual/consulta-de-expedientes | Enlace → extranet | Licencias/ITE (requiere datos expediente) |
| Listado aprobaciones | https://extranet.urbanismosevilla.org/Extranet/ListadoAprobaciones.aspx | ASP.NET + AJAX | Aprobaciones planeamiento (carga dinámica; sin API pública) |
| Datos abiertos IDE | https://cda-idesevilla.opendata.arcgis.com/ | ArcGIS Hub | Capas LOUA / NNSS (servicios raster) |
| Callejero CDUS | https://map4.urbanismosevilla.org/GIS_GIE/CAU/callejero/Embedded.aspx | JS + ArcGIS | Búsqueda vial y portales |
| geoSEVILLA / ide.SEVILLA | https://sig.urbanismosevilla.org/ | ArcGIS legacy | Visor; WMS/tiles |
| Sede ayuntamiento | https://sede.sevilla.org | — | **Inaccesible** desde CI (SSL handshake timeout) |

## Cómo se listan expedientes / proyectos

- **Planeamiento en trámite (NN.DD):** categoría Plone con una página por instrumento (slug descriptivo). Título en `<h1>`, sin tablón RSS. Ejemplos: estudios de ordenación (Luis Montoto 138, Kansas City 9), planes parciales (Palmas Altas Sur), SUNP Lagoh.
- **Planeamiento en desarrollo / registro:** páginas índice sin listado HTML scrapeable (contenido vacío o solo menú).
- **Listado de aprobaciones:** formulario extranet con ViewState; datos en grid cargado por JavaScript (`FuncionesAJAX.js`), no expuesto como JSON público.
- **SITUA Junta de Andalucía:** sin filas para municipio 41091 en `planeamientoGeneralCompartir.jsf` (Sevilla gestiona planeamiento en portal propio).

## Cómo se publican licencias

- No hay tablón público scrapeable en `sede.sevilla.org` (timeout SSL).
- **Oficina Virtual** ofrece consulta de expediente por número (licencias, ITE, calicatas, vados) sin listado masivo.
- Trámites informativos: obra menor (DR modelo 2), DR con técnico (modelo 5), ITE, renovación veladores.
- Diputación Sevilla LicytalPub devuelve HTTP 500 para CIF ayuntamiento (`P4114800J`).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - **CDUS Callejero CDAU** (consultable): búsqueda vial `TR_Callejero_ORA_json.ashx` → `id_vial`; geometría portal en `map5.urbanismosevilla.org/sci/rest/services/Callejero/Callejero_CDAU/MapServer/1` (`esriGeometryPoint`, campos `NUM_POR_DE`, `REFCATPARC`).
  - **ide.SEVILLA / ArcGIS Online** (`tiles-eu1.arcgis.com/wiBHjWb8dHS8gqIZ`): capas LOUA, NNSS, UAR, etc. publicadas como **MapServer raster** (`capabilities: Map,TilesOnly`) — **no query** (`returnGeometry` no disponible).
  - **ArcGIS Hub** (`cda-idesevilla.opendata.arcgis.com`): metadatos y tiles; descargas GeoJSON vacías; OGC Features 403.
- **Estrategia adapter:** extraer calle/número del título del proyecto → buscar `id_vial` → query portal CDAU → `geom_geojson` Point + centroide.
- **Limitaciones:**
  - Solo puntos de portal (no polígonos parcela; capa parcelas del visor JS apunta a servicio antiguo no expuesto en MapServer actual).
  - Proyectos sin dirección en título (p. ej. ámbitos SUNP genéricos) quedan sin geometría.
  - `sede.sevilla.org` y LicytalPub no accesibles desde el entorno del agente.

## Limitaciones generales

- Portal principal `www.sevilla.org` con conectividad intermitente; fuente operativa es `urbanismosevilla.org`.
- Listado masivo de licencias y aprobaciones requiere interacción con extranet (certificado o formulario).
- Sin re-parse BOCM; 3 entradas BOJA ya en pipeline regional.
