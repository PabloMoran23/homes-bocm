# Las Cabezas de San Juan — Sevilla — INE 41020

Investigación y extracción real: 7 de noviembre de 2026. Se revisaron primero
`municipio/manifest.py`, `municipio/adapters/portal.py`, el registro de adaptadores
y los ejemplos de Chipiona y Hernani. No hay cambios en código compartido.

## Fuentes oficiales y alcance

- [PGOM: Plan General de Ordenación Municipal](https://www.lascabezasdesanjuan.es/es/pgom/).
  La sección municipal contiene una tabla documental de **44 enlaces**: inicio
  de redacción, programa de trabajo y participación, diagnóstico, avance,
  documento inicial estratégico, memoria, anexos, cartografía y otros documentos
  del mismo instrumento. Se conserva también el enlace de galería sin extensión
  PDF que el propio inventario etiqueta como PDF. No se presupone que dos enlaces
  de títulos similares correspondan a archivos distintos: se retienen como
  enlaces publicados, sin afirmar un recuento de documentos binarios únicos.
- [Plan parcial sector SUBS-R.2 Ranchillo](https://www.lascabezasdesanjuan.es/es/plan-parcial-sector-subs-r.2.-ranchillo/).
  Descubierto en la navegación de la web municipal. Contiene **un enlace** al
  documento de avance del plan parcial de ordenación del sector SUBS-R.2.

Ambas son secciones documentales de instrumentos identificados, no noticias,
formularios ni anuncios de contratación. Cada una produce **un registro** con
todos sus enlaces documentales y procedencia. Los títulos proceden del
encabezado de cada sección; no se genera una actuación genérica a partir de la
página de inicio municipal. Los identificadores locales son estables por
instrumento y no pretenden ser números oficiales de expediente.

Se localizó asimismo el
[inventario histórico del PGOU en Transparencia](https://transparencia.lascabezasdesanjuan.es/es/transparencia/indicadores-de-transparencia/indicador/Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan-00071/),
cuyos resultados indexados muestran paginación `pagegalleryfiles-1-1` hasta al
menos la página 10. **No se extrae este inventario**: queda fuera del alcance
de este adaptador, al igual que las modificaciones que puedan estar en otras
secciones. No se presenta esta cobertura como un registro exhaustivo municipal.

## Extracción y semántica

El adaptador consulta siempre las dos secciones, valida su encabezado y las
tablas Nombre/Tamaño/Tipo, y agrupa enlaces de galería PDF por instrumento.
Deduplica por URL dentro de cada instrumento. Los enlaces externos a las tablas
no generan registros. Las tablas observadas son completas en HTML y no muestran
paginación. Si aparece paginación, falta una fuente, cambia un encabezado o hay
filas inesperadas, falla sin sustituir la salida anterior. No hay límite de
filas, corte temporal ni truncamiento. `update_proyectos` repite la instantánea
completa; no promete reconstruir documentos retirados del portal.

No se extraen fechas: las fechas incluidas en nombres de archivo no acreditan
publicación, acuerdo ni aprobación del instrumento completo. Una resolución de
aprobación del programa de trabajo tampoco significa aprobación definitiva del
PGOM. Se conservan los títulos originales de los documentos sin convertirlos en
estados o fases del instrumento. No se inventan coordenadas, geometría, licencias
concedidas ni ejecución de obras. `publication_ready=false` y
`geometry_status=unavailable`. Licencias, programación y jitter geográfico están
desactivados en el manifest.

La ejecución mediante el cargador real añade la política compartida de entidades:
los dos registros quedan `pendiente / insufficient_identity_evidence`, con
`activity_eligible=false`. Son instrumentos documentados, pero el clasificador
compartido no los habilita como actividad publicable. No se fuerza una referencia
de expediente ni se modifica esa política para eludir esta limitación.

## Validación reproducible

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_las_cabezas_de_san_juan -v`

Resultado: **5 pruebas correctas**. Cubren agrupación y deduplicación, enlace sin
extensión, procedencia, aislamiento de instrumentos, identificadores estables,
ausencia de fechas/coordenadas inferidas, rechazo de cambios y paginación,
manifest, escritura completa y conservación de salida ante fallo de una fuente.

Extracción en vivo mediante `load_manifest`, `load_portal_adapter` y
`backfill_proyectos`, con `config['capture_dir']='evidence'`:
**2 registros, 45 enlaces documentales**. Capturas y resultados locales:

- `evidence/proyectos.jsonl`: registros reales con la anotación compartida.
- `evidence/validation.json`: recuentos, fuentes, limitaciones, hora UTC, hashes
  de capturas y comprobaciones de documentos.
- `evidence/pgom.html` y `evidence/ranchillo.html`: HTML utilizado por el adaptador.
- `evidence/*.pdf.prefix`: 1.024 bytes por documento comprobado.
- `evidence/proyectos.entities.json`: informe generado por el cargador común.

Se verificaron el documento integrado de fase II del PGOM y el avance de
Ranchillo: ambos respondieron HTTP 206, `application/pdf`, firma `%PDF-`.
Solo se descargaron sus primeros 1.024 bytes. No se han verificado todos los
enlaces ni analizado íntegramente los PDF; no se afirma su vigencia jurídica.
La evidencia es local y no forma parte de los cuatro archivos fuente entregados.
No se accede a bases de datos ni se publica o despliega nada.
