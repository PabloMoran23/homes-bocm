# Dos Hermanas — investigación portal ayuntamiento

Municipio: **Dos Hermanas** (`dos-hermanas`) — provincia Sevilla, Andalucía. INE **41038**.

## URLs base y semillas

| Fuente | URL |
|--------|-----|
| Web municipal (SagaSuite) | https://www.doshermanas.es |
| Concejalía Urbanismo | https://www.doshermanas.es/concejalias/urbanismo/ |
| Instrumentos ordenación (PGOU, PP, ERI, estudios detalle) | https://www.doshermanas.es/concejalias/urbanismo/Instrumentos-Ordenacion-Urbanistica/ |
| PGOU (PDFs consolidados y planos) | https://www.doshermanas.es/concejalias/urbanismo/Instrumentos-Ordenacion-Urbanistica/pgou/ |
| Convenios urbanísticos | https://www.doshermanas.es/concejalias/urbanismo/convenios-urbanisticos/ |
| Licencias / comunicaciones previas (trámites) | https://www.doshermanas.es/concejalias/urbanismo/licencias-urbanisticas/ |
| Transparencia urbanismo | https://doshermanas.es/transparencia/transparencia-en-materias-de-urbanismo-obras-publicas-y-medioambiente/ |
| Sede electrónica | https://sede.doshermanas.es |
| Tablón de anuncios (STA) | https://sede.doshermanas.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all |
| SITUA (Junta, documentación digitalizada) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=41038 |

## Cómo se listan expedientes / planeamiento

- **Web SagaSuite:** páginas estáticas con enlaces a PDFs bajo `/export/sites/ayto-dos-hermanas/...` (PGOU, modificaciones históricas en BOP/BOJA, planes parciales SEN/SNP, estudios de detalle). No hay API JSON; el adapter extrae `<a href="...pdf">` y enlaces de texto urbanístico.
- **Tablón STA:** la página `PTS2_TABLON&KEY=all` incluye `var dataset_PTS2_TABLON = [...]` con ~850 anuncios (`descriptionProc`, `externString`, `remitent`, fechas XML). Filtrado por palabras clave urbanísticas / remitente Urbanismo.
- **Información pública reciente:** anuncios de innovación/modificación PGOU aparecen en tablón y en prensa local; el undécimo expediente de innovación PGOU estuvo en exposición pública (2026).

## Licencias de obra

- No hay dataset abierto de concesiones con coordenadas (estilo Madrid SIGMA).
- El ayuntamiento publica **páginas de trámites** (licencias, comunicaciones previas, declaraciones responsables) sin listado histórico de concesiones.
- El **tablón STA** incluye algunas notificaciones/edictos relacionados con licencias; el adapter las captura cuando el título coincide con patrones de licencia.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - Web municipal: plano PDF de usos del suelo (`UsosdelSuelo.pdf`) sin servicio WMS/WFS ni enlace a expediente.
  - SITUA Junta: documentación escaneada del planeamiento aprobado; no expone geometría vectorial consultable por código de expediente municipal.
  - No se encontró visor ArcGIS/GeoServer municipal público enlazado desde la sede.
- **Estrategia:** el orquestador usará centroide municipal (`manifest.portal.config.centroid`) + jitter en geocode.
- **Limitaciones:** geometría de ámbito solo en PDFs/planos raster; tablón sin coordenadas.

## Limitaciones generales

- Tablón STA: respuesta ~800 KB; timeout recomendado **180 s**.
- Certificado sede: `sede_insecure_ssl: true` en manifest (patrón otros municipios STA).
- Muchos PDFs del PGOU son documentación histórica (BOP 2002–2012), no expedientes en curso.

## Adapter

- `municipio.adapters.dos_hermanas:DosHermanasAyuntamientoAdapter`
- Fuentes: tablón STA + crawl semillas urbanismo SagaSuite + páginas trámite licencias.
