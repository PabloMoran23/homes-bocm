# Tordesillas — investigación portal ayuntamiento

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal (Liferay) | https://tordesillas.ayuntamientosdevalladolid.es/ |
| Urbanismo | https://tordesillas.ayuntamientosdevalladolid.es/el-municipio/urbanismo |
| Sede electrónica (tablón) | https://tordesillas.sedelectronica.es/board |
| Portal transparencia | https://tordesillas.sedelectronica.es/transparency |
| Trámites (dossier) | https://tordesillas.sedelectronica.es/dossier |
| PLAI JCYL (docs publicados) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=47&municipio=165 |
| Urbanismo en Red JCYL | https://urbanismoenred.jcyl.es/ |
| IDECyL WFS sectores | https://idecyl.jcyl.es/geoserver/urbanismo/ows |

## Cómo se listan expedientes

- **Liferay (ayuntamientosdevalladolid.es)**: portal provincial con sección Urbanismo (planeamiento vigente, instrumentos en tramitación, documentos en información pública). Enlaces a Urbanismo en Red, LocalGIS e IDEVA. La web municipal puede responder con timeout desde CI (>60 s).
- **Sede espublico (Wicket)**: tablón `/board` con anuncios (`preview-document` UUIDs). Transparencia `/transparency` incluye sección «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» (9 documentos). `/dossier` puede redirigir o tardar.
- **PLAI JCYL**: tabla paginada (~72 documentos) de instrumentos de planeamiento (PP, PERI, ED, modificaciones PGOU) con `openDocumento.do?cDocId=…`.
- **No hay** visor urbanístico propio del ayuntamiento; consulta parcelaria vía Urbanismo en Red / LocalGIS (JCYL).

## Licencias de obra

- El tablón actual no publica concesiones de licencias de obra (predominan plenos, fiestas, oposiciones).
- Transparencia agrupa documentación de urbanismo pero sin listado de licencias concedidas con coordenadas.
- El adapter incluye páginas informativas de trámites (sede, urbanismo web, PLAI).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — 36 sectores del PGOU de Tordesillas (`n_mun='Tordesillas'`, códigos SUED-1…SUED-17, etc.)
  - Capas adicionales: `plau_cyl_instrumentos_ambito` (1), `plau_cyl_planes_parciales` (12)
  - URL ejemplo: `https://idecyl.jcyl.es/geoserver/urbanismo/ows?service=WFS&version=2.0.0&request=GetFeature&typeNames=urbanismo:plau_cyl_sectores&CQL_FILTER=n_mun='Tordesillas'&outputFormat=application/json&srsName=EPSG:4326`
  - Campo enlace: `n_num_sect` (p. ej. `SUED-1`, `SUED-14`), `c_id_sect`
- **Estrategia:** ingestar polígonos WFS como proyectos; enriquecer filas PLAI/tablón extrayendo códigos de sector (`SUED-14`, `SAU-1`, etc.) y consultando WFS por `n_num_sect`.
- **Limitaciones:** sin visor ArcGIS municipal; estudios de detalle y PERI sin polígono en WFS salvo coincidencia por código; licencias sin georreferencia; web Liferay con timeout frecuente; sede requiere `insecure_ssl`.
