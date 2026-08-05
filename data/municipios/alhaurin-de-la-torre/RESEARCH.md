# Alhaurín de la Torre — investigación portal ayuntamiento

**Municipio:** Alhaurín de la Torre (Málaga, Andalucía)  
**Slug:** `alhaurin-de-la-torre`  
**Boletín:** BOJA (`boja`, 8 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://alhaurindelatorre.es | **Operativa** — WordPress (`alhaurin-theme`) |
| Urbanismo (área) | https://alhaurindelatorre.es/category/areas-municipales/urbanismo-obras-e-infraestructura-viaria/ | **Operativa** |
| Planeamiento vigente | https://alhaurindelatorre.es/category/areas-municipales/urbanismo-obras-e-infraestructura-viaria/planeamiento-urbanistico/ | **Operativa** — PGOU adaptación LOUA, calificación |
| Trámites urbanismo | https://alhaurindelatorre.es/category/areas-municipales/urbanismo-obras-e-infraestructura-viaria/tramites-de-urbanismo/ | **Operativa** — formularios licencias |
| Obras ejecutadas | https://alhaurindelatorre.es/category/areas-municipales/urbanismo-obras-e-infraestructura-viaria/obras-ejecutadas/ | **Operativa** — fichas obra con PDF |
| Planimetría 1:5000 | https://alhaurindelatorre.es/planimetria-escala-1-5000/ | **Operativa** — mosaico PDF por cuadrícula |
| Sede electrónica | https://sede.alhaurindelatorre.es | **Operativa** — SWAL (ASP.NET WebForms) |
| Tablón anuncios | Sede → lateral «Tablón de Anuncios» → «Acceder desde aquí» | **Operativa** — grid `_gridDetalle` con paginación |
| Transparencia | http://transparencia.alhaurindelatorre.es | Portal oGov (contratos/presupuesto); sin carpeta urbanismo scrapeable |
| Sugerencias PGOM | https://alhaurindelatorre.es/sugerencias-al-pgom/ | Trámite sede (participación ciudadana PGOM) |

## Cómo se listan expedientes / planeamiento

### WordPress (REST API + HTML)

- **CMS:** WordPress con categorías hijas de urbanismo (IDs 89–94, 177).
- **REST:** `GET /wp-json/wp/v2/posts?categories={id}&per_page=100` — sin autenticación.
- **Planeamiento (cat. 91):** entradas PGOU adaptación LOUA y calificación urbanística con decenas de PDFs en `/wp-content/uploads/attachments/`.
- **Obras (cat. 92–93):** fichas de obra pública (reurbanizaciones, infraestructura) con PDF adjunto.
- **Planimetría (cat. 90):** mosaicos interactivos que enlazan PDFs cartográficos (escala 1:2000 y 1:5000).
- **Trámites (cat. 89):** formularios PDF (licencias, vía pública); no son concesiones históricas.

### Tablón electrónico SWAL (sede)

- **Plataforma:** SWAL sede electrónica (`sede.alhaurindelatorre.es`), ASP.NET con `__doPostBack`.
- **Acceso:** menú lateral índice 3 → botón «Acceder desde aquí» (`ctl00$principal$lbAccion`).
- **Listado:** tabla `ctl00_principal__gridDetalle` con columnas fecha, entidad, nº edicto, descripción, enlace «Ver documento».
- **Paginación:** `ctl00$principal$miniBotoneraDetalle$lnkSiguiente` (~10 filas/página).
- **Contenido urbanístico:** escaso en primeras páginas (predominan RRHH, cobranza); bandos de obra ocasionales.
- **Notificaciones:** desde 2015 muchas notificaciones van al TEU/BOE (texto informativo en landing del tablón).

## Licencias de obra

- No hay dataset público de concesiones de licencia mayor/menor.
- Formularios informativos en WordPress (solicitud licencia, declaración responsable obra menor, vía pública).
- Trámites en sede: «Certificados Urbanísticos», catálogo trámites (requiere certificado digital).
- Bandos/edictos de obra pueden aparecer en tablón SWAL.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - Planimetría WordPress: PDFs cartográficos por cuadrícula (1:2000, 1:5000) sin GeoJSON/WFS ni enlace a expediente.
  - RPGUR Junta de Andalucía (`services8.arcgis.com/.../RPGUR/FeatureServer`): requiere token ArcGIS.
  - Portal transparencia oGov: visores de contratos/presupuesto, no planeamiento parcelario.
  - No hay visor urbanístico interactivo municipal (PGOM en redacción; participación vía sede).
- **Estrategia:** no hay query GIS por código de expediente; el orquestador usará centroide municipio + jitter.
- **Limitaciones:** PDFs sin georreferencia embebida; tablón sin coordenadas; sede sin API REST pública.

## Limitaciones generales

- Tablón SWAL requiere cadena de postbacks (sesión con `?key=`); el adapter parsea varias páginas.
- Poco contenido urbanístico reciente en tablón frente a RRHH/cobranza.
- Transparencia oGov no expone expedientes urbanísticos de forma scrapeable.
- Consulta de expedientes en sede requiere identificación Cl@ve/certificado.

## Adapter implementado

- `municipio.adapters.alhaurin_de_la_torre:AlhaurinDeLaTorreAyuntamientoAdapter`
- Fuentes: tablón SWAL + posts/PDFs WordPress (planeamiento, obras, planimetría) + páginas informativas trámites.
- IDs: `alhaurin-de-la-torre-lic-*` / `alhaurin-de-la-torre-proy-*` (sha256[:14]).
