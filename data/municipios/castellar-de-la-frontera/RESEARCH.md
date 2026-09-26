# Castellar de la Frontera — investigación portal ayuntamiento

**Municipio:** Castellar de la Frontera (Cádiz, Andalucía)  
**Slug:** `castellar-de-la-frontera`  
**BOJA:** 2 entradas en histórico regional

## URLs base y páginas semilla

| Recurso | URL | Estado |
|---------|-----|--------|
| Web corporativa | https://www.castellardelafrontera.es | Operativa (Joomla + YooTheme) |
| Ordenanzas | https://www.castellardelafrontera.es/ayuntamiento/ordenanzas | Operativa — categorías municipales/fiscales |
| PBOM (Diputación Cádiz) | https://www.dipucadiz.es/.../castellar/pbom/ | Operativa — repositorio PBOM + PDFs cartografía |
| Sede electrónica | https://castellardelafrontera.sedelectronica.es | Operativa — espublico gestiona |
| Tablón de anuncios | https://castellardelafrontera.sedelectronica.es/board/ | Operativa — tabla HTML Wicket |
| Transparencia sede | https://castellardelafrontera.sedelectronica.es/transparency/ | Carpeta «7. URBANISMO…» (88 docs) vía AJAX |
| Transparencia Diputación | https://gobiernoabierto.dipucadiz.es/...entidadId=403 | Catálogo indicadores (entidad 403) |
| Consulta expedientes | https://castellardelafrontera.sedelectronica.es/expedientes | Requiere autenticación |
| Planeamiento vigente (SITUA) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Visor NN.SS. regional |

**Nota:** `castellardelafrontera.es` (sin www) redirige a `www`. No confundir con `castellar.es` (Jaén).

## Cómo se listan expedientes / proyectos

1. **Tablón sede (`/board/`):** tabla HTML con columnas Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha. Procedimiento «Licencias Urbanísticas» agrupa anuncios de licencias y actuaciones. Enlaces a `/preview-document/{uuid}` cuando disponibles. Paginación Wicket AJAX (solo primera página scrapeada).
2. **PBOM Diputación Cádiz:** portal de participación ciudadana del PBOM con PDFs cartográficos (`Hoja_1075-*.pdf`), memoria y documentación de tramitación. Enlace desde web municipal.
3. **Ordenanzas web:** categorías Joomla con PDFs de ordenanzas municipales (incl. urbanismo si publicadas).
4. **Transparencia sede:** carpeta «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» con 88 documentos; navegación por subcarpetas requiere peticiones AJAX Wicket.

## Licencias de obra

- **No hay listado público histórico** de licencias concedidas.
- El tablón publica anuncios puntuales bajo «Licencias Urbanísticas» (p. ej. AT-15003-22 anuncio IP).
- Trámites informativos en `/dossier` y consulta de expedientes autenticada.
- Adapter devuelve páginas informativas de referencia + edictos del tablón si aparecen.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - SITUA Junta de Andalucía (`ws132.juntadeandalucia.es/situadifusion`) — visor PGOU/NN.SS. municipal sin API REST/WFS enlazable a código de expediente.
  - PBOM Diputación — PDFs cartográficos (`Hoja_1075-*.pdf`) sin servicio GIS descargable.
  - Sede espublico — documentos PDF sin coordenadas ni visor integrado.
  - No se encontró visor ArcGIS/WFS municipal público.
- **Estrategia:** el orquestador aplicará centroide municipal + jitter (`centroid: [36.3177, -5.4541]`).
- **Limitaciones:** planeamiento publicado como PDF; sin ref. catastral sistemática en listados HTML; transparencia AJAX no accesible sin sesión Wicket.

## Limitaciones generales

- Tablón paginado; adapter captura página actual (~5 filas visibles).
- Transparencia sede requiere Wicket AJAX para subcarpetas (88 docs).
- Licencias históricas no publicadas en web abierta.
- PBOM en tramitación (sustituye NN.SS. vigentes de 2000/2013).
- SSL sede: certificado válido; `insecure_ssl: true` por consistencia con otros adapters espublico.

## Adapter

- `municipio.adapters.castellar_de_la_frontera:CastellarDeLaFronteraAyuntamientoAdapter`
- IDs: `castellar-de-la-frontera-lic-*` / `castellar-de-la-frontera-proy-*` (sha256[:14]).
