# Llanes — investigación portal ayuntamiento

Municipio: **Llanes** (`llanes`) — Asturias (BOPA, 20 entradas históricas).

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal (Liferay) | https://www.ayuntamientodellanes.com |
| Urbanismo | https://www.ayuntamientodellanes.com/es/urbanismo |
| PGOU y Catálogo | https://www.ayuntamientodellanes.com/es/aprobacion-pgou-y-catalogo |
| Plan Especial Uso Turístico | https://www.ayuntamientodellanes.com/es/plan-especial-de-uso-turistico |
| Documentos en información pública | https://www.ayuntamientodellanes.com/es/documentos-en-informaci%C3%B3n-p%C3%BAblica1 |
| Normativa urbanística | https://www.ayuntamientodellanes.com/es/normativa-urbanistica |
| Sede electrónica (e-ayuntamiento) | https://llanes.sede.e-ayuntamiento.es |
| Tablón anuncios (sede) | https://llanes.sede.e-ayuntamiento.es/action/infopublica?method=enter&edictos=ANUNCIOS |
| RPGUR (registro Asturias) | https://www54.asturias.es/rpgur/action/publico/welcome |
| Visor urbanístico regional | http://visorrpgur.asturias.es:8092/Visor_Urbanismo_RPGUR/Visor/VisorRPGUR.php |

## Cómo se listan expedientes / proyectos

1. **Registro RPGUR (Principado de Asturias)** — POST a `busquedaConsulta?method=listPublico` con `idConcejo=36` (LLANES). Devuelve tabla HTML con 15 instrumentos de planeamiento general (PGOU en tramitación, NSPM vigentes, revisiones históricas, etc.). Detalle en `gestionConsulta?method=retrieve&idInstrumento=…`.

2. **Web municipal Liferay** — Secciones de urbanismo publican PDFs en `/documents/…` y carpetas **Dropbox** compartidas (PGOU, PEUT, PEREDI). No hay visor de expedientes individuales; la documentación es estática por instrumento.

3. **Sede e-ayuntamiento** — Referenciada desde la web para tablón y trámites, pero **inaccesible** por error TLS (`curl` exit 35, handshake failure). No scrapeable en CI.

## Licencias de obra

- No hay dataset público de concesiones en la web municipal.
- La sede electrónica aloja trámites y tablón, pero está caída (TLS).
- El ayuntamiento publica en BOPA instrucciones de licencias urbanísticas (nov 2025), sin listado tabular en portal.
- **Estrategia adapter:** páginas informativas de trámites (`/es/urbanismo` + enlace sede) con `min_rows: 0` en validación de licencias.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer RPGUR: `http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows`
  - Capa: `E79_ENTIDADES_URBANISTICAS:n01_AMBITO_INSTRUMENTO_CONSULTAS`
  - Filtro: `Instrumento LIKE '%LLANES%'`
  - Campo enlace: `Id._Inventario_Registro_Urbanístico` ↔ `idInstrumento` RPGUR
  - También disponible `E79_ESTADO_PLANEAMIENTO:PG_TRAMITACION` (`NOMBRE LIKE '%LLANES%'`)
- **Estrategia:** tras obtener metadatos RPGUR, consultar WFS con `srsName=EPSG:4326` y rellenar `geom_geojson` (MultiPolygon) + centroide.
- **Limitaciones:**
  - Solo 2 instrumentos LLANES tienen polígono de ámbito en WFS (PGO LLANES en tramitación, Normas provisionales vigentes).
  - Instrumentos históricos / modificaciones puntuales (NSPM Celorio, Poo, etc.) no tienen geometría individual enlazable.
  - Sede y tablón municipal sin acceso → licencias sin coords.
  - Dropbox/PDF sin georreferencia.

## Limitaciones generales

- Sede `llanes.sede.e-ayuntamiento.es`: certificado/handshake TLS roto desde entorno de scraping.
- Tablón de anuncios solo accesible vía sede (no alternativa en web Liferay).
- Planeamiento documentado principalmente en RPGUR regional + PDFs estáticos.
- Sin API JSON municipal; scrape HTML determinista.
