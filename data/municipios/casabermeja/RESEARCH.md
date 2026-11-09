# Casabermeja — INE 29039, Málaga, Andalucía

Investigación y extracción verificadas el 2026-11-09. Un único adaptador municipal,
con fuente oficial autonómica alternativa y cobertura parcial explícita.

## Descubrimiento e inventarios

- Portal municipal: https://www.casabermeja.es/ — HTTP 202, cuerpo de 0 bytes.
  También ocurre sin `www`, por HTTP (redirige a HTTPS) y en `/6698`.
- El anuncio del canal municipal Bandomóvil
  https://www.bandomovil.com/casabermeja/1506344/0 identifica un **Avance del PGOM**
  y enlaza su documentación en
  https://www.casabermeja.es/6698/com1_md3_cd-80923/avance-pgom?com1_md=3 .
  Este destino municipal devuelve también HTTP 202 vacío. Se documenta el hallazgo,
  pero no se extrae como proyecto una noticia sin comprobar su documentación.
- Inventario oficial accesible: https://www.juntadeandalucia.es/medioambiente/daepu/ .
  Su formulario GET permite filtrar por Municipio (`filter5`), Actuación, Provincia,
  Tipo de Resolución y otros campos. La consulta empleada es
  https://www.juntadeandalucia.es/medioambiente/daepu/resolucions/find?find=findResolucionesFiltered&filter5=CASABERMEJA&page=1&size=10 .
  HTTP 200, cinco filas, «Página 1 de 1». Se valida **CASABERMEJA / MÁLAGA** en
  cada fila y detalle; un filtro ignorado provoca error, no incorpora otros municipios.
  Esta es una consulta actual de inventario, sin fijar una lista de noticias o IDs.

## Registros reales y agrupación

La extracción en vivo devuelve **3 instrumentos y 5 resoluciones ambientales**:

| Expediente ambiental | Instrumento | Resoluciones y detalle oficial |
| --- | --- | --- |
| EA/MA/69/19 | Modificación de las NN.SS. relativa al reajuste de dotaciones públicas en dos ámbitos del suelo urbano | Admisión a trámite, 2020-05-25: https://www.juntadeandalucia.es/medioambiente/daepu/resolucions/20340 |
| EA/MA/46/21 | Plan Especial de Ordenación de Sectores de Equipamiento | Admisión a trámite, 2021-10-28: https://www.juntadeandalucia.es/medioambiente/daepu/resolucions/30964 ; Documento de Alcance, 2024-06-24: https://www.juntadeandalucia.es/medioambiente/daepu/resolucions/44338 |
| EA/MA/30/22 | Plan Parcial de Ordenación del Sector PP-8 de las Normas Subsidiarias | Admisión a trámite, 2023-02-22: https://www.juntadeandalucia.es/medioambiente/daepu/resolucions/37960 ; Documento de Alcance, 2024-11-29: https://www.juntadeandalucia.es/medioambiente/daepu/resolucions/46660 |

Los documentos proceden de los enlaces `downloadFile` de cada detalle oficial.
Se preservan títulos originales, órgano tramitador, URL de resolución, URL del
inventario y procedencia documental. Se eliminan identificadores de sesión de las
URLs. Los paréntesis del expediente se normalizan para agrupar dos resoluciones
del mismo instrumento; cada documento conserva la URL del detalle del que procede.
La deduplicación utiliza expediente, URL de resolución y URL documental. Los IDs
permanecen estables si aparecen nuevas resoluciones del mismo expediente ambiental.
No se garantiza identidad común entre expedientes ambientales distintos de un plan.

Los cinco detalles enlazan **9 URLs PDF**, incluidos IAE y anuncio BOJA del primer
expediente. Hay copias del mismo Documento de Alcance con URLs distintas en los dos
últimos expedientes: se conservan sus enlaces y procedencias dentro de un instrumento,
sin generar proyectos adicionales. Los nueve PDF se descargaron y se verificaron
con `pdftotext` para confirmar instrumento y contenido.

Las fechas de las filas del inventario son **fechas de resolución ambiental**.
Las fechas de documentos conservan además `fecha_fuente` y el rótulo literal de la
columna, `campo_fecha_fuente: Fecha de Resolución`. En un adjunto «Publicación en
BOJA» ese rótulo es ambiguo: 2021-02-24 corresponde al anuncio; el PDF lleva cabecera
BOJA 42, 2021-03-04. Por ello su `fecha_resolucion` queda nula y no se deriva una
fecha de publicación del rótulo. Las fechas de los demás documentos se retienen
como ambientales. No son fechas de publicación ni de acuerdo
municipal, ni prueban aprobación inicial/definitiva urbanística o vigencia del plan.
`fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` quedan nulas. La admisión de
una evaluación ambiental no se presenta como licencia concedida. No se fija una
fase urbanística global a partir de la clase de resolución ambiental.

## Cobertura y comportamiento

Este inventario solo cubre instrumentos con resoluciones publicadas en la aplicación
EAE de la Junta. No es un censo de todos los planes, obras o licencias de Casabermeja.
La consulta solo identifica el municipio principal, no los listados como «Otros
Municipios». No se recorre el archivo general de noticias, contratación ni formularios.
La web municipal inaccesible impide cubrir su PGOM y otras posibles fuentes.
No se han verificado licencias concedidas: ambos métodos de licencias producen
vacío explícitamente deshabilitado.

Se recorre de 1 a N según «Página X de N», conservando el filtro y tamaño; no hay
límite de páginas silencioso. Si cambian el total durante el recorrido, el esquema,
las fechas, los identificadores o se repite una página sin progreso, se falla antes
de reemplazar el JSONL. Un inventario vacío requiere revisión. Cada resolución debe
tener documentación y detalle con municipio, provincia, expediente y fecha coherentes.
La actualización vuelve a consultar el inventario completo, sin watermark temporal.

## Geometría

`geometry_status: unavailable`. Las páginas de inventario y detalle verificadas no
exponen coordenadas ni una capa vectorial asociada a los expedientes. La documentación
PDF puede contener planos, pero no se georreferencia ni se digitaliza. No se obtiene
la geometría del término municipal como sustituto de la del proyecto. Coordenadas y
geometría quedan nulas; `publication_ready` es falso. No se afirma haber comprobado
un visor municipal inaccesible.

## Validación reproducible y evidencias locales

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Desde la raíz del repositorio:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_casabermeja -v
```

Cinco pruebas offline comprueban agrupación, deduplicación, semántica temporal,
rechazo de fuentes incorrectas/cambiadas, recorrido de dos páginas, rechazo de
paginación incoherente sin sobrescribir una salida anterior y licencias deshabilitadas.
La extracción real se ejecutó mediante `load_manifest` con la ruta explícita del
manifest y `load_portal_adapter`, invocando `backfill_proyectos`; no utiliza el
orquestador ni publicación. `portal.config.capture_dir` permite guardar las respuestas
HTML durante esa ejecución sin cambiar el manifest.

Evidencia no destinada a commit: `evidence/proyectos.jsonl` (3 registros reales),
`evidence/validation.json` (conteo, URLs consultadas, limitaciones y validaciones),
`evidence/captures/source-*.html` y capturas de los documentos oficiales.
El guard compartido de entidades se ejecuta al cargar por registro; clasifica estos
instrumentos como categoría desconocida (3/3), sin inventar una categoría inmobiliaria.
La revisión posterior debe tener en cuenta esta limitación y la ausencia de geometría.

Manifest con INE exacto, `schedule.enabled: false`, `licencias.enabled: false` y
`geocode.jitter_missing: false`. Sin cambios en fuentes compartidas ni dependencias.
