# Ciudad Rodrigo — investigación portal ayuntamiento

**Municipio:** Ciudad Rodrigo (Salamanca, Castilla y León)  
**Slug:** `ciudad-rodrigo`  
**Boletín:** BOCYL (`bocyl`, 17 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.ciudadrodrigo.es/ayuntamiento/ | **Operativa** — WordPress (tema Elletta) |
| Área urbanismo | https://www.ciudadrodrigo.es/ayuntamiento/area-de-urbanismo-y-obras/ | Informativa |
| PGOU | https://www.ciudadrodrigo.es/ayuntamiento/plan-general-de-ordenacion-urbana-municipal/ | **Operativa** — 65 PDFs de planeamiento |
| Informes urbanísticos | https://www.ciudadrodrigo.es/ayuntamiento/informes-seguimiento-actividad-urbanistica/ | **Operativa** — informes anuales 2012–2024 (PDF) |
| Trámites impresos | https://www.ciudadrodrigo.es/ayuntamiento/tramites-y-gestiones-impresos/ | Formularios licencias/obras |
| WP REST API | https://www.ciudadrodrigo.es/ayuntamiento/wp-json/wp/v2/ | **Operativa** — posts por categoría urbanismo |
| Sede electrónica | https://ciudadrodrigo.sedelectronica.es | espublico gestiona; home con redirect loop |
| Tablón de anuncios | https://ciudadrodrigo.sedelectronica.es/board/ | **Operativa** — tabla HTML (~10 filas vigentes) |
| Catálogo trámites | https://ciudadrodrigo.sedelectronica.es/dossier | Redirect loop desde CI |
| Consulta expedientes | https://ciudadrodrigo.sedelectronica.es/expedientes | Requiere autenticación |

## WordPress — normativa urbanística (REST API)

Categorías scrapeadas vía `wp-json/wp/v2/posts?categories={id}`:

| ID | Slug | Posts | Uso |
|----|------|-------|-----|
| 152 | normativa-urbanistica-de-aplicacion-planeamiento | 32 | Proyectos (estudios detalle, planes especiales, …) |
| 154 | normativa-urbanistica-en-tramitacion-planeamiento | 5 | Proyectos en tramitación (modificaciones PGOU) |
| 153 | normativa-urbanistica-de-aplicacion-gestion | 8 | Proyectos gestión (sectores, urbanización) |
| 155 | normativa-urbanistica-en-tramitacion-gestion | 0 | Vacía |
| 151 | urbanismo-autorizaciones-de-uso-excepcional | 77 | Licencias (autorizaciones suelo rústico) |

Cada post expone `title.rendered`, `date`, `link` (página con documentos PDF).

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Coín, Brunete, Humanes.
- **Listado:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** enlace `preview-document/{uuid}`.
- **Paginación:** AJAX Wicket («Mostrar más»); adapter parsea primera página (~10 filas).
- **Contenido actual (jul 2026):** mayoría empleo/contratación; filas urbanísticas esporádicas.

## Licencias de obra

- No hay dataset público de concesiones obra mayor/menor con coordenadas.
- **Autorizaciones uso excepcional:** 77 posts WordPress (categoría 151) con título, fecha y enlace.
- **Informes anuales:** estadísticas agregadas (346 licencias en 2023) en PDF, sin detalle por expediente.
- **Trámites:** formularios en web (`Solicitud de Licencia Urbanística de Obras`, declaración responsable obras menores).

## Proyectos / planeamiento

- **WP categorías planeamiento/gestión:** 45 posts con títulos de estudios de detalle, modificaciones PGOU, proyectos de actuación sectorial.
- **PGOU:** página con 65 PDFs (planos, ordenanzas, documentos por sector).
- **Informes seguimiento:** 13 PDFs anuales (2012–2024).
- **Tablón:** anuncios BOP/BOCYL de planeamiento cuando se publican.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - No hay visor urbanístico público del ayuntamiento (ArcGIS/GeoJSON).
  - PGOU publicado como PDF estático sin georreferencia embebida.
  - Junta CyL / Diputación Salamanca publica planeamiento en datos abiertos provinciales (XLSX/CSV), sin enlace a expedientes del tablón.
- **Estrategia:** sin WFS/ArcGIS REST enlazable por código de expediente; el orquestador aplicará centroide municipio + jitter.
- **Limitaciones:**
  - Documentos PDF sin coordenadas.
  - Tablón sin geometría.
  - Consulta expedientes requiere login.

## Limitaciones generales

- Sede `/dossier` y home con redirect loop (usar `/board/` directamente con `insecure_ssl`).
- Tablón paginado AJAX (solo primera página).
- Sin geometría por expediente.
- Licencias individuales de obra no listadas; solo autorizaciones uso excepcional y estadísticas en informes.

## Adapter implementado

- `municipio.adapters.ciudad_rodrigo:CiudadRodrigoAyuntamientoAdapter`
- Fuentes: WP REST (categorías urbanismo) + PGOU PDFs + informes anuales + tablón sede + páginas trámites.
- IDs: `ciudad-rodrigo-{lic|proy}-{sha256[:14]}`.
