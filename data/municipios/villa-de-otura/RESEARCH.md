# Villa de Otura — Granada — INE 18149

Investigación y ejecución real: 8 de noviembre de 2026.

## Fuente elegida y cobertura

Inventario oficial municipal, enlazado desde el menú Transparencia:
https://ayuntamientodeotura.es/transparencia/nuevo-planeamiento-urbanistico-de-otura/

La página publica dos consultas previas, con PDF descargables:

- Plan de Ordenación Urbana (POU): https://ayuntamientodeotura.es/wp-content/uploads/2022/04/CONSULTA-PREVIA-DEL-PLAN-DE-ORDENACION-URBANA-DE-LA-VILLA-DE-OTURA.pdf
- Plan General de Ordenación Municipal (PGOM): https://ayuntamientodeotura.es/wp-content/uploads/2022/04/CONSULTA-PREVIA-DEL-PLAN-GENERAL-DE-ORDENACION-MUNICIPAL-DE-LA-VILLA-DE-OTURA.pdf

Los dos documentos se descargaron íntegros, con HTTP 200, Content-Type application/pdf y firma `%PDF-`. Se verificó su texto mediante `pdftotext`: contienen el objeto y alcance de cada plan y describen la consulta previa. Son instrumentos concretos en elaboración, no formularios de licencia ni anuncios de contratación. La extracción produce **dos registros**, uno por instrumento, con sus enlaces documentales. Duplicados del mismo enlace se eliminan; documentos adicionales con el mismo encabezamiento del instrumento se agrupan, manteniendo sus enlaces y títulos originales.

Cobertura deliberadamente parcial: únicamente las consultas previas de esa página, actualmente accesible. No representa el inventario completo del planeamiento vigente, todos los expedientes municipales ni obras públicas. La página observada no tiene paginación; se inspeccionan todos los enlaces del contenido, sin límite de registros. Si aparecen señales de paginación se aborta explícitamente para revisar el recorrido. No se hacen llamadas al formulario de participación.

## Otras fuentes investigadas y límites temporales

https://ayuntamientodeotura.es/tramites/descarga-de-documentos/ ofrece solicitudes y formularios; no acredita concesiones. Se excluye y se desactivan licencias.

Se localizaron y consultaron también las fichas oficiales autonómicas:

- https://www.juntadeandalucia.es/medioambiente/daepu/resolucions/53780 — POU, expediente EAE/2599/2026, con documentos ambientales posteriores.
- https://www.juntadeandalucia.es/medioambiente/daepu/resolucions/44602 — PGOM, expediente EAE-2478-2024, también con documentación ambiental posterior.

Esas fichas no se integran en este adaptador de inventario municipal. Su existencia confirma que **consulta previa es la fase del documento municipal extraído, no una afirmación sobre la fase actual**. No se deduce aprobación del plan de una resolución ambiental. El scraper tampoco convierte noticias o contratación en proyectos adicionales.

## Semántica y procedencia

Cada registro tiene INE, municipio y provincia exactos, URL del documento, `inventory_url`, y `documentos` con título, URL y página de procedencia. Los identificadores son estables por instrumento POU/PGOM. Se conserva el carácter documental mediante `fase_documentada`, sin asignar `fase` actual.

La marca del CMS de 2022 y el directorio de subida no se utilizan como fecha de publicación ni fecha de acuerdo. No se extraen fechas administrativas del cuerpo de estos documentos. No se afirma aprobación, licencia concedida ni vigencia. Sin coordenadas verificadas; `geometry_status: unavailable`, `publication_ready: false`. El manifiesto desactiva programación, licencias y jitter.

Los errores HTTP, cambios de contenedor, ausencia de documentos reconocidos, enlaces documentales ajenos al dominio oficial, redirecciones a otro dominio y respuestas que no sean PDF abortan la extracción. Se escribe la salida después de validar todos los documentos, de forma atómica. Update vuelve a consultar el inventario completo sin filtrar por fechas del CMS.

## Validación reproducible

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_villa_de_otura -v` — cinco pruebas correctas: agrupación y aislamiento de documentos, exclusión de formularios, normalización de acentos, rechazo de cambios/vacíos/enlaces externos, detección de paginación, carga del manifiesto por el registro y actualización completa, fallo de PDF sin sobrescribir salida anterior y licencias desactivadas.

Ejecución real: carga mediante `load_manifest('villa-de-otura')` y `load_portal_adapter`, configuración local `capture_dir='evidence'`, llamada a `backfill_proyectos(Path('evidence/proyectos.jsonl'))`. Resultado: dos registros; política de entidades compartida correcta, cero entidades desconocidas.

Evidencia local no destinada al commit: `evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/inventory.html`, ambos PDF completos y sus textos `pou.txt` / `pgom.txt`. El JSON de validación incluye recuento real, URLs y limitaciones. No se han usado bases de datos, publicación ni despliegue.
