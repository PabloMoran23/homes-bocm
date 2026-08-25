# Villamuriel de Cerrato — investigación portal ayuntamiento

**Municipio:** Villamuriel de Cerrato (Palencia, Castilla y León)  
**Fecha:** 2026-08-23  
**BOCYL regional (referencia):** 3 avisos

## Resumen

Villamuriel de Cerrato no dispone de **web corporativa** con DNS activo (`villamurieldecerrato.es` no resuelve). La publicación urbanística se concentra en la **sede electrónica espublico** y en los portales autonómicos **PlanPublica** e **IDECyL/SIUCyL**.

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Sede electrónica | https://villamurieldecerrato.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios, servicio información pública |
| PlanPublica JCyL | https://servicios.jcyl.es/PlanPublica/ | JSP | Archivo planeamiento aprobado (15 docs) |
| IDECyL WFS | https://idecyl.jcyl.es/geoserver/urbanismo/wfs | GeoServer | Sectores, planes parciales, ámbito PGOU |

## Fuentes identificadas

### 1. Sede electrónica — tablón de anuncios

- **URL:** https://villamurieldecerrato.sedelectronica.es/board
- **Formato:** tabla HTML espublico (Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha)
- **Ventana:** ~10 anuncios recientes; mayoría administrativa (empleo, subvenciones, censos)
- **Urbanismo/obras:** ayudas para obras en espacios urbanos, ordenanza edificio Soto Alburez
- **SSL:** certificado con cadena incompleta en CI → `insecure_ssl: true`

### 2. Sede — información pública

- **URL:** https://villamurieldecerrato.sedelectronica.es/citizen-service/256bf975-701d-4ee8-81e3-f2815195d8a9
- Servicio en línea para consulta de expedientes en información pública

### 3. Sede — catálogo trámites (no accesible)

- `/dossier`, `/dossier.0`, `/info`, `/info.0` → bucle de redirección 302 en urllib/curl
- No scrapeable; se usan páginas informativas de PlanPublica como semillas

### 4. Junta CYL — PlanPublica

- **Archivo aprobado:** `searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=34&municipio=217`
- **Info pública:** `searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=34&municipio=217` (0 docs activos)
- Código municipio 217 = INE 34217 (Villamuriel de Cerrato, Palencia)
- Instrumentos: PP S-3 El Tesoro, Sector 4 La Carcava, PERI Polígono San Blas, NUM, PPI industrial, etc.

### 5. IDECyL — SIUCyL WFS

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- Capas consultadas:
  - `urbanismo:plau_cyl_sectores` — 21 polígonos
  - `urbanismo:plau_cyl_planes_parciales` — 4 planes parciales
  - `urbanismo:plau_cyl_instrumentos_ambito` — 1 ámbito PGOU
- Campos: `n_sector`, `n_num_sect`, `c_id_sect`, `n_instrum`, `f_bocyl`, `url_doc_info`

## Licencias

No hay visor georreferenciado ni dataset abierto de concesiones históricas.

- Tablón: anuncios puntuales sobre ayudas a obras en espacios urbanos (subvenciones, no concesiones)
- Sin catálogo de trámites accesible (`/dossier` en bucle)
- Páginas informativas de PlanPublica como referencia de trámites urbanísticos

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - SIUCyL WFS `urbanismo:plau_cyl_sectores` — 21 polígonos (`n_mun='Villamuriel de Cerrato'`)
  - SIUCyL WFS `urbanismo:plau_cyl_planes_parciales` — 4 planes parciales
  - SIUCyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 ámbito PGOU
  - URL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Campos: `n_sector`, `n_num_sect`, `c_id_sect`, `n_instrum`, `f_bocyl`
- **Estrategia:** descarga WFS por municipio; enriquecimiento por código de sector en título (S-3, Sector 2, UZPI, CTU); expedientes tablón/PLAI sin GIS directo usan centroide municipal + jitter
- **Limitaciones:**
  - Sin web corporativa ni visor municipal propio
  - `/dossier` y `/info.0` con bucle de redirección
  - Licencias y anuncios puntuales sin polígono enlazable
  - PlanPublica info pública vacía (0 docs)

## Limitaciones

- Sin web municipal (solo sede electrónica)
- Tablón sede: ventana corta, sin API
- Catálogo trámites inaccesible (redirect loop)
- Licencias sin geolocalización en fuentes públicas

## Estrategia adapter

1. WFS SIUCyL → proyectos con `geom_geojson` (26 features)
2. PlanPublica Plau/Plai → proyectos de planeamiento (15 docs archivo)
3. Tablón espublico `/board` → proyectos/licencias filtrados
4. Páginas informativas (citizen-service IP, PlanPublica) → semillas
5. IDs estables: `villamuriel-de-cerrato-{lic|proy}-{sha256[:14]}`

## Referencia adapters

- espublico tablón: `pelabravo.py`
- IDECyL WFS + PLAI: `melgar_de_fernamental.py`, `duenas.py`
