# Fresno de la Vega — investigación portal ayuntamiento

**Municipio:** Fresno de la Vega (provincia León, Castilla y León)  
**Fecha:** 2026-09-16  
**BOCYL (referencia):** 1 aviso  
**INE:** 24073 | **PlanPublica:** provincia=24, municipio=073

## Resumen

Fresno de la Vega publica urbanismo en **tres portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://www.fresnodelavega.org | WordPress | Normativa urbanística, enlaces a Junta CYL |
| Sede electrónica | https://fresnodelavega.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios, catálogo trámites, transparencia |
| Junta CYL | https://servicios.jcyl.es/PlanPublica/ | Java portal | Planeamiento aprobado (NUM) y archivo PLAU |

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Inicio web | https://www.fresnodelavega.org/ |
| Normativa urbanística | https://www.fresnodelavega.org/pages/documents/ |
| Trámites (enlace sede) | https://www.fresnodelavega.org/pages/departments/ |
| Tablón de anuncios | https://fresnodelavega.sedelectronica.es/board/ |
| Tablón información pública | https://fresnodelavega.sedelectronica.es/info.0 |
| Catálogo trámites | https://fresnodelavega.sedelectronica.es/dossier/.0 |
| Transparencia (sección 7) | https://fresnodelavega.sedelectronica.es/transparency |
| PLAU — archivo aprobado | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=24&municipio=073 |
| PLAI — información pública | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=24&municipio=073 |

## Proyectos / expedientes

### 1. IDECyL WFS — sectores e instrumentos

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Capas con datos (sep 2026):**
  - `plau_cyl_instrumentos_ambito`: 1 polígono (NUM — Normas Urbanísticas Municipales, `24073-PU-20120214-287804`)
  - `plau_cyl_sectores`: 1 sector **Valderinas SUNC-SR-01** (MultiPolygon)
  - `plau_cyl_planes_parciales`: 0 features
- **Filtro:** `n_mun = 'Fresno de la Vega'`

### 2. Sede electrónica — tablón de anuncios

- Tabla HTML espublico (Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha)
- Ventana corta (~10 anuncios); incluye **EXPOSICIÓN PÚBLICA PROYECTOS PIOS** (sep 2026)
- PDFs en `https://fresnodelavega.sedelectronica.es/preview-document/{uuid}`
- Sin paginación pública evidente

### 3. PlanPublica (Junta CYL)

- NUM aprobado (2012) accesible vía PLAU
- Listado HTML con enlaces `doOpen(cDocId)` y PDFs

### 4. Transparencia

- Sección **7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE** — 34 documentos (requiere sesión Wicket)

## Licencias de obra

No hay listado histórico público de concesiones con coordenadas.

| Fuente | Contenido |
|--------|-----------|
| Catálogo sede (`/dossier/.0`) | Formularios: licencia/autorización urbanística, declaración responsable, ocupación, certificado urbanístico |
| Tablón sede | Sin licencias de obra en ventana visible (sep 2026) |
| Web WordPress | Enlace a sede para «Autorización Urbanística» |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — polígono sector Valderinas SUNC-SR-01
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — ámbito NUM municipal
  - SiUR visor regional: `https://idecyl.jcyl.es/siur/index.html?id=24073`
- **Estrategia:** descarga WFS por municipio (`n_mun='Fresno de la Vega'`); enriquecimiento por código de sector en título del tablón; expedientes sin GIS usan centroide municipal + jitter
- **Limitaciones:** licencias y anuncios del tablón sin polígono enlazable; visor municipal inexistente; transparencia requiere sesión Wicket

## CMS / tecnología

| Componente | Stack |
|------------|-------|
| Web corporativa | **WordPress** (tema municipal, REST API `/wp-json/`) |
| Sede electrónica | **espublico gestiona** (Apache Wicket + nginx) |
| Planeamiento regional | **PlanPublica** — portal Java/JSP (Junta CyL) |
| GIS regional | **GeoServer** IDECyL + visor **SiUR** |

## Limitaciones

- Tablón sede: ventana corta, sin API
- `/dossier/.0` requiere cookie de sesión (primera carga ~7 s)
- Licencias sin geolocalización en fuentes públicas
- Sin visor urbanístico municipal propio

## Estrategia adapter

1. WFS IDECyL → proyectos con `geom_geojson`
2. Tablón espublico → proyectos/licencias filtrados por keywords
3. Catálogo dossier → licencias/trámites informativos
4. Semillas normativa + JCyl → proyectos de planeamiento
5. IDs: `fresno-de-la-vega-{lic|proy}-{sha256[:14]}`
