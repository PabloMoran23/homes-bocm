# Morcín — investigación portal ayuntamiento

Municipio: **Morcín** (`morcin`) — Asturias / provincia Morcín  
Boletín: BOPA (`boletin_source_id: bopa`, 1 entrada histórica)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.morcin.es | Liferay DXP (i-cast) |
| PGOU / normativa urbanística | https://www.morcin.es/normativa-urbanistica1 | Texto PGOU, enlaces normativa |
| Instrumentos planeamiento vigentes | https://www.morcin.es/instrumentos-de-planeamiento-vigentes | Suelo urbano (Argame, Santa Eulalia, La Foz, Las Mazas) |
| Gestión urbanística / núcleos rurales | https://www.morcin.es/instrumentos-de-gestion-urbanistica | Instrumentos gestión |
| PERI Parteayer | https://www.morcin.es/convenios-urbanisticos | PDFs Liferay `/documents/` (memoria, planos) |
| Plan parcial Argame | https://www.morcin.es/plan-parcial-de-argame | Documentación plan parcial |
| Clasificación / zonificación | https://www.morcin.es/clasificacion-zonificacion | Mapas PGOU |
| Visor geográfico municipal | http://urbanismo.i-cast.es/Morcin/ | Visor i-cast (HTML/JS, sin API REST pública documentada) |
| RPGUR (Principado) | https://www54.asturias.es/rpgur/action/publico/welcome | Registro planeamiento |
| Consulta RPGUR Morcín | `busquedaConsulta?method=listPublico&idConcejo=38&estado=V` | Instrumentos vigentes (tabla HTML) |
| Visor RPGUR (Asturias) | https://sigvisor.asturias.es/visorurbanismo | Visor regional (sustituye legacy visorrpgur HTML) |
| Sede electrónica | https://morcin.sede.e-ayuntamiento.es | Trámites; tablón de anuncios (no integrado en adapter) |
| Portal transparencia | https://www.morcin.es/portal-de-transparencia | Contratación / normativa (sin listado expedientes urbanísticos) |

## Cómo se listan expedientes / proyectos

1. **RPGUR (fuente principal):** `busquedaConsulta?method=listPublico` con `idConcejo=38` (MORCÍN, código INE 33038). Tabla HTML paginada con `idInstrumento`, denominación, expediente, clasificación y estado. Detalle en `gestionConsulta?method=retrieve&idInstrumento=N` (fechas BOPA, metadatos).

2. **Web Liferay:** Documentos estáticos en `/documents/1899854/...` (PERI Parteayer, planos, memorias). Páginas temáticas PGOU / plan parcial sin API JSON.

3. **Visor i-cast:** Mapa embebido en web municipal; no expone WFS/WMS enlazable por expediente en la investigación.

## Cómo se publican licencias

- No hay dataset ni tablón HTML público de licencias concedidas en morcin.es.
- Trámites en sede electrónica (`morcin.sede.e-ayuntamiento.es`).
- El adapter devuelve páginas informativas de normativa urbanística / ordenanzas (patrón Pozuelo/Llanes).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer: `http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows`
  - Capa: `E79_ENTIDADES_URBANISTICAS:n01_AMBITO_INSTRUMENTO_CONSULTAS`
  - Filtro: `Instrumento LIKE '%MORC%'`
  - Campo enlace: `Id._Inventario_Registro_Urbanístico` → `idInstrumento` RPGUR
  - Visor municipal: http://urbanismo.i-cast.es/Morcin/ (sin integración API en adapter)
- **Estrategia:** Precargar polígonos WFS; al procesar instrumentos RPGUR, adjuntar `geom_geojson` si coincide inventario.
- **Limitaciones:**
  - WFS suele exponer pocos ámbitos municipales (PGOU / normas); instrumentos de desarrollo sin polígono individual.
  - RPGUR puede ser lento o bloquear desde algunos entornos (timeout TLS); Liferay sigue aportando filas mínimas.
  - Licencias sin georreferencia pública.

## Limitaciones generales

- RPGUR codificación ISO-8859-1; host `www54.asturias.es`.
- Documentos Liferay sin listado RSS de urbanismo.
- Sin re-parse BOCM; cruce opcional vía `municipio match`.
