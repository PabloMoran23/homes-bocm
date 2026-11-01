# San Martín del Rey Aurelio — investigación portal ayuntamiento

Municipio: **San Martín del Rey Aurelio** (`san-martin-del-rey-aurelio`) — Asturias / provincia San Martín del Rey Aurelio  
Boletín: BOPA (`boletin_source_id: bopa`, 1 entrada histórica)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.smra.org | Liferay DXP (main-responsive-theme) |
| Urbanismo | https://www.smra.org/urbanismo | Oficina técnica, contacto |
| Normativa urbanística | https://www.smra.org/normativa-urbanistica | Enlaces RPGUR, visor regional, PDF instrucciones planeamiento |
| Documentos en información pública | https://www.smra.org/documentos-en-informaci%C3%B3n-p%C3%BAblica | Carpetas Liferay (p. ej. modificación normas subsidiarias Leopoldo Alas Clarín, Choza) |
| Alegaciones / IP | https://www.smra.org/alegaciones-a-tramites-de-informacion-publica | Trámites de información pública |
| Normativa municipal | https://www.smra.org/normativa-municipal1 | Ordenanzas (algunas urbanísticas) |
| RPGUR (Principado) | https://www54.asturias.es/rpgur/action/publico/welcome | Registro planeamiento |
| Consulta RPGUR SMRA | `busquedaConsulta?method=listPublico&idConcejo=46&estado=V` | Instrumentos vigentes (tabla HTML; INE 33046) |
| Visor RPGUR legacy | http://visorrpgur.asturias.es:8092/Visor_Urbanismo_RPGUR/Visor/VisorRPGUR.php | Mapa interactivo |
| Sede electrónica | https://sedeelectronica.smra.org | Trámites, tablón información pública |
| Sede alternativa | https://smra.sede.e-ayuntamiento.es/action/infopublica?method=enter | Tablón anuncios (mismo proveedor e-ayuntamiento) |

## Cómo se listan expedientes / proyectos

1. **RPGUR (fuente principal):** GET `busquedaConsulta?method=listPublico` con `idConcejo=46` (código concejo = últimos dos dígitos INE 33046). Tabla HTML paginada con `idInstrumento`, denominación, expediente, clasificación y estado. Detalle en `gestionConsulta?method=retrieve&idInstrumento=N` (fechas BOPA, metadatos). Codificación ISO-8859-1.

2. **Web Liferay:** PDFs en `/documents/1909823/...` (normativa, consultas previas, modificaciones ordenanzas/planeamiento). Páginas de urbanismo e información pública sin API JSON.

3. **Tablón sede:** HTML tabular en `infopublica` (anuncios, delegaciones, planes); no hay RSS público documentado en la sede SMRA.

## Cómo se publican licencias

- No hay dataset ni listado de licencias concedidas en smra.org.
- Trámites en sede (`sedeelectronica.smra.org/action/tramites`).
- El adapter incluye páginas informativas de normativa urbanística y trámites (patrón Morcín/Llanes).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer: `http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows`
  - Capa: `E79_ENTIDADES_URBANISTICAS:n01_AMBITO_INSTRUMENTO_CONSULTAS`
  - Filtro: `id_municipio=33046`
  - Campo enlace: `Id._Inventario_Registro_Urbanístico` → `idInstrumento` RPGUR
  - Visor: enlace desde normativa urbanística al visor RPGUR regional
- **Estrategia:** Precargar polígonos WFS por municipio; al procesar instrumentos RPGUR, adjuntar `geom_geojson` si coincide inventario.
- **Limitaciones:**
  - WFS y RPGUR (`www54.asturias.es`) pueden dar timeout/TLS desde algunos entornos cloud; Liferay aporta filas mínimas.
  - Sede electrónica con errores TLS intermitentes desde agentes automatizados.
  - Licencias sin georreferencia pública.
  - IGN OGC API no devuelve `nameunit` para este municipio; el manifest incluye límite OSM (`municipal-boundary.geojson`, Nominatim) para validación geográfica y centroide `[43.2744, -5.6153]`.

## Limitaciones generales

- Documentos Liferay en biblioteca `1909823`; crawl limitado a semillas urbanismo/IP.
- Sin re-parse BOCM; cruce opcional vía `municipio match`.
