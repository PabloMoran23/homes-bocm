# Los Huertos — investigación portal ayuntamiento

**Municipio:** Los Huertos (Castilla y León, Segovia)  
**INE:** 40103  
**Fecha:** 2026-09-22

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (Liferay / Diputación Segovia) | https://www.loshuertos.es | Portal Segovia11 theme (Diputación de Segovia) |
| Urbanismo | https://www.loshuertos.es/urbanismo | Página informativa con enlace a sede electrónica; sin biblioteca PDF local |
| Tablón de anuncios web | https://www.loshuertos.es/tablon-de-anuncios | Asset Publisher RSS vacío (sin entradas) |
| Sede electrónica (espublico gestiona) | https://loshuertos.sedelectronica.es | Trámites, tablón `/board`, consulta expedientes |
| Tablón sede | https://loshuertos.sedelectronica.es/board/ | Tablón de anuncios (vacío a sept. 2026) |
| Catálogo trámites | https://loshuertos.sedelectronica.es/dossier | Trámites urbanísticos (licencias, planeamiento) |
| PLAI Junta CYL (prov. 40, mun. 103) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=40&municipio=103 | Archivo planeamiento aprobado (6 documentos) |
| PLAI información pública | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=40&municipio=103 | Sin documentos en IP activa |

## Cómo se listan expedientes

- **PLAI JCYL (PlanPublica):** tabla HTML con instrumentos de planeamiento (NUM, DOAS, PYIC). Documentos vía `openDocumento.do?cDocId=` o `doGoBoletin`.
- **IDECyL WFS:** capas `plau_cyl_instrumentos_ambito` (1 NUM), `plau_cyl_sectores` (5 sectores: UA-1, Sector 1a/1b/2/3).
- **Sede espublico:** tablón `/board` con tabla de anuncios (expediente, procedimiento, categoría); actualmente sin filas urbanísticas.
- **Web Liferay:** `/urbanismo` sin documentos PDF en biblioteca; redirige a sede electrónica.
- **BOCYL:** 1 entrada en CSV regional (`boletin_source_id: bocyl`).

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra publicadas.
- Trámites disponibles en sede (`/dossier`): solicitud de licencia urbanística, comunicación previa, etc.
- Tablón sede vacío; no hay licencias concedidas scrapeables.
- Estrategia adapter: páginas informativas de trámites de sede + semillas urbanismo/sede.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito` (1), `urbanismo:plau_cyl_planes_parciales` (0), `urbanismo:plau_cyl_sectores` (5)
  - Filtro: `n_mun = 'Los Huertos'` (c_mun=40103)
  - Campos: `n_titulo`, `n_sector`, `n_num_sect`, `c_id_sect`, `f_aprob`, `f_bocyl`, `url_doc_info`
  - Visor mapa PLAI: enlace «Pulse para ver el planeamiento vigente en el mapa» en PlanPublica
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer filas PLAI por coincidencia de sector en título.
- **Limitaciones:**
  - Sin visor ArcGIS municipal propio.
  - Tablón sede y web vacíos; licencias sin georreferencia.
  - Geometría WFS solo para ámbitos PLAU CyL (NUM + sectores), no para licencias individuales.
  - Sede `/dossier` responde lento desde CI (>45s).

## Limitaciones generales

- Municipio pequeño (~180 hab.); volumen bajo de publicaciones urbanísticas activas.
- Portal gestionado por plantilla Diputación de Segovia (Liferay Segovia11); patrón replicable en otros municipios segovianos.
- `insecure_ssl: true` en sede espublico por compatibilidad CI.
