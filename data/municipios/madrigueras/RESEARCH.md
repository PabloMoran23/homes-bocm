# Madrigueras — Albacete — INE 02045

Investigación y extracción real: 9 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento y cobertura

Se revisaron el contrato `municipio/adapters/portal.py`, el cargador de manifiestos
y los ejemplos de Chipiona, Hernani y Manlleu antes de implementar el adaptador.

La [web oficial municipal](https://madrigueras.es/) enlaza directamente su
[inventario Anuncios](https://madrigueras.es/anuncios/). Se inspeccionaron también
[Mapa Web](https://madrigueras.es/mapa-web/), [Áreas](https://madrigueras.es/areas/)
y [Normativa Municipal](https://madrigueras.es/normativa-municipal/).
Áreas no mostraba inventario; Normativa contiene ordenanzas, reglamentos y planes
no físicos, que no se convierten en proyectos. La portada contiene noticias y
programas de empleo que tampoco se consideran proyectos por su mera publicación.
El directorio estatal identifica el Ayuntamiento de Madrigueras en Albacete con
unidad orgánica L01020450:
https://administracion.gob.es/espanaadmon/quienesquien/entidades-locales-ayuntamientos-estructuras-y-directorios?idUniOrganica=L01020450&idioma=eu&imprimir=1

El inventario Anuncios es un acordeón HTML con cinco secciones observadas, todas
inspeccionadas. Una identifica una **obra física concreta**, no una convocatoria
ni licitación: modernización y mejora de las infraestructuras del colegio de
primaria San Jorge de Madrigueras (Albacete). La ficha publica el código de
operación **ES302039/2018/1802/101**, coste total **63.974,78 €** y cofinanciación
FEDER del 80 %. El adaptador lee estos campos de la respuesta viva; no contiene
el título, código ni importe de esta obra como registros precargados.

Se obtiene **1 registro** en la ejecución real. La cobertura se limita a las
operaciones FEDER físicas estructuradas de esa página. No es un inventario
exhaustivo del planeamiento ni de todas las obras del municipio. No se afirma
que una operación histórica esté actualmente en ejecución. El texto municipal
habla de obras realizadas, pero no se traduce en una fase administrativa.

## Procedencia, documentos y fechas

La URL conserva el fragmento de la sección municipal:
https://madrigueras.es/anuncios/#elementor-tab-content-8493

La propia ficha HTML constituye la documentación de la operación; no había un
proyecto técnico PDF adjunto a esa sección. Los PDF de ordenanzas y de normas de
biblioteca de las secciones vecinas quedan excluidos. Si aparecen enlaces en la
sección de una operación, se retienen en `documentos`, con su URL de procedencia.
Las fichas con el mismo código se agrupan; las discrepancias de datos provocan
error. No se agrupan instrumentos diferentes por palabras del título.

No se extraen fechas: no hay fecha de publicación, acuerdo o aprobación
verificada para esta operación. Los años del programa FEDER 2014–2020 y del
código de operación no son fechas de aprobación. El acuerdo de 30/04/2021 citado
en otra sección corresponde a normas de biblioteca y no se atribuye a la obra.
Las rutas de subida del CMS tampoco se interpretan como fechas de acuerdo.

No hay coordenadas ni geometría verificadas. Cada registro declara
`publication_ready: false` y `geometry_status: unavailable`. La anotación común
`entity_policy` queda en `pendiente / insufficient_identity_evidence`: el código
FEDER se conserva como `codigo_operacion`, sin fingir que sea un número de
expediente urbanístico. El adaptador no altera las reglas compartidas ni habilita
publicación. Licencias desactivadas por no disponer de registro público verificado
de concesiones. Programación y jitter desactivados en el manifiesto.

## Integridad y validación

Se recorre el acordeón entero, sin límites de registros ni cortes por fecha.
No se observó paginación en esta fuente. Si aparecen enlaces de página siguiente
o navegación paginada, el parser falla para exigir revisión del rastreo; no
entrega silenciosamente una primera página. También falla ante pérdida de la
estructura, ausencia de operaciones físicas o campos ambiguos. Se escribe la
salida de forma atómica, después de validar la respuesta.

Comando de pruebas ejecutado:

```text
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_madrigueras -v
```

Resultado: ocho pruebas correctas. Cubren los campos reales, ausencia de fechas
inventadas, exclusión de formularios y documentos vecinos, agrupación y estabilidad
de identidad, duplicados contradictorios, estructura inválida, paginación,
restricciones municipales/físicas, manifiesto y actualización del adaptador.

Extracción HTTP real ejecutada con `load_manifest('madrigueras')`,
`load_portal_adapter(...)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
La fuente respondió HTML válido. Evidencia local, sin publicar ni incorporar al
código fuente:

- `evidence/proyectos.jsonl`: un registro extraído y anotado por el cargador común.
- `evidence/validation.json`: cantidad viva, fuentes, limitaciones, hash de captura
  y resultado de clasificación común.
- `evidence/anuncios-live.html`: respuesta exacta capturada por el adaptador.
- `evidence/home.html`, `anuncios.html`, `areas.html`, `normativa-municipal.html`,
  `mapa-web.html`: capturas de descubrimiento.

No se han utilizado bases de datos, credenciales ni herramientas de despliegue.
