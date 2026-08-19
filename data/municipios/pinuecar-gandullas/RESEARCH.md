# Piñuécar-Gandullas — investigación portal ayuntamiento

**Municipio:** Piñuécar-Gandullas (Comunidad de Madrid)  
**Fecha:** 2026-08-13  
**BOCM regional (referencia):** 4 avisos

## Resumen

Piñuécar-Gandullas es un municipio pequeño de la Sierra Norte de Madrid (dos núcleos:
Piñuécar y Gandullas). La **sede electrónica** (`pinuecargandullas.sedelectronica.es`) usa la
plataforma **espublico gestiona** con tablón de anuncios, catálogo de trámites (`/dossier`) y
portal de transparencia. El dominio web oficial
(`xn--ayuntamientopiuecargandullas-byc.es`) devuelve **HTTP 500** y no es scrapeable en el
momento de la investigación.

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Sede electrónica | `https://pinuecargandullas.sedelectronica.es/` | espublico gestiona | Inicio, trámites, tablón, transparencia |
| Tablón anuncios | `https://pinuecargandullas.sedelectronica.es/board` | HTML tabla Wicket | ~10 anuncios recientes (cobranza, transporte, ordenanza residuos BOCM) |
| Tablón info | `https://pinuecargandullas.sedelectronica.es/info.0` | HTML | Subconjunto del tablón principal |
| Catálogo trámites | `https://pinuecargandullas.sedelectronica.es/dossier` | HTML enlaces `/catalog/t/{uuid}` | ~103 trámites; 25+ de urbanismo/licencias |
| Portal transparencia | `https://pinuecargandullas.sedelectronica.es/transparency` | HTML estático | Sección «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» con **0** documentos |
| Web municipal (caída) | `https://xn--ayuntamientopiuecargandullas-byc.es/` | HTTP 500 | No accesible |

## Tablón de anuncios (`/board`)

Tabla HTML con enlaces `preview-document/{uuid}` (visor PDF). En agosto 2026 muestra anuncios de
cobranza IBI, horarios autobús L191, oficinas móviles bancarias, recogida residuos y
**Ordenanza definitiva gestión de residuos** (referencia BOCM-20260318-97). No hay anuncios de
licencias de obra concretas publicados en el tablón.

## Licencias

- No hay dataset histórico de concesiones con coordenadas.
- El catálogo `/dossier` lista trámites informativos: licencia de obra mayor, obra menor
  (declaración responsable), licencia de actividad, ocupación de vía pública, etc.
- Los anuncios de concesión aparecen en el tablón cuando el ayuntamiento los publica.

## Proyectos / planeamiento

- **Tablón:** Ordenanza definitiva gestión de residuos (BOCM).
- **Trámites dossier:** Modificación del planeamiento de desarrollo, planeamiento general
  (modificación), solicitud de actuación urbanística, aprobación de planeamiento de desarrollo,
  certificado/informe urbanístico.
- **Transparencia:** Sin documentos en la sección de urbanismo.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** Consulta WFS `sitcm:VPLA_V_AMBITO` (Comunidad de Madrid) con
  `DS_MUNICIPIO='PINUECAR-GANDULLAS'` y variantes devuelve **0 ámbitos**. No hay visor
  urbanístico municipal, ArcGIS ni datos abiertos georreferenciados.
- **Estrategia:** El orquestador aplicará centroide municipal + jitter (`centroid` en manifest).
- **Limitaciones:** Solo tablón PDF y trámites informativos sin georreferenciación; municipio sin
  planeamiento digitalizado en SITCM.

## Limitaciones

- Web municipal oficial inaccesible (HTTP 500).
- Tablón muestra solo anuncios recientes (~10 filas); histórico no paginado.
- Transparencia urbanismo vacía (0 documentos).
- Sin visor GIS ni polígonos SITCM.

## Estrategia adapter

1. Scrape tablón `/board` + `/info.0` (tabla + fallback enlaces `preview-document`).
2. Scrape catálogo `/dossier` para trámites de licencias y planeamiento.
3. Páginas informativas de licencias (tablón, transparencia, dossier urbanismo).
4. IDs: `pinuecar-gandullas-{lic|proy}-{sha256[:14]}`.
