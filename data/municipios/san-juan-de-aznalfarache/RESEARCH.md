# San Juan de Aznalfarache — investigación portal ayuntamiento

Municipio: **San Juan de Aznalfarache** (`san-juan-de-aznalfarache`) — Sevilla, Andalucía  
INE: **41047** | Boletín: **BOJA** (1 aviso histórico)

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal (OpenCMS INPRO) | https://www.sanjuandeaznalfarache.es/es/ |
| Área Urbanismo | https://www.sanjuandeaznalfarache.es/es/urbanismo/ |
| Planeamiento (redirect → sede transparencia) | https://www.sanjuandeaznalfarache.es/es/urbanismo/planeamiento-urbanistico |
| Declaraciones responsables / modelos | https://www.sanjuandeaznalfarache.es/es/urbanismo/declaraciones-responsables/ |
| Descarga documentos urbanismo | https://www.sanjuandeaznalfarache.es/es/ayuntamiento/descarga-de-documentos/ |
| Noticias urbanismo | https://www.sanjuandeaznalfarache.es/es/urbanismo/noticias/ |
| Tablón de anuncios web | https://www.sanjuandeaznalfarache.es/es/actualidad/tablon-de-anuncios/ |
| Tablón electrónico edictos (INPRO Dip.) | https://www.sanjuandeaznalfarache.es/es/ayuntamiento/tablon-electronico-de-edictos |
| Sede espublico gestiona | https://sanjuandeaznalfarache.sedelectronica.es |
| Tablón sede | https://sanjuandeaznalfarache.sedelectronica.es/board/ |
| Transparencia sede | https://sanjuandeaznalfarache.sedelectronica.es/transparency |
| Trámites (dossier) | https://sanjuandeaznalfarache.sedelectronica.es/dossier |
| LicytalPub Dip. Sevilla | https://portal.dipusevilla.es/LicytalPub/jsp/pub/index.faces?cif=P4108600J |
| Tablón INPRO Dip. Sevilla | https://portal.dipusevilla.es/tablon-1.0/do/entradaPublica?ine=41047 |
| SITUA (Junta Andalucía) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=41047 |

## CMS y listado de expedientes

- **Web:** OpenCMS INPRO (`es.inpro.opencms.*`). PDFs en `/export/sites/sanjuandeaznalfarache/.galleries/`. Noticias y eventos vía módulo listado (`pm-noticia`, `pm-evento`).
- **Planeamiento urbanístico:** enlace web redirige a la sede (sección transparencia **7. URBANISMO… / 7.1 PLANEAMIENTO URBANÍSTICO**, ~806 documentos en índice Wicket; descarga vía AJAX).
- **Sede:** espublico gestiona. Tablón `/board/` con filas HTML (`class_name`, `class_folderCode`, `class_folderName`, `class_dateFrom`). En la revisión predominan edictos administrativos (cobranza, BOP), sin licencias de obra recientes.
- **Tablón web municipal:** listado paginado de eventos/anuncios (`/es/actualidad/tablon-de-anuncios/`); algunos anuncios de infraestructura (Plan Sevilla 107).
- **Tablón Diputación:** INPRO en `portal.dipusevilla.es` con INE 41047; búsqueda POST interactiva.
- **Licencias concedidas:** portal provincial **LicytalPub** (CIF `P4108600J`); no hay dataset en web municipal.

## Licencias de obra

- No hay listado histórico público en sede (solo tablón de edictos recientes y modelos de declaración responsable en web).
- Trámites vía `/dossier` y consulta provincial LicytalPub.
- El adapter incluye filas informativas (tablón sede, trámites, LicytalPub, tablón Diputación) y licencias detectadas en tablón cuando aparecen.

## Proyectos / planeamiento

- **Instrumento general:** adaptación parcial de las Normas Subsidiarias a la LOUA (aprobación 2011; consulta SITUA).
- Documentación: PDFs de declaraciones responsables, comunicación previa, plan vivienda y suelo, registro demandantes.
- Transparencia sede: repositorio masivo de planeamiento (PDFs sin API).
- Noticias urbanismo (gasolinera Valparaíso, obras Emasesa, etc.) filtradas por categoría/regex.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:** sin visor urbanístico municipal ni ArcGIS/WFS en datos abiertos; SITUA/VITUA Junta (JSF, sin WFS por expediente); transparencia sede y tablones solo PDF/HTML.
- **Estrategia:** orquestador aplicará centroide municipal `[37.3583, -6.0374]` + jitter vía `geocode`.
- **Limitaciones:** transparencia sede vía AJAX Wicket; tablón Diputación requiere POST; planeamiento web redirige a sede.

## Limitaciones generales

- Histórico de licencias solo en LicytalPub (consulta interactiva).
- Consulta de expedientes en sede requiere autenticación (`/expedientes`).
- Tablón sede muestra ventana corta de anuncios (~10 filas).
