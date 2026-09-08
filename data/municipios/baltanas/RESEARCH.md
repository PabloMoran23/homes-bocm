# Baltanás — investigación portal ayuntamiento

**Municipio:** Baltanás (Palencia, Castilla y León)  
**Fecha:** 2026-09-08  
**BOCYL regional (referencia):** 1 aviso

## Resumen

Baltanás publica urbanismo y licencias en **cuatro portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://baltanas.es | WordPress + Elementor (Dip. Palencia) | Página urbanismo, enlaces a documentación y JCyL |
| Sede electrónica | https://baltanas.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios, catálogo trámites, transparencia |
| Junta CYL / PlanPublica | https://servicios.jcyl.es/PlanPublica | JSP | PLAU/PLAI documentos aprobados e info pública |
| IDECyL / SIUCyL | https://idecyl.jcyl.es/geoserver/urbanismo/wfs | WFS GeoServer | Sectores NUM, ámbito instrumento |

## Fuentes identificadas

### 1. WordPress — Urbanismo y vivienda

- **URL semilla:** https://baltanas.es/ayuntamiento/urbanismo-y-vivienda/
- **Subsecciones (plugin documental, redirigen a la misma página):**
  - `?g=10&st=0` Documentación informativa
  - `?g=10&st=1` Planeamiento en tramitación
  - `?g=10&st=2` Cerrado
  - `?g=20` Licencias
- **Enlace JCyL:** `lplanes.plau?municipio=3402250001701`
- **REST API:** parcialmente disponible (`/wp-json/wp/v2/pages/870`); sin categoría urbanismo con noticias

### 2. Sede electrónica — tablón de anuncios

- **URL:** https://baltanas.sedelectronica.es/board/
- **Formato:** tabla HTML espublico con `preview-document/{uuid}`
- **Contenido urbanismo (sep 2026):** aprobación definitiva reparcelación sector SE-00-A (NUM), adendas, proyectos de actuación
- **info.0:** timeout frecuente desde CI; tablón principal suficiente

### 3. Sede electrónica — catálogo trámites

- **URL:** https://baltanas.sedelectronica.es/dossier.0 (requiere sesión previa vía `/board/`)
- **Formato:** enlaces `/catalog/t/{uuid}` (~110 trámites)
- Trámites urbanismo/licencias: solicitud licencia, declaración responsable, certificados urbanísticos, etc.

### 4. Junta CYL — PlanPublica

- **PLAI (info pública):** `searchVPubDocMuniPlai.do?provincia=34&municipio=18`
- **PLAU (archivo aprobado):** `searchVPubDocMuniPlau.do?provincia=34&municipio=18`
- Código municipio PlanPublica: **18** (INE 34022)
- Documentos: delimitación suelo urbano, plan parcial industrial, NUM, etc.

### 5. Portal transparencia sede

- **URL:** https://baltanas.sedelectronica.es/transparency
- Sección **7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE** (10 documentos)
- Carga vía AJAX Wicket; no scrapeado (tablón + WFS + PLAU cubren expedientes)

## Licencias

No hay visor georreferenciado ni dataset abierto de concesiones históricas.

- **Catálogo sede:** páginas informativas de trámites (licencia urbanística, ocupación, etc.)
- **Tablón:** anuncios puntuales cuando mencionan licencias/obras
- **Web:** enlace a sección licencias (`?g=20`) sin listado público detallado
- Sin listado histórico de concesiones con coordenadas

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — 18 polígonos (`n_mun='Baltanás'`, códigos SE-00, SE-00-A, SE-02…)
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 ámbito (Normas Urbanísticas Municipales)
  - URL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Campos: `n_sector`, `n_num_sect`, `c_id_sect`, `n_instrum`, `f_bocyl`, `c_mun=34022`
- **Estrategia:** descarga WFS por municipio; enriquecimiento por código de sector en título del tablón (p. ej. SE-00-A); expedientes PLAU/tablón sin GIS directo usan centroide municipal + jitter
- **Limitaciones:**
  - No hay visor municipal ArcGIS propio
  - Licencias y expedientes puntuales sin polígono enlazable
  - Consulta expedientes sede requiere certificado digital
  - Subsecciones documentales WP (`?g=10`) redirigen sin listar PDFs en HTML estático

## Limitaciones

- WordPress sin categoría `/urbanismo/` con noticias (web reciente, sep 2025)
- Tablón sede: ventana corta (~3 anuncios urbanismo visibles)
- `dossier.0` requiere cookie de sesión (warm-up vía board)
- SSL sede: posible cadena incompleta → `insecure_ssl: true`
- `info.0` inestable desde entornos CI

## Adapter

- `municipio/adapters/baltanas.py` — `BaltanasAyuntamientoAdapter`
- Fuentes: WFS IDECyL + tablón sede + catálogo trámites + PlanPublica PLAU/PLAI + páginas semilla
