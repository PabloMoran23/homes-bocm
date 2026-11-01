# Alzira — investigación portal ayuntamiento

## Fuentes base

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://alzira.es | WordPress (Insuit); noticias y documentación urbanismo |
| Urbanisme | https://alzira.es/serveis-municipals/urbanisme-i-infraestructures/ | Hub planeamiento, ordenanzas, estudios |
| Planejament | https://alzira.es/serveis-municipals/urbanisme-i-infraestructures/planejament-i-informacio-urbanistica/ | Enlace visor gvSIG |
| Sede electrónica | https://sedeelectronica.alzira.es/PortalCiudadano/ | inDenova: catálogo trámites, tablón edictos |
| Tablón edictos | https://sedeelectronica.alzira.es/PortalCiudadano/tablonEdictos.do?formAction=btShowInfoTablonEdictos | Listado vía formulario/JS (sin tabla HTML en GET) |
| Registro GVA | https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/4%20VALENCIA/46017%20ALZIRA/ | PG / planeamiento diferido (PDFs) |
| WP REST | https://alzira.es/wp-json/wp/v2/posts?categories=1632 | Categoría «Àrea d'Urbanisme…» (~80 entradas) |

## Listado de expedientes / proyectos

- **Noticias urbanismo:** WP REST `categories=1632` (y `1635` planejament); filtro por palabras clave (normes urbanístiques, expropiació, minimització impacte, etc.).
- **Documentos:** PDFs en páginas de ordenanzas y hub urbanismo; índice autonómico GVA con planes generales y diferidos.
- **Sede:** catálogo de trámites por sección (`seccion=27` urbanismo, `46` licencias); tablón de edictos no expone filas en HTML estático (requiere POST/JS del portal).

## Licencias

- No hay listado público de concesiones (como Sedipualba RSS).
- Trámites informativos en sede (declaración responsable quemas `t=3317`, catálogo licencias/urbanismo).
- Ordenanzas y tasas de construcción en web (`ORDENANZA-FOTOVOLTAICAS`, impost construccions).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Visor municipal gvSIG Online: https://alzira.gvsigonline.com/gvsigonline/core/load/planeamiento/ (capas WMS internas; sin API REST pública documentada para expediente).
  - ICV WFS `ms:InventarioSuSuz` / `Planeamiento.Zonificacion` en https://terramapas.icv.gva.es/0702_Planeamiento — filtro `cod_ine_mun=46017` (~31 polígonos SU/SUZ, escaneo por `startIndex`).
- **Estrategia:** ingestar sectores ICV como proyectos con `geom_geojson`; intentar cruce por tokens UE/PPI en títulos de noticias.
- **Limitaciones:** tablón sede y expedientes de licencia sin geometría enlazable; gvSIG no expone query por código de expediente sin autenticación/sesión de proyecto.
