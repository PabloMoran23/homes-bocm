# Barbate — investigación portal ayuntamiento

**Municipio:** Barbate (Cádiz, Andalucía)  
**Slug:** `barbate`  
**BOJA:** 1 entrada en histórico regional  
**INE:** 11007

## URLs base y páginas semilla

| Recurso | URL | Estado |
|---------|-----|--------|
| Web corporativa | https://www.barbate.es | Operativa (Joomla + YOOtheme + Phoca Download, EPICSA/Dip. Cádiz) |
| Urbanismo | https://www.barbate.es/el-ayuntamiento/urbanismo | Operativa — expedientes PGOU/PGOM, UE, convenios |
| Sede electrónica | https://barbate.sedelectronica.es | Operativa — espublico gestiona |
| Tablón de anuncios | https://barbate.sedelectronica.es/board/ | Operativa — tabla HTML Wicket |
| Transparencia | https://barbate.sedelectronica.es/transparency | Carpeta urbanismo vía AJAX Wicket |
| Consulta expedientes | https://barbate.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |
| PGOU Junta (SITUA) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Visor PGOU regional (sin API por expediente) |

**Nota:** La web requiere User-Agent de navegador; peticiones sin UA pueden recibir 403 WAF.

## Cómo se listan expedientes / proyectos

1. **Tablón sede (`/board/`):** tabla HTML con columnas Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha. Incluye anuncios de planeamiento (p. ej. aprobación plan de trabajo equipo redactor PGOM, expediente 9665/2026) y contrataciones con componente de obra. Enlaces a `/preview-document/{uuid}`. Paginación «Mostrar más» vía Wicket AJAX (solo primera página scrapeada).
2. **Web urbanismo:** secciones Joomla con Phoca Download (`?download=ID:slug`) y PDFs estáticos en `/images/Ficheros/`. Expedientes documentados:
   - Modificación puntual PGOU reprogramación suelo urbanizable (~20 docs)
   - PGOU (subsecciones corrección errores autonómica)
   - PGOU Caños de Meca zona hotelera
   - UE B-7 El Zapal, UE B-17 El Jarillo
   - Plan Municipal de Vivienda y Suelo 2018-2023
   - Innovación Zaharatuna, Infoca, Hecamo, convenio Zahara
3. **Transparencia sede:** documentos urbanismo en carpetas Wicket — no replicado en adapter.

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
  - No se encontró visor ArcGIS/WFS municipal público.
- **Estrategia:** el orquestador aplicará centroide municipal + jitter (`centroid: [36.1925, -5.9219]`).
- **Limitaciones:** planeamiento publicado como PDF; sin ref. catastral sistemática en listados HTML; transparencia AJAX no accesible sin sesión Wicket.

## Limitaciones generales

- Tablón paginado (~10 filas visibles); adapter captura página actual.
- Web municipal bloquea bots sin User-Agent (403).
- Transparencia sede requiere Wicket AJAX para subcarpetas.
- Licencias históricas no publicadas en web abierta.
- `insecure_ssl: true` por consistencia con otros adapters espublico.

## Adapter

- `municipio.adapters.barbate:BarbateAyuntamientoAdapter`
- IDs: `barbate-lic-*` / `barbate-proy-*` (sha256[:14]).
