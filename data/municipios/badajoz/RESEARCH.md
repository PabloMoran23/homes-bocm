# Badajoz — investigación portal ayuntamiento

## Resumen

- **Web corporativa:** https://www.aytobadajoz.es
- **Sede electrónica:** https://sede.aytobadajoz.es
- **Provincia / CCAA:** Badajoz, Extremadura

## Fuentes de proyectos / planeamiento

### Tablón virtual sede (principal)

- **URL semilla:** https://sede.aytobadajoz.es/portal/tablonVirtual.do?opc_id=175&ent_id=1&idioma=1&subseccion=ANU_ADMON
- **Filtros usados:** `campo=17` (tipos urbanísticos varios), `campo=9` (programas de actuación); el listado visible coincide (~24 expedientes recientes).
- **Formato:** HTML tabular (plataforma STA/sede clásica), filas `tr.Lista2LineaPar|Impar` con `id='exp_<id>'`.
- **Columnas:** Año, código, tipo de expediente, nombre (enlace a detalle `expId=`), fechas creación/publicación.
- **Detalle expediente:** misma URL con `expId`; documentos en filas `id='doc_<id>'` con enlace `tablonVirtual.do?aDoc=F&documento=...`.
- **Tipos observados:** estudios de detalle, modificaciones PGM, reparcelaciones, programas de ejecución, proyectos de urbanización, convenios urbanísticos, reservas de aprovechamiento, etc.

### Plan General Municipal (web corporativa)

- **Índice PGM:** https://www.aytobadajoz.es/es/ayto/pgm
- **Planeamiento en trámite:** https://www.aytobadajoz.es/es/ayto/pgm/planeamiento-en-tramite (contenido ligero en HTML estático)
- **Documentación PDF:** subsecciones `publicacion`, `memorias`, `planespecial`, `programa` enlazan PDFs bajo `/~pgou/...`
- **Planos calificación (solo PDF 1:2000):** https://www.aytobadajoz.es/es/ayto/pgm/planos/nup/mapa-calificacion — cientos de hojas PDF, no API.

## Licencias de obra

- El tablón **ANU_ADMON** no incluye licencias municipales de obra concedidas.
- La sede expone trámites genéricos; no hay dataset ni RSS de licencias urbanísticas público equivalente a Madrid.
- **Estrategia adapter:** fila informativa apuntando a PGM/sede si no hay licencias en tablón; `licencias.jsonl` con `min_rows: 0` en validación.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - PGM ayuntamiento: planos PDF por hoja (NUP), sin servicio ArcGIS/WFS municipal enlazado al código de expediente.
  - Geoportal Diputación de Badajoz (https://geoportal.dip-badajoz.es): cartografía provincial; no consulta fiable por `expId` del ayuntamiento.
  - Visor SIU estatal (MIVAU): enlace informativo al planeamiento vigente, sin geometría de expediente.
- **Estrategia:** no hay query GIS por expediente; el orquestador usará centroide municipal + jitter (`centroid` en manifest).
- **Limitaciones:** delimitación de ámbito solo en PDFs de proyecto; sin `geom_geojson` en adapter.

## Limitaciones técnicas

- Codificación sede: ISO-8859-1 en respuestas HTML.
- Paginación del tablón: una página con expedientes recientes (sin API JSON).
- `request_delay_s` recomendado ≥ 0.35 s por petición de detalle (N+1 documentos).
- SSL sede válido; no requiere `insecure_ssl`.

## Referencia de implementación

- Patrón tablón STA: `municipio/adapters/torrejon_de_ardoz.py`, `municipio/adapters/villanueva_de_la_canada.py`
- PDFs corporativos: similar a sección ordenanzas en Torrejón / seeds Pozuelo
