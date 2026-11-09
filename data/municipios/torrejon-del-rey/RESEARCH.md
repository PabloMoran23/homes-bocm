# Torrejón del Rey — Guadalajara — INE 19280

Investigación y extracción en vivo: 9 de noviembre de 2026.

## Inventarios oficiales examinados

- [Web municipal](https://www.aytotorrejondelrey.com/), [Urbanismo, Obras e Infraestructuras](https://www.aytotorrejondelrey.com/?page_id=293) y [Transparencia](https://www.aytotorrejondelrey.com/?page_id=456). Las páginas examinadas de concejalías describen responsables, sin un inventario técnico utilizable. El dominio sin `www` produjo un bucle de redirecciones durante la investigación; el dominio `www` respondió 200. El subdominio `prueba` también sirvió estas páginas, pero no se utiliza como fuente del adaptador.
- [Portal de transparencia de la sede electrónica](https://torrejondelrey.sedelectronica.es/transparency/): árbol de carpetas mediante Wicket con enlaces de sesión. No se extrajo de él un registro de licencias concedidas ni se afirma haber recorrido sus carpetas. Los formularios, ofertas de empleo, contratación y noticias no se convierten en proyectos.
- [Información autonómica sobre instrumentos municipales](https://urbanismo.castillalamancha.es/planeamiento/planeamiento-municipal/instrumento-planeamiento-municipal): página informativa general; por sí sola no es un instrumento de Torrejón del Rey.
- **Fuente implementada:** [Registro oficial autonómico de PAU de Guadalajara](https://urbanismo.castillalamancha.es/registros/pau-gu), [inventario municipal filtrado](https://urbanismo.castillalamancha.es/registros/pau-gu?municipio=1007). Publica fichas registrales concretas de programas municipales. La JCCM es el organismo que publica la fuente, no el Ayuntamiento. Se preserva esa procedencia en `source`, `origen` y `organismo_fuente`. El valor `proyectos.source: ayuntamiento` es la ruta local de carga del adaptador en el esquema existente; no atribuye a la web municipal la publicación del registro autonómico.

Se excluyeron resultados relativos a Torrejón de Ardoz, Torrejón de Velasco y otros municipios. El filtro autonómico se descubre por el nombre exacto del municipio en cada ejecución; `1007` es una clave taxonómica de la JCCM, **no** el INE. Cada ficha debe además declarar GUADALAJARA y Torrejón del Rey.

## Resultado y unidad de extracción

**8 instrumentos reales**, extraídos del inventario vivo y de sus ocho fichas mediante `backfill_proyectos`, cargado con `load_portal_adapter(load_manifest('torrejon-del-rey'))`.

| Instrumento (título abreviado) | Fecha de aprobación indicada por la ficha |
| --- | --- |
| PAU sector I-8, suelo urbanizable industrial | 2011-04-13 |
| PAU sectores I-2 e I-3 | 2011-02-15 |
| PAU Ampliación del Señorío de Muriel | 2005-05-11 |
| Modificación PAU sector 3, zona 1 | 2003-07-09 |
| PAU sector I-7 | 2002-12-05 |
| PAU zona III del sector de las NNSS | 2002-12-05 |
| PAU sector 3, zona 1, Las Eras de San Sebastián | 2000-06-02 |
| PAU sector I-6 industrial | 1999-12-03 |

Cada ficha registral genera un registro. La modificación del sector 3 es un instrumento registral distinto del PAU original, con su propia inscripción. Los documentos/enlaces de una misma ficha se agrupan en `documentos`, sin registros adicionales por archivo. En la extracción actual las ocho fichas carecen de enlaces a anexos técnicos; se conserva la URL específica de cada ficha, sin inventar PDFs. Se retienen agente urbanizador, uso, inscripción y observaciones cuando existen.

El inventario filtrado actual sirve las ocho filas en una sola página, sin controles de paginación. El adaptador sigue todos los enlaces del paginador y `rel=next` conservando el filtro; deduplica fichas y falla si el recorrido supera el límite de seguridad, falta contenido o una página sale del municipio. No entrega un resultado parcial silencioso.

## Fechas y límites de cobertura

- `fecha_aprob` procede únicamente del campo **Fecha de aprobación** de la ficha, no de la columna del listado, titulada **Fecha de constitución**. No se infiere el grado de aprobación: `fase` es nulo.
- `fecha_publicacion` procede únicamente del campo **Publicación en el DOCM**, presente en seis fichas. En esas seis fichas la fecha DOCM es anterior a la aprobación indicada. Se conservan ambos valores tal como los publica el registro, sin afirmar que la publicación corresponda a la aprobación final o resolver la discrepancia mediante suposiciones.
- En I-8 e I-2/I-3 se conservan las menciones al BOP en `observaciones`; no se promueven sus fechas ni las de reparcelación a fechas normalizadas del PAU. `fecha` y `fecha_acuerdo` permanecen nulos.
- La cobertura es **parcial**: PAU inscritos en este registro autonómico, con fechas de aprobación observadas entre 1999 y 2011. No cubre todos los planes, modificaciones, obras públicas o actuaciones recientes. La publicación actual de una ficha histórica no prueba vigencia, ejecución ni concesión de licencia.
- No hay geometría verificada. `lat`, `lon` y `geometry` son nulos y `publication_ready` es falso. `licencias.enabled`, `schedule.enabled` y `geocode.jitter_missing` están desactivados.
- El anotador compartido del repositorio clasifica las ocho filas como `pendiente / insufficient_identity_evidence`: no reconoce las referencias registrales conservadas en `datos_inscripcion`. Se mantiene esa clasificación y no se inventa un número de expediente para cambiarla. La revisión y publicación siguen pendientes.

## Validación reproducible y evidencia local

Runtime usado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_torrejon_del_rey -v
```

Resultado: **8 pruebas correctas**, cubriendo identidad municipal, fechas independientes, rechazo de formularios/contenido ajeno, agrupación de enlaces, duplicados, paginación, fallo sin salida parcial, manifiesto y licencias desactivadas.

Ejecución real, sin pipeline de publicación:

```python
from pathlib import Path
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter
manifest = load_manifest('torrejon-del-rey')
manifest.portal.config['capture_dir'] = 'evidence/live-captures'
adapter = load_portal_adapter(manifest)
result = adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))
```

Evidencia no destinada a commit: `evidence/proyectos.jsonl` (8 filas), `evidence/validation.json` (recuento, URLs, limitaciones, resultado y clasificación compartida), `evidence/live-captures/` (HTML del inventario provincial, filtro municipal y ocho fichas, nombres derivados de SHA-256 de la URL). Otras capturas de descubrimiento también se guardan bajo `evidence/`. No se accedió a bases de datos ni se ejecutaron geocodificación, publicación o despliegues.
