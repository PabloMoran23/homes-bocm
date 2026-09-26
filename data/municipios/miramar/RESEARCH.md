# Miramar — investigación portal ayuntamiento

Municipio costero de la Safor (Valencia). INE **46154**.

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web oficial | https://ajumiramar.org | WordPress (tema Motif), bilingüe valenciano/castellano |
| Urbanismo | https://ajumiramar.org/ajuntament/serveis/urbanisme/ | Servicio de urbanismo, enlaces a trámites |
| PGOU | https://ajumiramar.org/ajuntament/plans-municipals/pgou/ | Plan General + subpáginas (planos, normas, modificaciones) |
| Trámites | https://ajumiramar.org/ajuntament/sollicituds/ | Tabla U1–U10 urbanismo con enlaces a sede |
| Sede electrónica | https://miramar.sedelectronica.es | espublico gestiona (Wicket) |
| Tablón | https://miramar.sedelectronica.es/board/ | Edictos HTML tabla `class_name` |
| Catálogo trámites | https://miramar.sedelectronica.es/dossier/.0 | ~15 trámites urbanismo/licencias (U1–U10, etc.) |
| Edictos web | https://ajumiramar.org/ajuntament/tauler-danuncis/edictes/ | Tablón municipal (poco urbanismo reciente) |

## Cómo se listan expedientes / proyectos

1. **PGOU (WordPress):** páginas estáticas con PDFs embebidos (`wp-content/uploads/…pdf`) en planols-pgou, normas estructurales/detalladas y modificaciones.
2. **Tablón sede:** tabla HTML con columnas Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha. Categoría «Urbanismo» incluye planos PGOU (2012) y ordenanza vados (2015).
3. **ICV WFS:** inventario estatal de sectores SU/SUZ con polígonos para Miramar (SECTOR 1–5, UE-1/2, AIS 1–2, IN-2).

No hay visor urbanístico propio ni API JSON de expedientes. La consulta de expedientes (`/expedientes`) requiere certificado digital.

## Cómo se publican licencias

- **Catálogo sede** (`/dossier/.0`): trámites informativos U1 (obra menor), U2 (obra mayor), U6–U8 (ocupación), U9 (compatibilidad), U10 (segregación), etc. Sin listado histórico de concesiones.
- **Tablón:** edictos puntuales (p. ej. «Licencias de Ocupación» para mercado estival — no licencias de obra).
- **Web sollicituds:** documentación descargable + enlace tramitación electrónica.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Capa: `ms:InventarioSuSuz`
  - Filtro: `cod_ine_mun=46154`
  - Campos: `pp`, `ue`, `clasificacion`, `f_aprob`, geometría GML Polygon
- **Estrategia:** paginar WFS (`STARTINDEX` 0–9000, count=200), filtrar por INE; enriquecer filas de tablón/PDF por coincidencia de token sector (SECTOR N, UE-N, AIS N).
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→polígono.
  - Tablón y PDFs PGOU no llevan coordenadas.
  - WFS requiere escaneo completo (~8.6k features) para localizar los ~10 sectores de Miramar.
  - `/dossier` sin cookie jar puede redirigir/timeout; el adapter usa sesión SSL.

## Limitaciones generales

- Sin dataset abierto de licencias concedidas (solo trámites y edictos).
- Portal transparencia sede sin carpeta urbanismo pública identificada.
- Contenido web mayoritariamente en valenciano; regex bilingüe en adapter.
