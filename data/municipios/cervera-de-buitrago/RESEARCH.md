# Cervera de Buitrago — investigación portal ayuntamiento

**Municipio:** Cervera de Buitrago (Comunidad de Madrid)  
**Fecha:** 2026-08-16  
**BOCM regional (referencia):** 3 avisos

## Resumen

Cervera de Buitrago publica trámites y anuncios en la **sede electrónica espublico gestiona**
(`cerveradebuitrago.sedelectronica.es`). La web corporativa (`www.cerveradebuitrago.org`) es
WordPress con noticias generales pero **sin sección de urbanismo**. El catálogo de trámites de la
sede incluye licencias y actuaciones urbanísticas. No hay visor GIS municipal ni ámbitos en el SIT
de la Comunidad de Madrid para este municipio.

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web municipal | `https://www.cerveradebuitrago.org/` | WordPress | Noticias, contacto, instalaciones; sin urbanismo |
| Sede electrónica | `https://cerveradebuitrago.sedelectronica.es/` | espublico gestiona | Trámites, tablón, transparencia |
| Tablón de anuncios | `https://cerveradebuitrago.sedelectronica.es/board/` | HTML tabla Wicket | 7 anuncios recientes (edicto calle Fresno, bandos, plenos) |
| Catálogo trámites | `https://cerveradebuitrago.sedelectronica.es/dossier.0` | HTML enlaces `/catalog/t/{uuid}` | Licencias urbanísticas, DRUO, planeamiento, actuaciones |
| Portal transparencia | `https://cerveradebuitrago.sedelectronica.es/transparency/` | HTML estático | Catálogo de bienes protegidos; sección urbanismo vacía (0 docs) |
| SIT Comunidad Madrid | `https://idem.comunidad.madrid/geoserver3/ows` | WFS GeoJSON | 0 ámbitos para `DS_MUNICIPIO='CERVERA DE BUITRAGO'` |

## Tablón de anuncios (`/board/`)

Tabla HTML con columnas: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha.
Enlaces `preview-document/{uuid}`. En agosto 2026: edicto exposición **Calle Fresno 5** (contratación
patrimonial), bandos, plenos, calendario fiscal. Sin licencias de obra publicadas en el tablón.

## Licencias

- Trámites informativos en catálogo sede: *Solicitud de Licencia o Autorización Urbanística*,
  *Declaración Responsable o Comunicación en Materia Urbanística*, *Solicitud de Licencia de
  Ocupación*, *Solicitud de Licencia de Actividad*, etc.
- No hay dataset histórico de concesiones con coordenadas ni listado de licencias concedidas.

## Proyectos / planeamiento

- **Transparencia:** sección «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» sin documentos
  indexados; único documento relacionado: **Catálogo de bienes protegido** (`preview-document`).
- **Tablón:** edicto de exposición pública Calle Fresno 5 (agosto 2026).
- **Catálogo sede:** trámites de planeamiento (modificación PG, aprobación desarrollo, actuación
  urbanística, compensación).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** WFS `sitcm:VPLA_V_AMBITO` devuelve 0 features para `CERVERA DE BUITRAGO`; no hay
  visor ArcGIS, WFS municipal ni GeoJSON en datos abiertos.
- **Estrategia:** El adapter consulta WFS SITCM por compatibilidad con municipios vecinos; sin
  ámbitos publicados no es posible enriquecer `geom_geojson`. El orquestador aplicará centroide
  municipal + jitter.
- **Limitaciones:** PDFs del tablón sin georreferenciación; transparencia sin visor enlazable;
  municipio pequeño sin planeamiento digitalizado en SITCM.

## Limitaciones

- Certificado SSL de la sede requiere `insecure_ssl: true` en algunos entornos CI.
- `/normative` redirige en bucle (302); no usable.
- Web WordPress sin páginas de urbanismo ni PDFs normativos.
- Tablón muestra solo anuncios recientes (~7 filas).

## Estrategia adapter

1. Scrape tablón `/board/` (tabla + fallback enlaces preview).
2. Catálogo trámites urbanismo desde `/dossier.0`.
3. Documentos transparencia (preview-document) con keywords urbanismo.
4. Páginas informativas de referencia (tablón + trámites + sede).
5. IDs: `cervera-de-buitrago-{lic|proy}-{sha256[:14]}`.
