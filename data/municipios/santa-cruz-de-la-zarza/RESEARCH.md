# Santa Cruz de la Zarza — Toledo — INE 45156

Verificación: 2026-11-09. Adaptador de inventario documental municipal con
cobertura parcial. Extracción real: **4 instrumentos y 32 enlaces documentales**.
No acredita vigencia consolidada, obras ejecutadas ni licencias concedidas.
`publication_ready=false`; programación, licencias y jitter desactivados.

## Fuentes oficiales descubiertas

- Inventario del POM, HTTP 200:
  https://www.santacruzdelazarza.es/areas-y-servicios/urbanismo/plan-de-ordenaci%C3%B3n-municipal
  Artículo municipal con tabla estática completa de 32 documentos. No presenta
  paginación. El adaptador procesa todas las filas; falla ante paginación,
  filas incompletas, formatos o instrumentos desconocidos. Actualizar vuelve a
  extraer la instantánea completa; no usa una fecha incremental que pierda anexos.
- Ordenanzas del POM, HTTP 200:
  https://santacruzdelazarza.es/areas-y-servicios/urbanismo/ordenanzas-del-p-o-m
  Ordenanzas y unidades de actuación del mismo planeamiento. Fuente descubierta,
  fuera del alcance de esta extracción: no crea once proyectos por once ordenanzas.
  Captura local `evidence/source-2.html`.
- Información de licencias, HTTP 200:
  https://santacruzdelazarza.es/areas-y-servicios/urbanismo/informaci%C3%B3n-licencias-de-obra
  Clasificación, requisitos y solicitudes de licencias. No contiene concesiones
  identificadas. Se excluye y se mantiene `licencias.enabled=false`.
- Anuncio de información pública de la modificación puntual nº 4, HTTP 200:
  https://www.santacruzdelazarza.es/ayuntamiento/tabl%C3%B3n-de-anuncios/2636-informaci%C3%B3n-p%C3%BAblica-urbanismo
  Evidencia de otro instrumento en tramitación, con enlace al documento/sede.
  No se incorpora en el adaptador de la tabla del POM ni se afirma una cobertura
  de todo el tablón. El texto indica que se persigue la aprobación definitiva,
  no que ya se haya concedido. Es una limitación concreta de cobertura.

## Agrupación y procedencia

La tabla municipal tiene errores de rotulación importantes. Por ello se leen los
cinco PDF cuyas etiquetas no corresponden al POM base mediante el `pdftotext`
preinstalado, sin instalar dependencias. Se conservan el título original de cada
fila (`titulo_fuente`), URL absoluta, inventario y extracto de identificación del
contenido de esos PDF. La clasificación usa su contenido, no el nombre de fichero
ni la etiqueta municipal incorrecta. Los 27 documentos base quedan agrupados en
un único POM; sus mapas de saneamiento, agua o pavimentación no se convierten en
obras independientes. El nombre de los registros y sus identificadores locales
representan instrumentos, no números de expediente inventados.

| Instrumento | Documentos | Fechas y significado |
| --- | ---: | --- |
| POM | 27 | Aprobación definitiva 2002-03-27 según frase explícita del artículo; publicación desconocida. |
| Modificación puntual nº 2 | 1 | BOP nº 118: publicación 2011-05-25; sesión de aprobación definitiva 2011-03-31, según el propio PDF. |
| Modificación puntual nº 3 | 1 | Resolución ambiental 2012-02-16, publicada en DOCM nº 43 el 2012-02-28; no equivale a aprobación urbanística. |
| PERI-3 | 3 | Memoria, normas y planos. Sin fecha ni fase de aprobación acreditadas; “ABRIL 2014” en la memoria no se trata como aprobación. |

Los PDF de la resolución ambiental y del PERI-3 están rotulados en la web como
“aprobación definitiva de la modificación puntual nº2”. El PDF de resolución,
`1425555309_29resolucion_peri_n3_del_pom.pdf`, realmente se refiere a la
**modificación puntual nº 3**, expte. ambiental PLA-TO-11-0101, no al PERI-3 ni a
la MP2. Mantenerlos separados evita inventar una aprobación definitiva del PERI.
No se hereda una fecha del POM a sus modificaciones. El día/mes sin año del
artículo no se completa por suposición: las fechas completas proceden del PDF.

No se han extraído coordenadas ni geometría verificable de estos documentos.
`lat`, `lon` y `geometry` son nulos. No se usa centroide municipal ni jitter.
La disponibilidad actual de documentación antigua no garantiza su vigencia.
No se cubre todo el archivo histórico, sede electrónica, tablón ni contratación.

## Validación reproducible y evidencia local

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_santa_cruz_de_la_zarza -v`: 6 pruebas correctas.
  Verifican agrupación y corrección de etiquetas, semántica de fechas, ausencia
  de geometría, rechazo de PDF desconocidos, paginación y enlaces externos,
  licencias desactivadas y conservación del resultado anterior si falla la red.
- Llamada real a `SantaCruzDeLaZarzaAyuntamientoAdapter.backfill_proyectos`,
  con `config={'capture_dir': 'evidence'}` y destino
  `Path('evidence/proyectos.jsonl')`: 4 registros, 32 enlaces.
- `evidence/validation.json`: recuento vivo, URLs, fecha de extracción,
  limitaciones y resultado de pruebas. `evidence/plan-inventory.html`, cinco PDF,
  textos extraídos y capturas adicionales permiten inspeccionar la procedencia.
  Son evidencia local, no archivos fuente para incorporar al repositorio.

El portal devolvió inicialmente HTTP 403 con el agente predeterminado de requests
y cerró una conexión con un agente personalizado. Con `User-Agent: Mozilla/5.0`
respondió HTTP 200 en la ejecución real del adaptador; no se eluden sesiones ni
se usan credenciales. Un fallo HTTP/PDF se propaga sin escribir una salida parcial.
Se requiere que el ejecutable existente `pdftotext` siga disponible en el entorno.
