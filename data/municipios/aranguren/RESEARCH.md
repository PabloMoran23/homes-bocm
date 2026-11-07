# Aranguren — INE 31023, Navarra

Verificación: 2026-11-07. Adaptador limitado al **Plan General Municipal de
Aranguren**, un instrumento real publicado por el Ayuntamiento del Valle de
Aranguren. No se confunde con el barrio de Aranguren de Zalla (Bizkaia).

## Descubrimiento y cobertura

La página oficial de [Urbanismo](https://www.aranguren.es/servicios/urbanismo/)
contiene tres ámbitos diferentes: actuaciones municipales, el PGM y noticias.
El extractor lee exclusivamente el bloque `main #planmunicipal`, descubre sus
enlaces y contrasta el instrumento con el anuncio BON enlazado. No convierte
noticias, licitaciones, comunidades energéticas ni formularios en proyectos o
licencias. Las dos actuaciones destacadas de vivienda P17C y Espacio Joven quedan
fuera del alcance de este adaptador de planeamiento.

El inventario municipal de
[planes y convenios](https://www.aranguren.es/general/transparencia/urbanismo-obras-publicas-y-medioambiente/planes-de-ordenacion-urbana-y-convenios-urbanisticos/)
remite al [SIUN de Navarra](https://administracionelectronica.navarra.es/SIUN_Consulta/Index.html#/instrumentos),
con búsqueda manual de Aranguren. Es una aplicación Angular; el HTML inicial no
enumera instrumentos. Urbanismo remite además la documentación aprobada desde el
PGM al punto 10 del [nuevo portal de transparencia](https://transparencia.animsa.es/P3102300E).
Su respuesta HTTP 200 es una estructura Blazor Server sin registros prerenderizados.
No se ha implementado el protocolo interactivo de esos portales ni se afirma que
carezcan de datos. **La cobertura es parcial: no incluye modificaciones posteriores,
planes parciales, convenios ni todos los instrumentos del registro autonómico.**

El bloque del PGM es estático, de un solo instrumento y sin paginación. Se leen
todos sus enlaces y se deduplican por URL; anuncio y PDF permanecen agrupados bajo
`aranguren-proy-pgm`. Si aparece paginación en ese bloque, falta el anuncio, hay
varios anuncios distintos, faltan los documentos o cambia la identidad/fecha, se
produce un error explícito. El enlace a más noticias pertenece a otro ámbito y no
se utiliza ni se presenta como un histórico completo.

## Procedencia y fechas

El [BON 223, anuncio 13](https://bon.navarra.es/es/anuncio/-/texto/2022/223/13)
corrobora la aprobación definitiva por Orden Foral **61E/2022 de 26 de abril**:
`fecha_aprob=2022-04-26`. El anuncio leído publica la normativa y catálogo del PGM
el **11 de noviembre de 2022**: `fecha_publicacion=2022-11-11`.
La narración cita además un anuncio previo de aprobación en el BON 198 de
5 de octubre de 2022 y una firma en Mutilva de esa misma fecha. Esas menciones
no sustituyen la fecha de publicación de la normativa ni la de aprobación.
El campo genérico `fecha` queda nulo y cada fecha explícita conserva su procedencia.

El Ayuntamiento y el BON enlazan el mismo
[PDF de normativa y catálogo](https://www.navarra.es/appsext/DescargarFichero/default.aspx?CodigoCompleto=Portal@@@epub/BON/L2213506_ARANGUREN_PGM.pdf).
Se conserva la URL oficial original; no se presenta el PDF como todos los planos
del PGM. El enlace redirige a una página HTML de descarga que ejecuta
`window.location.replace('DownloadFile.aspx' + query)`; ese paso se ha comprobado
por separado en la evidencia. El parser no deduce acuerdos ni fechas del nombre
del fichero, ni fragmenta documentos como instrumentos adicionales.

## Geometría y licencias

`geometry_status: unavailable`. La fuente extraída ofrece normativa y catálogo,
no una geometría vectorial asociada al instrumento. SIUN dispone de una consulta
urbanística, pero aquí no se ha verificado ninguna capa, identificador geométrico
ni CRS que permita vincular una geometría al registro. No se vectorizan PDFs,
no se inventan coordenadas y `publication_ready` queda falso.

No se ha verificado un inventario público de licencias concedidas. Los impresos
municipales de solicitud no acreditan concesiones. Ambos métodos de licencias
escriben vacío con estado `disabled`. `licencias.enabled=false`,
`schedule.enabled=false` y `geocode.jitter_missing=false`.

## Validación reproducible

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -B -m unittest municipio.test_aranguren -v`: **5 pruebas pasan**.
Cubren agrupación de documentos, fechas distintas, fuentes ausentes o ajenas,
contradicciones con BON, paginación inesperada y actualización de instantáneas,
además de licencias deshabilitadas sin red.

Extracción real mediante `load_manifest('aranguren')`,
`load_portal_adapter(manifest).backfill_proyectos(...)`: **1 registro**.
La política compartida lo marca `pendiente/insufficient_identity_evidence` por no
tener un número de expediente municipal; se conserva esa anotación sin inventar
una referencia ni alterar las reglas compartidas. No está listo para publicación.

Evidencias locales en `evidence/`: `proyectos.jsonl`, `validation.json`, capturas
HTML comprimidas y metadatos HTTP/SHA-256. No forman parte de los cuatro archivos
fuente entregados. No hay cambios compartidos, dependencias nuevas ni publicación.
