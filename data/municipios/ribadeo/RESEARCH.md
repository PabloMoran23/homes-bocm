# Ribadeo — INE 27051, Lugo

Verificado el 2026-11-07 con el runtime preinstalado indicado. Un único adaptador,
para el inventario de planeamiento oficial de SIOTUGA enlazado por el Concello.

## Descubrimiento y fuentes

- https://www.ribadeo.gal/urbanismo/ — página municipal, HTTP 200. Su enlace
  «PXOM» apunta a SIOTUGA con `idconcello=27051&inv=1` (contiene un espacio
  accidental después del signo de interrogación). El texto introductorio municipal
  sobre la futura aprobación del PXOM está desactualizado: no se usa como estado.
  Los apartados de licencias describen solicitudes; no acreditan concesiones.
- https://siotuga.xunta.gal/siotuga/inventario?idconcello=27051&inv=1 — formulario
  público, HTTP 200. Devuelve el selector INE y un campo anti-CSRF anónimo.
- https://siotuga.xunta.gal/siotuga/assets/inventario/controls.min.js?2.5.0 — código
  público que identifica las consultas y cómo construir los enlaces documentales.
- `POST https://siotuga.xunta.gal/siotuga/assets/inventario/query_document.php`
  con `id=27051`, `idclase=14` (general) o `13` (desarrollo), y campo anti-CSRF.
  Son arrays JSON completos; el JS hace la paginación local con DataTables después
  de recibir todas las filas. No hay corte por número de filas en el adaptador.
  Un cambio a una respuesta con envoltorio/paginación provoca error explícito.
- `POST https://siotuga.xunta.gal/siotuga/assets/inventario/getIOTPU.php`
  con `iddoc`, `idp=0`, `lang=gl_ES` y campo anti-CSRF. Cada ficha devuelve datos
  generales y todos los grupos/componentes. Las URLs `url_ficha` conservan los
  parámetros de identificación; el sitio utiliza el POST desde su modal y puede
  requerir el campo anónimo actualizado para consultar esas URLs fuera del portal.

No se accede a cuentas ni credenciales. El campo de formulario se obtiene en cada
sesión pública. Las capturas de JSON no lo contienen.

## Resultado y agrupación

Las dos consultas actuales devuelven **7 entradas**. Resultado: **5 instrumentos**,
**1.516 enlaces documentales** (no se han descargado todos los documentos):

| ID SIOTUGA | Instrumento | Documentos |
| --- | --- | ---: |
| 27886 | PXOM, aprobación definitiva 2014-11-14 | 677, incluida corrección |
| 28692 | MP Nº1 do PXOM, aprobación definitiva 2024-10-09 | 40 |
| 28397 | PEPRICH do núcleo histórico, aprobación definitiva 2021-05-31 | 788 |
| 28312 | PE Protección das Catedrais, aprobación definitiva 2020-06-09 | 11 |
| 25393 | Estudio de detalle, Avda. Rosalía de Castro / estrada de Vilaselán, 2004-06-28 | 0 |

`28691`, «CE N1 PXOM», se agrupa con el PXOM 27886. La memoria oficial
https://siotuga.xunta.gal/siotuga/documentos/urbanismo/RIBADEO/documents/28691mx001.pdf
se descargó (HTTP 200) y su texto confirma «CORRECCIÓN DE ERROS Nº 1 DO PXOM» y
la aprobación por orden de 18/12/2024. Sus fechas se conservan en `correcciones`,
sin sustituir las del plan de 2014. Cada enlace conserva su ID de procedencia,
título y grupo. Los planos, memorias, catálogos y anuncios no generan proyectos
independientes. La modificación puntual sí es un instrumento separado.

Se excluye expresamente **25392**: el listado lo sitúa en Ribadeo (Rinlo), pero el
detalle declara `menutitle=Begonte` y `folder=BEGONTE`, sin componentes. No se
corrige por conjetura ni se atribuye a Ribadeo. El informe devuelve esta exclusión.
La ficha 25393 sí identifica Ribadeo; se conserva como instrumento documentado por
metadatos oficiales, con `documentacion_disponible=false`, sin inventar adjuntos.

## Fechas, estado y cobertura

`fechaaddef` se guarda en `fecha_aprob`; `fechadog`, `fechabop` y
`fechanormativabop` en campos separados de publicación DOG/BOP/normativa BOP.
`fecha` queda nula. No se infiere fecha de publicación municipal ni fecha de
acuerdo adicional. La fase se atribuye explícitamente al inventario de aprobados,
no a una revisión jurídica de vigencia. Se conserva `incidencias_iuris`.

Cobertura parcial: planeamiento general y de desarrollo del inventario actual.
Durante la investigación, clase 16 devuelve 11 entradas históricas, varias anuladas;
clase 18 devuelve null. Las capturas se conservan, pero estas categorías no se
incorporan al adaptador. Tampoco se incluyen instrumentos territoriales, todas las
obras públicas, contratación, noticias generales o registro de licencias.
La ausencia en este conjunto no significa inexistencia de otros instrumentos.

Geometría: el portal enlaza el visor https://siotuga.xunta.gal/siotuga/carto y su
JS menciona servicios WMS; las fichas utilizadas proporcionan planos PDF/JPG,
sin geometría vectorial verificada por expediente. No se extraen centroides ni
se vectorizan planos. `lat`, `lon`, `geometry` nulos; `geometry_status=unavailable`
y `publication_ready=false`. El anotador compartido clasifica las cinco entidades
como desconocidas; eso no acredita preparación para publicación ni ejecución.

## Validación reproducible y evidencia local

Desde la raíz del repositorio:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_ribadeo -v
```

**7 pruebas pasan**: fechas/procedencia, ausencia de coordenadas, lectura completa
con 100 filas y deduplicación, rechazo de paginación no soportada/formularios,
conflictos de municipio/fechas, documentos ausentes, agrupación de corrección y
licencias deshabilitadas sin red.

Extracción real ejecutada cargando `load_manifest('ribadeo')` y
`load_portal_adapter(manifest).backfill_proyectos(Path('evidence/proyectos.jsonl'))`,
con `manifest.portal.config['capture_dir']='evidence'`. `update_proyectos` hace la
misma instantánea completa; no mantiene un cursor ni elimina silenciosamente
expedientes por fecha. La salida se escribe atómicamente tras validar las fichas.

`evidence/validation.json` contiene `live_records=5`, URLs, exclusiones, número de
enlaces y limitaciones. Hay capturas de la página municipal, inventario, JS,
consultas JSON y siete fichas, además de memoria PDF y texto de la corrección.
La evidencia es local y no se incorpora como fuente versionada.

Manifest: `schedule.enabled=false`, `geocode.jitter_missing=false` y
`licencias.enabled=false`. Sin cambios compartidos, dependencias, despliegue o DB.
