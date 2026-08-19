# Arcos de la Frontera — investigación portal ayuntamiento

**Municipio:** Arcos de la Frontera (Cádiz, Andalucía)  
**Slug:** `arcos-de-la-frontera`  
**Boletín:** BOJA (`boja`, 6 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://arcosdelafrontera.es | **Operativa** — WordPress Avada + weDocs |
| Delegación Urbanismo | https://arcosdelafrontera.es/delegaciones/delegacion-de-urbanismo/ | Menú planeamiento, PGOU, trámites |
| Planeamiento en tramitación | https://arcosdelafrontera.es/docs/planeamiento-en-tramitacion/ | weDocs — Mod. 61 y Mod. 63 PGOU |
| Portal PGOU | https://pgouarcos.es/ | **Operativa** — WP REST; 108+ PDFs en `/documentos/` |
| Participación PGOM | https://planificaarcos.es/ | **Inaccesible** desde CI (respuesta vacía) |
| Sede electrónica | https://sedelectronicaarcos.blcloud.es | **Operativa** — plataforma blcloud (no espublico) |
| Catálogo trámites | https://sedelectronicaarcos.blcloud.es/sede/catalogoTramites.do | Sección URBANISMO con trámites electrónicos |
| Trámites urbanísticos | https://arcosdelafrontera.es/iii-tramites-urbanisticos/ | Guía PDF editable + procedimientos |
| Declaraciones / comunicaciones | https://arcosdelafrontera.es/declaraciones-responsables-y-comunicaciones-previas/ | Formularios B01–B07 |

## Proyectos / planeamiento

### weDocs (arcosdelafrontera.es)

- **CMS:** WordPress + plugin weDocs (`/docs/`).
- **Árbol relevante:**
  - `planeamiento-en-tramitacion` (id 8311): Mod. nº61 PGOU (EAE + documento urbanístico), Mod. puntual nº63 (memoria, planos, anexos).
  - `urbanismo` (id 6593): Plan Municipal de Vivienda y Suelo (PMVS) con PDFs en `/wp-content/uploads/PMVS/`.
- **API:** `GET /wp-json/wp/v2/docs?parent={id}` — recorrido recursivo; PDFs embebidos en HTML de hojas (no siempre en REST `content`).

### pgouarcos.es

- **REST:** `https://pgouarcos.es/index.php?rest_route=/wp/v2/pages/{77,100,169}`.
- **Contenido:** PGOU 95 (expediente, memoria, NNUU, PAU, planos), adaptación LOUA, Plan Especial Conjunto Histórico, avance revisión PGOU (70 PDFs), regularización asentamientos.
- **Formato:** enlaces relativos `/documentos/.../*.pdf` parseados del HTML de página.

### Noticias municipales

- Posts WP sobre PGOM/POU, exposición pública avance planeamiento (2025–2026).
- API: `/wp-json/wp/v2/posts?search=planeamiento`.

## Licencias de obra

- **No hay** dataset público de licencias concedidas con coordenadas ni tablón de anuncios tipo espublico `/board/`.
- **Trámites informativos:**
  - Web: licencias obra mayor/menor, comunicaciones previas, declaraciones responsables (PDF editables).
  - Sede blcloud: «Solicitud General de Urbanismo» y trámites del bloque URBANISMO (presentación electrónica con login).
- Consulta de expedientes (`consultaExpedientes.do`) requiere identificación.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - **VITUA / SITUA** (Junta de Andalucía): planeamiento vigente por municipio; sin campo expediente del ayuntamiento ni API REST enlazable por código de expediente.
  - **pgouarcos.es**: documentación PDF/planos sin servicio ArcGIS/WFS público.
  - **planificaarcos.es**: portal participativo PGOM; sin visor GIS accesible desde CI.
  - Sede blcloud: sin visor cartográfico público.
- **Estrategia:** documentación urbanística en PDF; el orquestador aplicará centroide municipio + jitter.
- **Limitaciones:** sin WFS/GeoJSON por expediente; tablón de edictos no expuesto en HTML scrapeable.

## Limitaciones generales

- Sede blcloud distinta de espublico gestiona — sin `/board/` público.
- weDocs: PDFs en hojas hoja vía HTML, no siempre en REST.
- planificaarcos.es no responde en entorno CI.
- Consulta estado expedientes requiere autenticación.

## Adapter implementado

- `municipio.adapters.arcos_de_la_frontera:ArcosDeLaFronteraAyuntamientoAdapter`
- Fuentes: weDocs + pgouarcos REST + posts WP + sede trámites urbanismo + páginas informativas.
- IDs: `arcos-de-la-frontera-lic-*` / `arcos-de-la-frontera-proy-*` (sha256[:14]).
