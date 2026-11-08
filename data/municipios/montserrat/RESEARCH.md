# Montserrat — Valencia — INE 46172

Investigación y extracción en vivo: 2026-11-07. Adaptador limitado al inventario
documental de planeamiento publicado por la Generalitat Valenciana para este
municipio. No confundir con Monistrol de Montserrat (Barcelona) ni con el
territorio británico de Montserrat.

## Fuentes oficiales descubiertas

- [Ajuntament, índice municipal](https://montserrat.es/ajuntament/): la consulta
  mediante navegador de investigación muestra un enlace «PGOU» al Registro
  Autonómico de Instrumentos de Planeamiento Urbanístico, con el parámetro
  `/auto/urbanismo/reg-planeamiento/4 VALENCIA/46172 MONTSERRAT/`.
  El enlace usa el dominio anterior `politicaterritorial.gva.es`; su redirección
  apunta a `mediambient.gva.es`. El acceso HTTP directo desde Python a la web
  municipal agotó el tiempo de espera. No se usa una copia de buscador como
  entrada de la extracción.
- [Departamento municipal de Urbanisme](https://montserrat.es/administracio-i-tramits/departaments/urbanisme/):
  información del servicio y tramitación de licencias, no un registro de
  concesiones. Se descarta como fuente de filas de actividad.
- [Directorio oficial GVA de Montserrat](https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/4%20VALENCIA/46172%20MONTSERRAT/):
  HTTP 200 real desde el runtime solicitado. Es el subdirectorio específico
  identificado por el enlace municipal. Contiene `1 P. GENERAL/`, que contiene
  el expediente `46172-1000 PG 2015-0087/`.
- [Expediente del Plan General](https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/4%20VALENCIA/46172%20MONTSERRAT/1%20P.%20GENERAL/46172-1000%20PG%202015-0087/):
  inscripción registral y seis carpetas: aprobación, memoria, normas, planos,
  catálogo y otros. El recorrido completo obtiene **57 PDF**, agrupados en
  **un instrumento**, sin convertir cada plano o norma en un proyecto distinto.
- [Archivo municipal de Urbanisme i medi ambient](https://montserrat.es/category/urbanisme-i-medi-ambient/):
  la investigación web muestra noticias sobre obras físicas, además de ayudas,
  anuncios y otros contenidos. No se incluye este archivo editorial en el
  adaptador, ni se afirma haber cubierto su paginación. Tampoco se extraen
  convocatorias de plenos como si fueran acuerdos adoptados o licencias.

El BOP y el acuerdo de aprobación se descargaron adicionalmente a evidencia
local para comprobar que el expediente corresponde a un instrumento real.
`BOP.pdf` empieza con el anuncio de aprobación definitiva del Plan General de
Montserrat, expediente 20150087, en el BOP de Valencia n.º 139, **19-VII-2018**.
Esa es la fecha de publicación del boletín, no una fecha de acuerdo. El archivo
`ACUERDO.pdf` es un documento escaneado sin texto utilizable mediante
`pdftotext`. El adaptador no interpreta PDF ni incorpora fechas constantes de
esta investigación: `fecha`, `fecha_acuerdo`, `fecha_aprob`,
`fecha_publicacion` y `fase` quedan nulos. No se deduce ninguna fecha de
2015-0087, de las marcas del servidor o del día de extracción.

## Extracción, identidad y límites

Se recorre el directorio municipal, todas las categorías reconocidas, todos
sus expedientes y todas las subcarpetas documentales. El índice Apache entrega
la lista completa y no muestra paginación. Se rechazan controles de paginación,
índices vacíos, encabezados de otro directorio, enlaces fuera de ámbito,
redirecciones, categorías o identidades desconocidas y formatos inesperados.
El límite de seguridad de 250 directorios provoca error, nunca una salida
truncada. Cualquier fallo aborta la nueva instantánea y conserva la anterior.
Las actualizaciones vuelven a recorrer la instantánea completa; no usan marcas
de modificación de documentos como fechas de actividad.

La identidad estable deriva del URL oficial del expediente. Se conservan por
separado el identificador registral `46172-1000` y el expediente `2015-0087`,
tal como aparecen juntos en la carpeta oficial. Cada documento mantiene su
título, URL exacto, directorio de procedencia y editor. Se preservan las
secuencias porcentuales Latin-1 originales en los enlaces de PDF; convertirlas
a UTF-8 rompería nombres acentuados como INSCRIPCIÓN. La lectura de los índices
usa ISO-8859-1, comprobado con los bytes recibidos.

Cobertura **parcial**: inventario actualmente publicado en esa carpeta GVA,
no todos los instrumentos históricos, modificaciones, proyectos ni obras del
municipio. La presencia en este inventario no demuestra por sí sola la vigencia
legal actual de cada determinación. Los PDF se enlazan; no se extrae su contenido
en producción. Los planos PDF no son geometría vectorial verificada: `lat`,
`lon` y `geometry` quedan nulos y `publication_ready` es falso. No se sustituyen
por un centroide municipal ni por coordenadas aleatorias.

`licencias.enabled=false`: no se ha verificado un inventario público de
licencias concedidas. `schedule.enabled=false` y
`geocode.jitter_missing=false`. El manifest usa `proyectos.source=ayuntamiento`
para el contrato de carga existente, mientras que las filas declaran
`source=generalitat-valenciana`, su procedencia real.

## Validación reproducible y evidencia local

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_montserrat -v`: **8 pruebas correctas**. Verifican
  agrupación y enlaces, recorrido de varios instrumentos, semántica de fechas,
  rechazo de login/otro municipio, paginación y enlaces ajenos, carpetas vacías,
  conservación de la salida ante fallos, manifest y licencias desactivadas.
- Extracción real mediante `load_manifest('montserrat')`,
  `load_portal_adapter(manifest)` y `backfill_proyectos(...)`: **1 registro,
  57 documentos, 9 directorios HTTP**, clasificación compartida sin registros
  desconocidos. No se ha ejecutado ningún paso de publicación.
- `evidence/proyectos.jsonl`: fila real con los 57 enlaces documentales.
- `evidence/validation.json`: recuento `live_records`, URLs consultadas,
  limitaciones, runtime/pruebas y resultado del adaptador.
- `evidence/live-captures/`: respuestas originales de todos los índices y
  archivos `.url` que identifican cada captura.
- `evidence/BOP.pdf`, `BOP.txt`, `ACUERDO.pdf`, `ACUERDO.txt` y las capturas de
  descubrimiento documentan la investigación adicional. La evidencia es local,
  no forma parte de los cuatro archivos fuente entregados.

No se han utilizado credenciales, otros espacios de trabajo, bases de datos,
GitHub ni herramientas de producción o despliegue. Sin dependencias nuevas ni
cambios en código compartido.
