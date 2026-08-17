# Estremera — investigación portal ayuntamiento

**Slug:** `estremera`  
**Nombre oficial:** Estremera  
**BOCM (referencia):** 3 anuncios  
**Fecha investigación:** 2026-08-17

## Dominios

| Rol | URL | Estado |
|-----|-----|--------|
| Web corporativa (WordPress) | https://estremera.es | Accesible |
| Sede electrónica (Maggioli / eAdmin) | https://sedeestremera.eadministracion.es | Accesible (SPA; tablón sin HTML scrapeable) |
| Transparencia (Maggioli) | http://transparenciaestremera.eadministracion.es | Accesible (sin urbanismo indexado) |
| Sede legacy (espublico) | https://estremera.sedelectronica.es | Parcial — tablón deshabilitado; transparencia vacía en urbanismo |

## URLs base y páginas semilla

| Recurso | URL | Formato | Contenido |
|---------|-----|---------|-----------|
| Concentración parcelaria | https://estremera.es/2024/11/05/concentracion-parcelaria/ | WordPress + PDF | Actuación agraria/urbanística Estremera II Secano |
| Bandos | `/category/ayuntamiento/bandos/` | WordPress | Convocatorias (quioscos, gestión barra fiestas) |
| Obras municipales | `/category/ayuntamiento/obras/` | WordPress | Noticias obras (algunas mencionan ámbitos SITCM: Peña Rubia, La Vega) |
| Mapa cartográfico | https://estremera.es/mapa-cartografico/ | WP embed | Mapa turístico sin capas urbanísticas |
| Tablón eAdmin | `sedeestremera.eadministracion.es/PortalCiudadano/Tablon/wfrTablon.aspx` | ASP.NET SPA | Shell sin filas scrapeables vía HTTP simple |
| Transparencia espublico | `estremera.sedelectronica.es/transparency` | espublico | Sección «7. URBANISMO…» con 0 documentos |
| WP REST API | `estremera.es/wp-json/wp/v2/posts` | JSON | Accesible (a diferencia de otros municipios con Solid Security) |

## Proyectos / expedientes

- **Concentración parcelaria** (nov 2024): reunión informativa + PDF manifestación conformidad.
- **Bandos** municipales (quioscos, gestión barra) — no planeamiento pero categoría bandos monitorizada.
- **Obras** en ámbitos del planeamiento (Peña Rubia, La Vega) publicadas como noticias.
- No hay visor de expedientes urbanísticos ni listado tabular de información pública en sede.

## Licencias de obra

No hay registro público de concesiones con coordenadas.

Fuentes:

- Sede eAdmin Maggioli (trámites con identificación; tablón SPA)
- Sede espublico legacy con tablón deshabilitado
- Sin dataset de licencias en transparencia

Estrategia adapter: páginas informativas de sede (como Pozuelo/Robledo de Chavela).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid SITCM: `sitcm:VPLA_V_AMBITO` con `DS_MUNICIPIO='ESTREMERA'` (15 features: AA-1…AA-7, S-1…S-4, actuación aislada)
  - URL: `https://idem.comunidad.madrid/geoserver3/ows?service=WFS&typeName=sitcm:VPLA_V_AMBITO&CQL_FILTER=DS_MUNICIPIO='ESTREMERA'`
  - Sin visor urbanístico municipal propio; mapa cartográfico web es turístico
- **Estrategia:** matching por palabras clave en títulos (`Peña Rubia`, `La Vega`, códigos AA/S) vía `resolve_ambito_geometry` y mapa `AMBITO_KEYWORDS`
- **Limitaciones:** concentración parcelaria y bandos sin georreferencia; sede SPA sin API pública; muchos anuncios sin código de ámbito

## Limitaciones generales

- Tablón espublico (`/board`) devuelve «Página deshabilitada»
- Transparencia espublico urbanismo vacía (0 documentos)
- eAdmin tablón requiere sesión/JS; no scrapeable determinísticamente
- Sin histórico tabular de licencias concedidas
- WP REST accesible; scraping vía REST + HTML

## Referencia adapters

- WordPress + SITCM partial: `robledo_de_chavela.py`, `perales_de_tajuna.py`
- Trámites informativos licencias: `pozuelo.py`
