# Arrigorriaga — INE 48011, Bizkaia

Investigación y extracción real: 7 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Inventarios oficiales encontrados y alcance elegido

Fuente principal: [Barrios, Urbanismo y Vivienda](https://www.arrigorriaga.eus/es/departamentos/barrios-urbanismo-y-vivienda).
El apartado Urbanismo → Planes publica cuatro instrumentos concretos de planificación
física de equipamientos, accesibilidad, movilidad y paisaje. No son formularios,
licitaciones ni noticias. Se extraen **cuatro registros con 35 enlaces documentales**:

| Instrumento | Documentos | Procedencia |
| --- | ---: | --- |
| Plan Director de Equipamientos Públicos Municipales | 2 | Carpeta 533: memoria y planos |
| Plan de Accesibilidad | 27 | Carpeta 658: memoria; subcarpetas 536 y 537: 13 propuestas de vía pública y 13 de edificios |
| Plan de Movilidad Sostenible | 5 | Carpeta 535: diagnosis, objetivos, actuaciones, cartografía y participación |
| Plan de Acción del Paisaje de Arrigorriaga | 1 | PDF enlazado directamente en su acordeón; diagnóstico del eje sur industrial |

Las carpetas se descubren en los `script.file-list-widget-config` del panel de
cada plan. No se extraen todos los documentos genéricos de la página.
Se usa la misma API pública que el widget municipal:

- [Árbol de equipamientos](https://www.arrigorriaga.eus/api/v1/folder/533/recursive/).
- [Árbol completo de accesibilidad](https://www.arrigorriaga.eus/api/v1/folder/658/recursive/).
- [Árbol de movilidad](https://www.arrigorriaga.eus/api/v1/folder/535/recursive/).
- [Archivos de accesibilidad, raíz](https://www.arrigorriaga.eus/api/v1/file/?format=datatables&folder=658).

También se descubrió la [sede electrónica, planeamiento urbanístico](https://arrigorriaga.egoitzaelektronikoa.eus/transparency/92f5165c-3c57-4139-b605-4f117c835f1e),
enlazada desde «Plan General de Ordenación Urbana». En la captura viva enumera
PGOU (136 documentos), ECIA (12), título VI de las NNSS (1), PGOU MOD.1 (14) y
sectorización SUNS 26.1 Bentakoerreka-Iparra (28). Sus enlaces expanden un árbol
Wicket mediante llamadas de sesión. **Ese árbol y el PGOU no están incluidos en
este adaptador**: no se devuelve la categoría del PGOU como un expediente
sintético ni se fija un token de sesión como URL documental permanente.
El [catálogo foral de planeamiento de Arrigorriaga](https://www.opendatabizkaia.eus/es/catalogo/planeamiento-urbanistico-arrigorriaga)
fue localizado como inventario complementario, pero no se mezcla su cartografía
orientativa con proyectos ni se usa como evidencia de aprobación.
La cobertura es deliberadamente parcial: cuatro planes documentados del inventario
departamental, no todas las actuaciones ni todo el planeamiento del municipio.

## Semántica y comprobación documental

Cada registro representa un instrumento documental publicado, con `source_entity_type:
documento`, y conserva todos sus documentos dentro de `documentos`. Las propuestas
de calles o edificios de accesibilidad no se convierten en obras independientes,
ni se afirma que se hayan contratado o ejecutado. El enlace principal identifica
el panel del instrumento; cada documento retiene URL propia, carpeta, nombre,
API de procedencia y, cuando existe, `cms_created_at`.

Se descargaron y comprobaron cuatro PDFs de muestra: memoria de equipamientos,
memoria de accesibilidad, diagnosis de movilidad y diagnóstico de paisaje. Todos
respondieron HTTP 200, `application/pdf` y firma `%PDF-`. Con `pdftotext` se
verificaron sus portadas: equipamientos julio de 2015; accesibilidad noviembre de
2017; movilidad marzo de 2023; paisaje fase I, noviembre de 2017. Esas fechas son
del documento, **no fechas de acuerdo ni publicación**. El diagnóstico paisajístico
contiene criterios de intervención, pero no acredita aprobación del plan final.
El nombre de archivo con prefijo 20210118 tampoco se usa como fecha de aprobación.

La API incorpora cargas de abril/mayo de 2026; esas marcas solo se conservan bajo
`cms_created_at` en documentos. No se emiten `fecha`, `fecha_publicacion`,
`fecha_acuerdo`, `fecha_aprob` ni fases de aprobación inferidas. No se emiten
coordenadas o geometría. `publication_ready: false` y `geometry_status:
unavailable`; licencias, ejecución programada y jitter están desactivados.
El clasificador compartido puede identificar estas entradas como documentación;
no se reclama una identidad de expediente administrativo ni elegibilidad de actividad.

## Exhaustividad dentro del alcance

El HTML observado presenta los cuatro planes sin paginación. El scraper rechaza
paginación HTML nueva y cambios que eliminen secciones reconocidas. Recorre todo
el árbol de carpetas, incluidos los hijos de accesibilidad, sin límite de profundidad
que corte silenciosamente. Rechaza carpetas repetidas y discrepancias de conteos.
La API DataTables se consulta con `start` y `length`, avanzando hasta
`recordsFiltered`, que debe coincidir con `recordsTotal` y con el conteo del árbol.
Respuestas vacías prematuras, páginas repetidas, tipos documentales inesperados y
redirecciones fuera del dominio producen error. Los instrumentos vacíos también.
Se reemplaza la salida solo al terminar una extracción válida.

## Validación reproducible

Pruebas offline:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_arrigorriaga -v
```

Siete pruebas: selección y aislamiento de paneles, exclusión de formulario,
cambios de estructura, paginación real y repetida, truncamiento, conteos, recursión,
agrupación, ausencia de fechas/coordenadas inferidas, actualización por instantánea,
preservación de salida ante error, carga del manifest/registry y licencias sin red.

La ejecución viva usa `load_manifest('arrigorriaga')`, `load_portal_adapter(...)` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con
`adapter.config['capture_dir']='evidence/captures'`. Resultado: **4 registros,
35 documentos**, sin acceso a base de datos, publicación ni geocodificación.
La actualización repite la instantánea completa porque no existe cursor jurídico
fiable en las fechas del CMS.

Evidencia local no versionada: `evidence/proyectos.jsonl`, `evidence/validation.json`
(con conteos, URLs y limitaciones), HTML del inventario y sede, JS del widget,
respuestas JSON de árboles/archivos, capturas de la ejecución por hash de URL y
cuatro PDFs de muestra. Solo se comprobaron contenidos de muestra, no el texto
completo de los 35 documentos. Se conservan todos sus enlaces.
