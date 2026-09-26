# Los Barrios — investigación portal ayuntamiento

Municipio: **Los Barrios** (`los-barrios`), provincia Cádiz, Andalucía. Boletín: BOJA (2 entradas).

## URLs base y páginas semilla

| Fuente | URL | Tipo |
|--------|-----|------|
| Web municipal | https://losbarrios.es | WordPress + Visual Composer (Avada) |
| Portal transparencia urbanismo | https://losbarrios.es/portal-de-transparencia/urbanismo/ | Índice urbanismo |
| Proyectos urbanismo | https://losbarrios.es/portal-de-transparencia/proyectos-de-urbanismo/ | Enlaces a aprobaciones |
| Estudios de detalle | https://losbarrios.es/portal-de-transparencia/planeamiento-estudio-de-detalles/ | Índice ED |
| Info pública activa | https://losbarrios.es/portal-de-transparencia/otros-tramites-en-informacion-publica/ | Lista dinámica (sidebar) |
| PGOU | https://losbarrios.es/portal-de-transparencia/urbanismo-obras-publicas-y-medio-ambiental/plan-general-de-ordenacion-urbana-pgou/ | Documentación PGOU |
| Urbanismo consistorio | https://losbarrios.es/el-consistorio/servicios-publicos-basicos/urbanismo/ | Sección servicios |
| Sede electrónica | https://losbarrios.sedelectronica.es | espublico gestiona (**no operativa**) |
| SITUA Junta Andalucía | https://ws132.juntadeandalucia.es/situadifusion/ | Planeamiento regional digitalizado |

**Nota:** `losbarrios.sedelectronica.es`, `los-barrios.sedelectronica.es` y `barrios.sedelectronica.es` devuelven página genérica «Por favor, seleccione su sede electrónica» en `/board/` y `/dossier`. La sede no expone tablón ni catálogo de trámites de forma pública.

## Expedientes / proyectos

1. **Portal transparencia (WordPress REST API):** Páginas con títulos de aprobaciones urbanísticas (estudios de detalle API-12/14, modificaciones PGOU Guadacorte Sur, proyectos de actuación, plan parcial SUS 7/8, PMVS, etc.). Contenido en HTML con enlaces a PDFs en `/wp-content/uploads/` y ocasionalmente Google Drive.
2. **Índices semilla:** Las páginas índice (`proyectos-de-urbanismo`, `planeamiento-estudio-de-detalles`, `otros-tramites-en-informacion-publica`) enlazan a subpáginas de expedientes individuales.
3. **PGOU:** Documentación en transparencia (resumen ejecutivo PDF 2018, documento cumplimiento aprobación definitiva).
4. **SITUA:** Consulta regional de planeamiento digitalizado (raster escaneado); no listado de expedientes municipales individuales ni geometría vectorial por expediente.
5. **Sin visor urbanístico municipal** ni datos abiertos GIS del ayuntamiento.

## Licencias de obra

- **Sin listado histórico** de licencias concedidas en portal público.
- Sede espublico no accesible (página indeterminada).
- Transparencia publica trámites puntuales de licencia (ej. LAP 69/23 — licencia de apertura en info pública).
- Tramitación urbanismo: https://losbarrios.es/el-consistorio/servicios-publicos-basicos/urbanismo/tramitacion-de-la-delegacion-de-urbanismo/
- Adapter devuelve páginas informativas de trámites + licencias publicadas en transparencia (patrón Pozuelo/Bornos).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - Web municipal: sin visor ArcGIS, WFS ni GeoJSON en datos abiertos.
  - SITUA Junta de Andalucía: planeamiento digitalizado raster; sin query por código de expediente municipal ni geometría vectorial descargable.
  - Portal transparencia: solo PDFs y enlaces externos (Drive); sin coordenadas ni polígonos.
  - Sede espublico: no accesible.
- **Estrategia:** No aplicable; orquestador usará centroide municipio + jitter.
- **Limitaciones:** Sin visor urbanístico municipal; documentos de planeamiento solo en PDF; sectores (API-12, SUS 7/8, Guadacorte Sur) mencionados en título pero sin GIS enlazable.

## Limitaciones técnicas

- Sede espublico gestiona configurada pero no resuelve municipio (página «indeterminada»).
- WordPress REST API (`/wp-json/wp/v2/pages`) accesible sin autenticación.
- Contenido transparencia en sidebar dinámico (`avada-custom-sidebar-portaldetransparencia`); algunos enlaces solo en HTML renderizado.
- Certificados SSL válidos; no requiere `insecure_ssl`.
