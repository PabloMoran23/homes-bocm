# Conil de la Frontera — investigación portal ayuntamiento

**Municipio:** Conil de la Frontera (Cádiz, Andalucía)  
**Slug:** `conil-de-la-frontera`  
**BOJA:** 4 entradas en histórico regional

## URLs base y páginas semilla

| Recurso | URL | Estado |
|---------|-----|--------|
| Web corporativa | https://www.conildelafrontera.es | Operativa (Joomla + Phoca Download) |
| Urbanismo | https://www.conildelafrontera.es/areas-y-servicios-municipales/urbanismo | Operativa — PDFs planeamiento |
| Sede electrónica | https://conil.sedelectronica.es | Operativa — espublico gestiona |
| Tablón de anuncios | https://conil.sedelectronica.es/board/ | Operativa — tabla HTML Wicket |
| Transparencia | https://conil.sedelectronica.es/transparency/ | Carpeta «7. URBANISMO…» (169 docs) vía AJAX |
| Consulta expedientes | https://conil.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |
| PGOU Junta (SITUA) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Visor PGOU regional (sin API por expediente) |

**Nota:** `www.conil.es` no resuelve; el dominio oficial es `conildelafrontera.es`.

## Cómo se listan expedientes / proyectos

1. **Tablón sede (`/board/`):** tabla HTML con columnas Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha. Categoría «Actuaciones Urbanísticas» agrupa edictos PGOU (modificaciones puntuales, avances, aprobaciones). Enlaces a `/preview-document/{uuid}`. Paginación «Mostrar más» vía Wicket AJAX (solo primera página scrapeada).
2. **Web urbanismo:** enlaces Phoca Download (`/component/phocadownload/category/20-urbanismo?download=…`) y PDFs estáticos en `conil.org/www/Urbanismo/`. Documentos de modificaciones PGOU (Barrio Nuevo-El Colorado, SLN/SLV, AO-27 CONISOL, reparcelaciones, PMVS).
3. **Transparencia sede:** carpeta «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» con 169 documentos; navegación por subcarpetas requiere peticiones AJAX Wicket — no replicado en adapter.

## Licencias de obra

- **No hay listado público** de licencias concedidas (ni decreto ni tablón dedicado).
- El tablón puede publicar edictos de licencia puntuales (filtro por regex).
- Trámites informativos en `/dossier` y consulta de expedientes autenticada.
- Adapter devuelve páginas informativas de referencia + edictos del tablón si aparecen.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - SITUA Junta de Andalucía (`ws132.juntadeandalucia.es/situadifusion`) — visor PGOU municipal sin API REST/WFS enlazable a código de expediente.
  - Web municipal — solo PDFs planimétricos sin servicio GIS.
  - Sede espublico — documentos PDF sin coordenadas ni visor integrado.
  - No se encontró visor ArcGIS/WFS municipal público (p. ej. `visorurbanistico.conil.es` no resuelve).
- **Estrategia:** el orquestador aplicará centroide municipal + jitter (`centroid: [36.2772, -6.0889]`).
- **Limitaciones:** planeamiento publicado como PDF; sin ref. catastral sistemática en listados HTML; transparencia AJAX no accesible sin sesión Wicket.

## Limitaciones generales

- Tablón paginado (10 filas visibles); adapter captura página actual.
- Transparencia sede requiere Wicket AJAX para subcarpetas.
- Licencias históricas no publicadas en web abierta.
- SSL sede: certificado válido; `insecure_ssl: true` por consistencia con otros adapters espublico.

## Adapter

- `municipio.adapters.conil_de_la_frontera:ConilDeLaFronteraAyuntamientoAdapter`
- IDs: `conil-de-la-frontera-lic-*` / `conil-de-la-frontera-proy-*` (sha256[:14]).
