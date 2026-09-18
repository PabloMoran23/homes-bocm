# Guardo — investigación portal ayuntamiento

**Municipio:** Guardo (Palencia, Castilla y León)  
**Fecha:** 2026-09-18  
**BOCYL regional (referencia):** 1 aviso

## Resumen

Guardo publica urbanismo y licencias en **tres portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://guardo.org | WordPress (portal turístico/informativo) | Anuncios, normativa urbanística (enlace Google Drive), sin sección `/urbanismo/` |
| Sede electrónica | https://guardo.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios, catálogo trámites (111 trámites) |
| Junta CYL / SIUCyL | https://idecyl.jcyl.es/geoserver/urbanismo/wfs | WFS GeoServer | PGOU, 13 sectores, 1 plan parcial (La Albariza SU-11) |

## Fuentes identificadas

### 1. WordPress — guardo.org

- **URL base:** https://guardo.org
- **Formato:** WordPress clásico; REST API disponible para páginas
- **Anuncios:** https://guardo.org/anuncios/ — enlace externo a carpeta Google Drive «Normativa urbanística»
- **Limitación:** no hay categoría `/urbanismo/` ni listado de expedientes; el portal es mayoritariamente turístico

### 2. Sede electrónica — tablón de anuncios

- **URL:** https://guardo.sedelectronica.es/board
- **Formato:** tabla HTML espublico con `preview-document/{uuid}`
- **Extracto inicio:** https://guardo.sedelectronica.es/info.0
- Ventana corta (~10 anuncios); en la investigación no había entradas de urbanismo/licencias de obra (subvenciones, edictos, aprovechamientos vecinales)
- **SSL:** certificado con cadena incompleta en CI → `insecure_ssl: true`

### 3. Sede electrónica — catálogo trámites

- **URL:** https://guardo.sedelectronica.es/dossier.0 (requiere cookie de sesión del tablón; `/dossier` sin warm-up → bucle 302)
- **Formato:** enlaces `/catalog/t/{uuid}` con título del trámite
- Trámites urbanismo/licencias relevantes (17): Solicitud de Licencia o Autorización Urbanística, Declaración Responsable en Materia Urbanística, Solicitud de Actuación Urbanística, Modificación del Planeamiento, etc.

### 4. Junta CYL — PlanPublica

- **Info pública:** `searchVPubDocMuniPlai.do?provincia=34&municipio=80`
- **Archivo aprobado:** `searchVPubDocMuniPlau.do?provincia=34&municipio=80`
- Código municipio 80 = `c_mun` 34080 (Guardo, Palencia)
- **PGOU revisión:** `openDocuIndice.do?cDocId=282619` (aprobación 2006, BOCYL 2006-05-04)

### 5. Normativa urbanística (Google Drive)

- Enlace desde https://guardo.org/anuncios/ → carpeta compartida con documentación PDF
- No scrapeable de forma determinista (requiere auth Google); documentado como referencia humana

## Licencias

No hay visor georreferenciado ni dataset abierto de concesiones históricas.

- **Catálogo sede:** 17 trámites informativos de licencias urbanísticas, actividad, ocupación, etc.
- **Tablón:** sin concesiones de obra publicadas en la ventana actual
- Sin listado histórico de concesiones con coordenadas

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - SIUCyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 ámbito PGOU (6280 ha)
  - SIUCyL WFS `urbanismo:plau_cyl_sectores` — 13 polígonos (`n_mun='Guardo'`)
  - SIUCyL WFS `urbanismo:plau_cyl_planes_parciales` — 1 plan parcial «La Albariza» SU-11
  - URL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Campos: `n_sector`, `n_num_sect`, `c_id_sect`, `n_instrum`, `f_bocyl`, `url_doc_info`
- **Estrategia:** descarga WFS por municipio; enriquecimiento por código de sector en título (S-1…S-12, SU-11); expedientes tablón/catálogo sin GIS directo usan centroide municipal + jitter
- **Limitaciones:**
  - No hay visor municipal ArcGIS propio
  - Web guardo.org sin expedientes urbanísticos georreferenciados
  - Licencias y anuncios puntuales sin polígono enlazable
  - Catálogo dossier requiere warm-up de sesión vía tablón

## Limitaciones

- WordPress sin sección urbanismo; solo anuncios + enlace Drive
- Tablón sede: ventana corta, sin API, sin urbanismo en muestra
- `/dossier.0` sin cookie de tablón → bucle de redirección 302
- Licencias sin geolocalización en fuentes públicas
- PlanPublica: tabla de documentos con sesión JS; usado como semilla URL

## Estrategia adapter

1. WFS SIUCyL → proyectos con `geom_geojson` (15 features)
2. Tablón espublico `/board` + `/info.0` → proyectos/licencias filtrados
3. Catálogo trámites `/dossier.0` (warm-up tablón) → licencias y proyectos informativos
4. Semillas PlanPublica + anuncios → proyectos de planeamiento
5. IDs estables: `guardo-{lic|proy}-{sha256[:14]}`

## Referencia adapters

- espublico tablón + dossier: `duenas.py`
- IDECyL WFS geometría: `villadangos_del_paramo.py`
