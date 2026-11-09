# La Campana (Sevilla), INE 41022

Investigación y extracción real: 9 de noviembre de 2026. Se revisaron el contrato
`municipio/adapters/portal.py`, el cargador y esquema de `municipio/manifest.py`,
los adaptadores y manifests de Chipiona y Manlleu antes de implementar.

## Fuentes oficiales y alcance

La portada municipal https://www.lacampana.es/ enlaza la sección
https://www.lacampana.es/inicio/obras-servicios. Es un archivo público de noticias
municipales de Obras y Servicios, accesible actualmente, con **cinco páginas** y
30 entradas visibles, algunas duplicadas. No es un registro completo de proyectos
ni un inventario de licencias. Se descarga entero siguiendo `Siguiente` y se
comprueba el contador `Página N de M`, sin límite de páginas ni corte silencioso.
Una desaparición de estructura, página omitida, ciclo o total cambiante causa error.

La extracción comprobada produce **seis actuaciones físicas**: mejoras de Nueva,
Perdiz y Tenería (aviso 19/10/2017); Atraviesa (23/10/2017); Doctor Fleming y Murillo
(22/10/2016); Pregonero (10/01/2017); Nueva (10/12/2016); mejora y adaptación a
normativa de Plaza de Andalucía (14/01/2017). Nueva en 2016 y la actuación conjunta
de 2017 tienen avisos y ámbitos distintos; no se presupone que sean una sola obra.

Se exige descripción explícita de comienzo de obras, calle/plaza identificada y
aviso municipal enlazado en `Avisos_Obras`. No se convierte el título genérico
«Información municipal» en proyecto: se usa la descripción concreta. Se excluyen
servicios de basuras, jornadas, planes de tráfico y limpieza, reuniones sobre
adjudicación y formularios. Los cortes de calle aislados de Jilguero y Párroco D.
Fernando Villalba Guerra no bastan para verificar una actuación pública concreta
y quedan excluidos. Los avisos de Doctor Fleming/Murillo repetidos se agrupan por
URL documental, conservando ambas páginas de procedencia. Los documentos de cada
actuación permanecen juntos en `documentos`. No hay OCR: las descripciones se leen
del HTML; las imágenes enlazadas se conservan como documentos originales.

## Otras rutas investigadas

La portada enlaza el indicador oficial de PGOU:
http://transparencia.lacampana.es/es/transparencia/indicadores-de-transparencia/indicador/Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan-00063/
La petición redirige a HTTPS y responde **401**, sin inventario legible.

Se localizaron documentos de Diputación en
https://3web.dipusevilla.es/planeamiento/lacampana/ANSPGOU_MEMORIA_ORDENACION.pdf
y `ANSPGOU_ANEXO_N.U.pdf`. La carpeta y la memoria agotaron el tiempo de conexión;
los resultados indexados no se usan como extracción viva ni como prueba de vigencia.
No se ha verificado un registro público de licencias concedidas. Cobertura parcial:
solo anuncios históricos de comienzo de obra de 2016–2017, sin garantías de
terminación o estado de ejecución actual, ni cobertura del archivo general de noticias,
la sede, todos los instrumentos de planeamiento o las contrataciones municipales.
Contenido ajeno en el pie de la web no se procesa: solo los artículos del archivo.

## Semántica y validación

Las fechas visibles al comienzo de los artículos se guardan como
`fecha_publicacion`, distintas de las fechas de inicio descritas en el texto.
`fecha_acuerdo` y `fecha_aprob` permanecen nulas. La fase significa únicamente
«comienzo de obras anunciado», sin afirmar ejecución comprobada hoy. No se inventan
coordenadas ni geometrías; `publication_ready: false`. INE y provincia constan en
cada registro y en el manifest. Licencias, programación y jitter desactivados.
Actualización equivale a refrescar el archivo entero, porque no está ordenado
cronológicamente y contiene duplicados. Una extracción fallida no sobrescribe la
salida anterior por errores de red o paginación.

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Pruebas: `-m unittest municipio.test_la_campana -v`, **7 correctas**: semántica,
exclusiones, procedencia, deduplicación, recorrido completo y rechazo de paginación
incompleta/cíclica. Ejecución viva mediante
`LaCampanaAyuntamientoAdapter(config={'evidence_dir': 'evidence'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, cinco capturas `archive-N.html`, capturas de investigación
y los seis avisos JPG verificados con HTTP 200 y firma JPEG. Los enlaces exactos,
contador vivo, fecha UTC y limitaciones constan en validation.json y en cada registro.
No se utilizaron bases de datos, publicación, despliegue ni geocodificación.
