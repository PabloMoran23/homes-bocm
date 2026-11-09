# Navas de San Juan — INE 23063, Jaén, Andalucía

Verificación en vivo: 2026-11-09. Adaptador exclusivo del municipio, siguiendo
`AyuntamientoAdapter`, el cargador de manifests y los ejemplos existentes.

## Descubrimiento y fuentes oficiales

Desde https://navasdesanjuan.es/ → Ayuntamiento → Áreas Municipales → Urbanismo:

- https://navasdesanjuan.es/el-ayuntamiento/areas-municipales/urbanismo/
- https://navasdesanjuan.es/el-ayuntamiento/areas-municipales/urbanismo/registro-municipal-de-instrumentos-de-planeamiento-navas-de-san-juan-jaen/
- https://navasdesanjuan.es/el-ayuntamiento/areas-municipales/urbanismo/planeamiento-en-elaboracion/

Ambos inventarios respondieron HTTP 200 y presentan el contenido completo en HTML,
sin paginación activa. El adaptador rechaza enlaces de paginación si aparecen;
no establece límites de filas ni corta páginas. Extrae el contenido municipal,
excluyendo navegación, noticias laterales y banners. Sigue todas las páginas de
instrumentos enlazadas desde las filas admitidas y conserva sus documentos.
Falla ante ausencia del inventario, cambio de estructura, referencias duplicadas,
nuevos tipos no revisados o detalle sin documentos. Actualización = instantánea
completa, sin cursor ni modificaciones del estado incremental.

## Cobertura obtenida

**13 instrumentos reales**, no 13 obras nuevas ni licencias:

- 11 del registro municipal: números 1–9, 13 y 15. Incluyen NN.SS., modificaciones,
  adaptación parcial, innovaciones PGOU y estudios de detalle. Los números 10, 11,
  12 y 14 son ordenanzas (incluidas fiscales y una derogada), excluidas del conjunto.
- Un único PBOM agrupa expediente, avance, memorias, cartografía, evaluación
  ambiental y aprobación inicial, aunque sus documentos ocupan cuatro secciones.
- Estudio de Ordenación de Calle Cruz, 15: sus dos documentos forman un instrumento.

Se preservan títulos y enlaces tal como se publican, incluidas discrepancias entre
las etiquetas de los planos PBOM y sus nombres de fichero. Las páginas de detalle
se conservan además de sus adjuntos, con `source_url` por documento. Las filas 3,
4 y 5 tienen datos tabulares pero carecen de enlaces documentales. Los IDs usan
números del registro oficial y claves de instrumentos, nunca títulos de documentos
como proyectos independientes.

Cobertura parcial: inventarios urbanísticos publicados, no catálogo exhaustivo de
obras, expedientes administrativos o histórico de noticias. Descargas
(https://navasdesanjuan.es/servicios/descargas/) mezcla material antiguo de PGOU en
trámite y formularios; no se añade para evitar duplicación y confusión de vigencia.
No se ha verificado inventario público de licencias concedidas. La solicitud de
licencia de obras es un formulario, queda excluida; licencias deshabilitadas.

## Fechas y procedencia

En el registro, `fecha_aprob` procede exclusivamente de la columna «APROBACIÓN
DEFINITIVA»; `fecha_publicacion`, de «PUBLICACIÓN», que cita boletines, no la fecha
de actualización web. Se conservan ambas celdas originales y el órgano aprobador.
1995 sin día/mes permanece en `aprobacion_texto`, con fecha normalizada nula.
BOP-2019-679 no se convierte en fecha. La fila 8 tiene publicación original y
corrección: se conserva el texto, sin escoger una de las dos fechas. La fila 15
publica una fecha anterior a la aprobación indicada: se conserva esa discrepancia
sin corregirla ni inventar acuerdos. `fecha` genérica siempre nula.

Las dos entradas en elaboración tienen fase inicial documentada en etiquetas,
pero fechas nulas: el adaptador no extrae el texto de los PDFs ni interpreta fechas
en rutas o nombres. Verificación documental adicional guardada en evidencia:

- PBOM: edicto BOP 2026/3919, publicación 27-08-2026, pleno 30-07-2026,
  firma 12-08-2026. Fuente enlazada: https://navasdesanjuan.es/wp-content/uploads/2026/08/exposicion_bop.pdf
- Cruz 15: BOP 2025/5887, publicación 26-12-2025, acuerdo 11-11-2025,
  firma 09-12-2025. Fuente enlazada: https://navasdesanjuan.es/wp-content/uploads/2025/12/BOP-2025-5887-EXPOSICION-ESTUDIO-DE-ORDENACION-CRUZ-15.pdf

Estas comprobaciones manuales no se incorporan como constantes al scraper.
No se presume aprobación definitiva del PBOM por transcurso del tiempo.

## Geometría y límites de integración

`geometry_status: unavailable`, coordenadas y geometría nulas; sin jitter.
El inventario PBOM ofrece ZIP de «Planimetría georreferenciada», descargado e
inspeccionado: 13 archivos DWG (incluidas alternativas), sin GeoJSON, SHP o
metadatos CRS verificados. Se conserva el enlace. No se convierte CAD ni se atribuye
al conjunto una geometría de sus alternativas o del término municipal.

La anotación compartida de entidades clasifica las 13 filas como `pendiente`
(`insufficient_identity_evidence`) y comunica `adapter_incident / unknown_entity_spike`.
Las referencias del registro no se disfrazan como números de expediente para
eludir esa política. La extracción es verificable; su aceptación para ingestión o
publicación requiere revisión independiente. `publication_ready: false`.
No se modifica esa política ni se accede a servicios de publicación.

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_navas_de_san_juan -v`: 5 pruebas del parser y
contrato del adaptador. Cubren agrupación, ordenanzas excluidas, fechas ambiguas,
paginación/cambios estructurales, detalles enlazados, actualización y licencias vacías.

Extracción real mediante `load_manifest('navas-de-san-juan')` y
`load_portal_adapter(manifest).backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
Para guardar HTML se añade en memoria `portal.config.capture_dir='evidence/live-sources'`.
Los artefactos locales `evidence/proyectos.jsonl`, `evidence/validation.json`,
HTML, PDFs de edictos, sus textos y el inventario ZIP no forman parte del código.
Los adjuntos restantes se conservan como enlaces; no se afirma haber descargado
ni validado individualmente todos sus contenidos.

`schedule.enabled=false`, `licencias.enabled=false`, `geocode.jitter_missing=false`.
