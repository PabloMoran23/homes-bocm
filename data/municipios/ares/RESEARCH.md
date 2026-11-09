# Ares — INE 15004, A Coruña (Galicia)

Investigación y ejecución en vivo: 9 de noviembre de 2026.

## Fuentes descubiertas y alcance elegido

- [Inventario municipal de planes](https://concellodeares.gal/es/planes/): página oficial con un instrumento identificado, el documento refundido del Plan Xeral de Ordenación Municipal de Ares (PXOM 2020). Es la fuente del adaptador. Su bloque documental contiene **91 enlaces PDF**, agrupados en un único registro, incluyendo índices, memoria, normativa, catálogo, informes y planos. Los planos de calles o redes no se convierten en obras independientes. Se conservan las etiquetas y secciones de cada enlace y su página de procedencia.
- [Inventario provincial POS+ de Ares](https://plan-unico.dacoruna.gal/ares/): inventario oficial adicional, con 31 entradas bajo obras aprobadas al consultar. Incluye también suministro de maquinaria y presenta las mismas entradas como tarjetas y tabla. Se captura como investigación; **no está incluido** en este adaptador de planeamiento. No se afirma cobertura de todas las obras municipales.
- [Comunicación municipal sobre los ámbitos suspendidos](https://concellodeares.gal/es/el-concello-de-ares-recibe-la-aprobacion-de-los-dos-ambitos-suspendidos-de-su-pxom/): noticia publicada el 15/01/2025 que informa de la notificación recibida el 13 de enero sobre Seselle y Punta da Pena. Se conserva como contexto para demostrar el límite de la versión 2020; no se convierte en otro proyecto ni se utiliza la fecha de la noticia como aprobación. Tampoco se incorpora como si fuera un documento técnico del inventario.

La extracción representa una versión documental real de un instrumento, no un inventario jurídico completo del planeamiento vigente. Excluye correcciones posteriores y la documentación posterior de los ámbitos suspendidos. No se ha verificado un registro público de licencias concedidas: formularios, anuncios de contratación y noticias ajenas no son registros de licencias ni proyectos.

## Identidad, documentos y fechas

Se exige el título específico del plan, la versión 2020, el párrafo de procedencia y los documentos centrales de índice, memoria y normativa. La identidad estable es `ares-pxom-2020`. No se genera una entrada a partir de una simple navegación a urbanismo. Las 91 URL se descubren de nuevo en cada ejecución, sin lista documental precargada. Duplicados de URL se agrupan, conservando su primera etiqueta y sección.

`fecha_aprob = 2020-02-05` se extrae únicamente del párrafo que identifica la orden de aprobación de esa versión. No expresa aprobación íntegra actual ni fecha del documento refundido. `fecha_aprob_provenance` conserva párrafo, enlace y alcance. `fecha_publicacion`, `fecha_acuerdo` y `fecha` quedan nulas: no se reutilizan fechas de carpetas WordPress, actualización del CMS, publicación de noticias o registro como si fueran acuerdos. `fase` describe la versión documental; `fase_fuente` conserva el encabezado del inventario, sin afirmar que todo el territorio estuviera aprobado en 2020.

La geometría y coordenadas permanecen nulas. Los mapas enlazados no equivalen a geometría extraída. `publication_ready=false`, `schedule.enabled=false`, `geocode.jitter_missing=false` y `licencias.enabled=false`.

## Paginación y fallos

La fuente observada es una página estática completa sin paginación, con 91 PDF en su bloque de texto. No hay topes de documentos o páginas. Si aparecen marcadores de paginación el adaptador falla explícitamente para evitar un resultado incompleto. También falla ante redirecciones ajenas, inventarios ambiguos, secciones desconocidas, fechas inválidas, cambios de versión y ausencia de los documentos centrales. Una descarga o validación fallida no reemplaza la salida previa. `update_proyectos` refresca la instantánea completa sin recortar por fecha.

## Verificación reproducible

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_ares -v
```

Resultado: 10 pruebas correctas. Cubren agrupación, procedencia, fechas, ausencia de geometría inventada, exclusión de navegación/formularios, duplicados, paginación, origen, cambios de inventario, fallos de red, refresco, capturas y manifest.

Ejecución real: `AresAyuntamientoAdapter`, construido con el manifest y `capture_dir=evidence`, seguido de `backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **1 registro, 91 documentos**. El resultado y las limitaciones están en `evidence/validation.json`. No se ejecutó ningún pipeline de publicación o acceso a bases de datos.

Capturas locales (no fuentes para el parser en producción): `planes.html` (respuesta de la ejecución real), `pos.html`, `ambitos-contexto.html`. Se descargaron íntegramente dos documentos descubiertos en el inventario, ambos con HTTP 200, tipo `application/pdf` y firma `%PDF-`: índice (`indice.pdf`, 665567 bytes) y normativa (`normativa.pdf`, 5206832 bytes). La primera página de la normativa confirma el plan y la orden de 05/02/2020. `normativa.txt` y `normativa-extract.txt` contienen extracción local mediante `pdftotext`. Los restantes 89 PDF se conservan como enlaces de procedencia sin afirmar que todos sus contenidos se hayan descargado y verificado.
