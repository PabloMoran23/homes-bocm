# Mutxamel — investigación portal ayuntamiento

**Municipio:** Mutxamel (Alicante, Comunitat Valenciana)  
**Slug:** `mutxamel`  
**Boletín:** DOGV (`dogv`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://ayto.mutxamel.org | **Operativa** — WordPress (W3 Total Cache, GTranslate) |
| Urbanismo | https://ayto.mutxamel.org/area/urbanismo/ | Información de contacto; sin listado de expedientes |
| Transparencia — Obras y urbanismo | https://ayto.mutxamel.org/area/transparencia/obras-urbanismo-y-medio-ambiente/ | **Operativa** — M.P. nº 37 NN.SS. Río Park, convenios |
| Transparencia — Normativa / audiencia | https://ayto.mutxamel.org/area/transparencia/normativa-y-relevancia-juridica/ | **Operativa** — PDFs IP, edictos licencia ambiental, consultas |
| Catálogo procedimientos | https://ayto.mutxamel.org/area/sede-electronica/catalogo-de-procedimientos/ | ZIP/formularios (SE015 Obras y Urbanismo, OF licencias) |
| Sede electrónica | https://sedeelectronica.mutxamel.org/eAdmin/Sede.do | **Operativa** — plataforma eAdmin (no espublico gestiona) |
| Tablón de anuncios | https://sedeelectronica.mutxamel.org/eAdmin/Tablon.do?action=verAnuncios | **Operativa** — ~36 anuncios HTML (mayoría RRHH) |
| Governalia | https://governalia.com/launch/mutxamel | Trámites electrónicos |
| Registro planeamiento GVA | https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/2 ALICANTE/03090 MUTXAMEL/ | Índice PG / PD y documentación |
| Textos consolidados NN.SS. | https://mediambient.gva.es/auto/urbanismo/Textos_consolidados/.../Mutxamel/ | PDF normas urbanísticas (nov 2025) |

## Cómo se listan expedientes

- **Planeamiento / IP:** principalmente en **transparencia** (enlaces a PDFs en `wp-content/uploads`) y noticias sobre M.P. 37 Río Park; no hay visor municipal de expedientes.
- **Tablón eAdmin:** tabla HTML con `Tablon.do?action=verAnuncio&id=…` y documentos `ValidarDocumento.do`; contenido actual muy orientado a RRHH y cobranza.
- **Licencias:** no hay dataset de concesiones; impresos (`oflicurb.pdf`, `Obras.zip`) y trámites vía Governalia/sede.
- **CMS:** WordPress; sin API pública estructurada para urbanismo (scrape de HTML/PDF).

## Licencias de obra

- Sin listado público de licencias concedidas (coordenadas).
- Edicto de **licencia ambiental** (taller reparación vehículos) en transparencia (`UR_edicto_licencia_ambiental_…pdf`).
- Trámites: catálogo SE015 (Obras.zip), ordenanza fiscal licencias urbanísticas, Governalia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `InventarioSuSuz`: `https://terramapas.icv.gva.es/0702_Planeamiento` — campo `cod_ine_mun=03090`, geometría en GeoJSON (`EPSG:4326`). ~44 polígonos (sectores SU/SUZ, UE, Río Park, etc.).
  - Visor GVA: `https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz`
- **Estrategia:** el adapter pagina el WFS (filtro cliente por `cod_ine_mun`) y asigna `geom_geojson` a cada ámbito ICV; enriquecimiento por coincidencia de título en filas de transparencia/tablón.
- **Limitaciones:** el WFS no admite `CQL_FILTER` fiable por municipio (hay que escanear con parada por rachas vacías); no hay enlace expediente↔polígono en el tablón; licencias sin geometría.

## Limitaciones generales

- Sede eAdmin distinta de espublico gestiona (`/board/` no existe).
- Tablón con poco contenido urbanístico en el momento de la investigación.
- Consulta de expedientes en sede requiere registro/login.
- WFS ICV: escaneo costoso (~8k features regionales para localizar 44 de Mutxamel).

## Adapter implementado

- `municipio.adapters.mutxamel:MutxamelAyuntamientoAdapter`
- Fuentes: tablón eAdmin + transparencia/catálogo WP + registro GVA + ICV WFS.
- IDs: `mutxamel-lic-*` / `mutxamel-proy-*` (sha256[:14]).
