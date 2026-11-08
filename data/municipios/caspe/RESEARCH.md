# Caspe — Zaragoza — INE 50074

Investigación y extracción en vivo: 2026-11-07. Se revisaron primero
`municipio/manifest.py`, `municipio/adapters/portal.py`, el registro de adaptadores
y los ejemplos de Hernani y Chipiona. No se modifican componentes compartidos.

## Fuentes oficiales y alcance

La página municipal [Urbanismo y Obras](https://www.caspe.es/urbanismo-y-obras/)
contiene una sección PGOU que enlaza explícitamente el
[archivo documental](https://www.caspe.es/pgou/). El archivo actualmente servido
es un índice Apache, con estos cinco subdirectorios además de su raíz:

- https://www.caspe.es/pgou/texto/
- https://www.caspe.es/pgou/texto/estudios_complementarios/
- https://www.caspe.es/pgou/planos/
- https://www.caspe.es/pgou/planos/informacion/
- https://www.caspe.es/pgou/planos/ordenacion/

Resultado real: **un instrumento con 62 documentos PDF**. Incluye memorias,
normas, estudio económico, fichas, catálogos, estudios complementarios y planos.
Se conserva cada URL y el índice donde fue descubierto. Los títulos documentales
proceden del nombre completo de archivo decodificado, porque el texto visible
de los enlaces está truncado. Los planos de redes existentes o propuestas se
mantienen como documentación del PGOU: no son obras independientes.

También se localizó en búsqueda la sede https://caspe.sedelectronica.es/ y
referencias regionales a modificaciones del PGOU. No se incorporan al scraper:
esta implementación cubre exclusivamente el archivo enlazado desde Urbanismo,
no todo el planeamiento posterior ni un histórico del tablón o de obras.
No se afirma que los 62 enlaces sean la versión consolidada vigente.

## Reglas y procedencia

La identificación del PGOU depende del enlace explícito dentro de su sección
municipal y de un árbol documental no vacío que incluya Normas Urbanísticas.
No hay registros precargados. El identificador `caspe-pgou` representa ese
instrumento municipal; todos sus documentos permanecen agrupados.

No se extraen formularios ni instrucciones de solicitud de obra mayor/menor,
licencia de actividad, ordenanzas genéricas, anuncios de contratación o noticias.
La presencia de estos trámites en Urbanismo no prueba licencias concedidas:
`licencias.enabled=false` y sus métodos producen salida vacía desactivada.

No se asignan fechas de publicación, acuerdo o aprobación: las marcas de
modificación del servidor y las fechas del CMS no acreditan ninguna de ellas.
No se inventan coordenadas, fases, promotores ni expedientes. Se explicita
`publication_ready=false`, geometría no disponible y cobertura parcial.
Programación y jitter desactivados en el manifest.

## Recorrido y fallos

Se recorren todos los subdirectorios enlazados dentro de `/pgou/`, deduplicando
visitas y documentos. Los enlaces de ordenación Apache `?C=...` no son páginas
adicionales. Se rechazan indicadores de paginación nueva, consultas dinámicas,
formatos de archivo inesperados y cambios del índice. No hay límite de registros
que recorte resultados: el límite de seguridad de 100 directorios aborta sin
reemplazar la salida anterior. Un fallo HTTP o una estructura vacía también
interrumpe la extracción. La actualización vuelve a leer el inventario completo
y reemplaza atómicamente el fichero tras terminar correctamente.

## Validación reproducible

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Comando: `python -m unittest municipio.test_caspe -v`: **7 pruebas correctas**.
Cubren descubrimiento contextual del PGOU, exclusión de formularios, nombres
completos y acentos, agrupación recursiva, deduplicación, actualización,
metadatos ausentes, fallos sin sobrescritura, archivos vacíos, paginación,
cambios de estructura, manifest y licencias desactivadas.

Se ejecutó realmente `CaspeAyuntamientoAdapter.backfill_proyectos` con el
manifest cargado. Evidencia local, no destinada a commit:
`evidence/proyectos.jsonl` (1 registro), `evidence/validation.json` (62 documentos,
URLs, limitaciones, hashes y relación de capturas), y HTML de las siete páginas
consultadas, incluida Urbanismo. Las capturas `source-*.html` corresponden a la
ejecución del adapter; las otras capturas HTML son de exploración previa.

Comprobación documental puntual:
https://www.caspe.es/pgou/texto/NORMAS%20URBANISTICAS.pdf respondió HTTP 200,
`application/pdf` y firma `%PDF-`. Se guardaron únicamente los primeros 1024 bytes
en `evidence/normas-prefix.bin`. No se descargó ni verificó jurídicamente cada
PDF; los demás documentos son enlaces descubiertos en el inventario oficial.
No se accedió a bases de datos ni se publicó ningún dato.
