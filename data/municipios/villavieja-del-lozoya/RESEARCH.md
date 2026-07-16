# Villavieja del Lozoya — investigación portal ayuntamiento

**Municipio:** Villavieja del Lozoya (Comunidad de Madrid)  
**Fecha:** 2026-07-16  
**BOCM regional (referencia):** 15 avisos

## Resumen

Villavieja del Lozoya publica planeamiento en la **web municipal WordPress** (Normas Subsidiarias
2024, urbanizaciones históricas con anuncios BOCM) y trámites en la **sede electrónica espublico
gestiona** (`villaviejadellozoya.sedelectronica.es`). Los ámbitos de planeamiento municipal están en
el **SIT de la Comunidad de Madrid** (WFS `sitcm:VPLA_V_AMBITO`).

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web municipal | `https://villaviejadellozoya.es` | WordPress Divi + REST API | Urbanismo, NNSS, urbanizaciones, modelos licencia |
| Normas Subsidiarias | `/urbanismo/normas-subsidiarias/` | HTML + 21 PDFs | Acuerdo, catálogo, memoria, normas, planos NNSS 2024 |
| Urbanizaciones | `/urbanizaciones/` | HTML + PDFs BOCM | Urbanización Los Llanos (BOCM 2019), callejero, estatutos |
| Licencias obra | `/licencias-de-obra-mayor-y-menor/` | HTML + PDFs | Modelos solicitud obra mayor/menor, DRUO |
| Sede electrónica | `https://villaviejadellozoya.sedelectronica.es` | espublico gestiona | Tablón, trámites, transparencia |
| Tablón de anuncios | `/board/` | HTML tabla Wicket | Vacío en julio 2026 (sin filas publicadas) |
| Servicio urbanismo sede | `/citizen-service/3a1af47f-...` | HTML menú | Enlace desde transparencia |
| SIT Comunidad Madrid | `https://idem.comunidad.madrid/geoserver3/ows` | WFS GeoJSON | 10 ámbitos `DS_NOMB_AMB` para `DS_MUNICIPIO='VILLAVIEJA DEL LOZOYA'` |

## Normas Subsidiarias (WordPress)

Página con acordeón Visual Composer: acuerdo, catálogo, memoria, normas urbanísticas y planos de
ordenación. Enlace al visor SIT CM. 21 PDFs en `/wp-content/uploads/2024/04/`.

## Urbanizaciones

Documentación de la urbanización «Los Llanos»: anuncios BOCM (enero–abril 2019), callejero,
bases y estatutos de la entidad de conservación.

## Tablón de anuncios (`/board/`)

Tabla Wicket con columnas Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha.
En julio 2026 el `<tbody>` está vacío; no hay anuncios recientes publicados.

## Licencias

- Modelos PDF en web: solicitud obra mayor/menor, declaración responsable urbanística.
- Página de 1ª ocupación: `/licencia-de-1a-ocupacion/`.
- No hay dataset histórico de concesiones con coordenadas; concesiones se publicarían en tablón
  cuando existan.
- Catálogo `/dossier` no responde de forma fiable en CI (timeout).

## Proyectos / planeamiento

- **NNSS 2024:** 21 documentos PDF (planeamiento vigente).
- **Urbanizaciones:** 5+ PDFs BOCM y documentación Los Llanos.
- **SIT WFS:** 10 ámbitos (UE-A-1/2/3, UE-B, actuaciones aisladas, Tercio de la Laguna, La Cañada,
  Las Cabezas, El Molinillo) con polígonos.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='VILLAVIEJA DEL LOZOYA'` (`srsName=EPSG:4326`)
  - Enlace al visor SIT CM desde página NNSS (sin API propia del ayuntamiento)
  - PDFs de planos sin georreferenciación vectorial automatizable
- **Estrategia:** Semillas de ámbitos desde WFS con `geom_geojson`; enriquecer títulos con códigos
  UE/ámbito cuando aparezcan en tablón o BOCM.
- **Limitaciones:** Tablón vacío; PDFs sin coords; `/dossier` inaccesible en CI; licencias sin GIS.

## Limitaciones

- Tablón sin filas publicadas (histórico requiere búsqueda POST Wicket).
- Catálogo trámites `/dossier` timeout en entorno del agente.
- Transparencia sede navegación Wicket sin scrape estable de documentos.
- Licencias: solo páginas informativas y modelos, no concesiones publicadas.

## Estrategia adapter

1. Scrape PDFs NNSS y urbanizaciones desde WordPress.
2. Scrape tablón `/board/` (vacío pero preparado para incremental).
3. Semillas de ámbitos SIT WFS (10 figuras) con `geom_geojson`.
4. Páginas informativas de licencias (modelos + sede).
5. IDs: `villavieja-del-lozoya-{lic|proy}-{sha256[:14]}`.
