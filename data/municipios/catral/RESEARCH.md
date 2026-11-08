# Catral — Alicante — INE 03055

Investigación y extracción real: 7 de noviembre de 2026.

## Fuentes oficiales y alcance

El [inventario municipal de urbanismo y medio ambiente](https://transparencia.catral.es/informacion-de-relevancia-juridica/urbanismo-y-medio-ambiente/)
enlaza expresamente «Planeamiento urbanístico vigente de Catral» al
[directorio RAIP de la Generalitat para 03055 CATRAL, provincia de Alicante](https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/2%20ALICANTE/03055%20CATRAL/).
El adaptador comprueba ese enlace en cada ejecución y recorre íntegramente el árbol
municipal del registro autonómico, tanto P. GENERAL como P. DIFERIDO.

Resultado real: **5 instrumentos y 66 enlaces PDF**, en 28 directorios más la página
municipal. Los identificadores son 03055-1000 (1997-0774 HOMO Y MOD PG),
03055-1001 (PGMOD ampliac. UE-C 2019-0083), 03055-1002 (1994-0181 PGMOD
ADAPT. LEY 4-92), 03055-1100 (PGMOD Nº1) y 03055-0010 (2009-0334 PE RESERVA
SUELO DOT). Los títulos conservan la denominación del registro, sin expandir sus
abreviaturas ni convertir los años de expediente en fechas de aprobación.

Un registro representa un instrumento identificado por su número RAIP. Sus acuerdos,
publicaciones en boletines, memorias, normas, documentos paisajísticos, planos y
certificados de inscripción quedan agrupados en `documentos`, con título, URL,
sección y directorio de procedencia. No se crean proyectos separados por cada plano
o publicación. No se inventa un PGOU completo a partir del encabezado de categoría.

Los directorios Apache observados no tienen paginación; los enlaces de ordenación
no son páginas adicionales. Se recorren todas las carpetas y se eliminan duplicados
de enlace. Una página con consultas desconocidas o paginación, un directorio vacío,
un enlace fuera del municipio, o un instrumento sin documentos provoca error. El
límite defensivo de 500 directorios también provoca error, nunca salida truncada.
El JSONL se escribe después de finalizar el recorrido. Los nombres históricos del
servidor mezclan HTML UTF-8 y Latin-1; se preservan los href codificados originales,
incluidos los escapes Latin-1 de algunas carpetas de aprobación.

## Comprobación documental y semántica

Se descargaron dos PDF de muestra, ambos HTTP 200, `application/pdf` y firma `%PDF-`,
y se examinó su texto con `pdftotext`:

- Certificado de inscripción de 03055-1001: identifica Catral y la «Modificación
  Puntual del Plan General #Ampliación UA-C#», aprobación definitiva 06/10/2020 e
  inscripción 26/10/2020. Esas son fechas distintas; el directorio dice UE-C y el
  certificado UA-C. Se mantiene el título del inventario sin corregirlo por inferencia.
- Publicación BOP de 03055-1100: boletín nº 113 de 14/06/2019; el texto cita la
  sesión plenaria de 03/05/2019 y la aprobación definitiva de la modificación nº 1.
  La fecha del boletín no es la del acuerdo.

Estas lecturas puntuales verifican que hay instrumentos reales; el adaptador no
extrae texto PDF ni fija estas fechas manualmente. Todos los registros dejan
`fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` a null. Tampoco infiere fase,
vigencia jurídica actual, coordenadas ni geometría. `publication_ready` es false.
La política compartida de entidades se ejecutó mediante el cargador del registro:
5 entidades de categoría desconocida, resultado `ok`; no se adjudica uso residencial.

## Cobertura parcial y exclusiones

El alcance es el inventario documental RAIP enlazado por el Ayuntamiento, no un
histórico completo de actuaciones municipales. La etiqueta municipal «vigente» se
conserva como contexto de procedencia, sin certificar la vigencia individual.
La página municipal incluye también planes de emergencias, quemas y clima, que no
se ingieren como instrumentos urbanísticos o proyectos físicos. Su enlace aislado
«Modificación puntual nº del PGOU de Catral» tiene un título incompleto y no se
convierte en un sexto proyecto ni se asocia por suposición a un expediente RAIP.
No se incluyen formularios, convocatorias de contratación ni noticias generales.
No se ha verificado un inventario de licencias concedidas: `licencias.enabled` es
false. También se desactivan la programación y el desplazamiento aleatorio de
coordenadas faltantes.

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_catral -v`: **7 pruebas correctas**, de agrupación,
procedencia documental, ausencia de fechas/geométricas inferidas, enlaces fuera de
ámbito, estructura vacía, paginación, codificaciones, integración con el manifest y
cargador, actualización como snapshot y conservación de la salida ante error.

Extracción real ejecutada con `load_manifest('catral')`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `capture_dir` apuntando a
`evidence/live-sources`. Sin instalación de dependencias, base de datos ni publicación.
La evidencia local incluye `proyectos.jsonl`, `validation.json` (5 registros reales,
66 documentos, las 29 URL de fuente y limitaciones), capturas de todas las páginas
consultadas y dos muestras PDF con texto y procedencia. La evidencia no forma parte
de los cuatro archivos fuente entregados.
