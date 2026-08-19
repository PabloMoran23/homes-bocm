# Gijón — investigación portal ayuntamiento

Municipio: **Gijón** (`gijon`) — Asturias / provincia Gijón  
Boletín: BOPA (`boletin_source_id: bopa`, 7 entradas históricas)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Sede electrónica | https://sedeelectronica.gijon.es | TAO — urbanismo, licencias, catálogo trámites |
| Urbanismo (sede) | `PAGE_CODE=SEDE_URBANISMO` | Instrumentos planeamiento, gestión, info pública |
| Licencias (sede) | `PAGE_CODE=SEDE_URBANISMO_LICENCIAS` | Catálogo TECREA (11 trámites) |
| Info pública detalle | `PAGE_CODE=SEDE_URB_PLANEAMIENTO_INFOPUB_DETALLE&DBOID=...` | Estudios de detalle en trámite |
| Web municipal | https://www.gijon.es | SPA Angular — no listado scrapeable |
| Urbanismo legacy | http://urbanismo.gijon.es | Redirige / enlaces a sede |
| RPGUR (Principado) | https://www54.asturias.es/rpgur/action/publico/welcome | Registro planeamiento |
| Consulta RPGUR Gijón | `busquedaConsulta?method=listPublico&idConcejo=24&estado=V` | ~300 instrumentos vigentes (HTML paginado) |
| Detalle instrumento | `gestionConsulta?method=retrieve&idInstrumento=N` | Metadatos, fechas BOPA |
| Visor urbanístico | https://sigvisor.asturias.es/visorurbanismo | Visor SIG (nueva versión 2026) |
| Visor legacy | http://visorrpgur.asturias.es:8092/Visor_Urbanismo_RPGUR/ | Mapa interactivo HTML/JS |

## Cómo se listan expedientes / proyectos

1. **RPGUR (fuente principal):** GET a `busquedaConsulta?method=listPublico` con `idConcejo=24` (GIJON). Tabla HTML paginada (15/página, ~300 vigentes). Cada fila enlaza a detalle con `idInstrumento`. Campos: ámbito, clasificación (General/Desarrollo/Gestión), denominación, expediente, estado.

2. **Sede TAO — información pública:** La página `SEDE_URBANISMO` embebe metadata JSON en `metadata_GJ_META_URBANISMO_PLANEAMIENTO_INFOPUBLICA` con filas DataTable (expediente, asunto, enlace detalle). Actualmente 3 estudios de detalle en trámite.

3. **Sede TAO — instrumentos planeamiento/gestión:** Tablas `GJ_META_URBANISMO_PLANEAMIENTO_INSTRUMENTOS` y `GESTION` existen pero con `rows:[]` vacíos en el HTML servido (posible carga dinámica no replicada sin sesión).

4. **Web www.gijon.es:** Angular SPA con API `api.gijon.es`; sin listado HTML estático de expedientes.

## Cómo se publican licencias

- No hay tablón público de licencias concedidas con datos estructurados.
- La sede publica **catálogo de trámites TECREA** (declaración responsable, comunicación previa, licencia ocupación, etc.) — páginas informativas sin listado de concesiones.
- El adapter devuelve trámites informativos desde `SEDE_URBANISMO_LICENCIAS`.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer: `http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows`
  - Capa: `n01_AMBITO_INSTRUMENTO_CONSULTAS`
  - Filtro: `id_municipio=33024` (44 features)
  - Campo enlace: `Id._Inventario_Registro_Urbanístico` → `idInstrumento` RPGUR
  - `srsName=EPSG:4326` para GeoJSON WGS84
- **Estrategia:** Precargar WFS por municipio; al procesar cada instrumento RPGUR, si `idInstrumento` coincide con `Id._Inventario_Registro_Urbanístico`, adjuntar `geom_geojson`.
- **Limitaciones:**
  - Solo 44 de ~300 instrumentos tienen polígono en WFS público.
  - PGO y modificaciones puntuales mayores sí; estudios de detalle y gestión menor no siempre enlazados.
  - Visor SIG nuevo (`sigvisor.asturias.es`) requiere JS; sin API REST directa por expediente.
  - Licencias sin georreferencia pública.

## Limitaciones generales

- RPGUR codificación ISO-8859-1; paginación hasta 25 páginas (~300 registros).
- Host legacy `rpgur.asturias.es` no resuelve DNS — usar `www54.asturias.es`.
- Sede TAO embebe datos en metadata JS (no API JSON separada).
- ~300 instrumentos RPGUR implican ~2 min de scrape con delay 0.35s por detalle.
- Sin dataset JSON/API en web municipal Angular.
