# Malpica de Bergantiños — INE 15043, A Coruña

Verificado el 2026-11-09 con el runtime preinstalado
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento y fuente elegida

- Web municipal oficial, HTTP 200: https://www.concellomalpica.com/gl/
  Enlaza la sede y su portal de transparencia. Sus noticias y formularios no se
  convierten en proyectos ni en licencias concedidas.
- Portal de transparencia, HTTP 200:
  https://sede.malpicadebergantinos.es/sxc/gl/portal_transparencia/
  Tiene un apartado de documentos sometidos a información pública. No se incorpora
  ese apartado ni se pretende cobertura completa de los expedientes municipales.
- Inventario oficial autonómico descubierto desde Urbanismo SIOTUGA:
  https://siotuga.xunta.gal/siotuga/urb?lang=es_ES
  Su fila INE 15043 identifica Malpica de Bergantiños y enlaza
  https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=15043
  Esta es la fuente del adaptador: instrumentos urbanísticos municipales publicados
  por la Xunta, no una selección de noticias individuales.

La página carga los datos mediante `assets/inventario/controls.min.js`. Se revisó
ese código público y se reproducen sus peticiones de consulta: POST a
`assets/inventario/query_document.php` con `id=15043` y las cuatro clases
14 (general), 13 (desarrollo), 16 (histórico), 18 (núcleos rurales).
Cada respuesta es un array completo; `null` representa categoría vacía. DataTables
pagina en el cliente, sin offset ni límite del servidor en estas consultas. El
adaptador procesa todos los elementos, sin cortar a diez filas. Un sobre paginado
o respuesta inesperada falla, sin sustituir el fichero anterior.

Las fichas se consultan por POST a `assets/inventario/getIOTPU.php`, `iddoc=<id>`,
`idp=0`, `lang=es_ES`. El formulario entrega un nonce público anónimo; no se usan
credenciales ni sesiones autenticadas. Las capturas del adaptador lo redactan.
Se comprueban municipio, ID, título, figura y fechas entre inventario y ficha.
La procedencia y los parámetros sin nonce quedan en cada registro. El campo
`proyectos.source=ayuntamiento` del manifiesto sigue la convención del contrato;
la procedencia efectiva de los registros es `source=siotuga`.

## Resultado y semántica

Extracción real mediante `load_manifest` y `load_portal_adapter`: **9 instrumentos**,
183 componentes documentales, 182 URLs distintas. Un archivo histórico aparece en
dos componentes con IDs y rótulos distintos: se retienen ambos sin crear otro
instrumento. Los documentos PDF/JPG, memorias, normativa y planos se agrupan por
el ID oficial de la ficha. Cinco fichas devuelven `elementos=null`: se conserva el
instrumento catalogado, con lista vacía y ausencia de digitalización explícita.

| ID SIOTUGA | Instrumento | Aprobación catalogada |
| --- | --- | --- |
| 22367 | Normas subsidiarias de planeamento | 1995-02-23 |
| 22368 | Modificación NSP na zona da Atalaia | 2003-01-17 |
| 25506 | Modificación NSP para centro de saúde | 2005-02-23 |
| 26066 | Modificación NSP: tanatorios e servizos funerarios | 2007-02-15 |
| 23599 | Estudio de detalle: Fonte do Fraile | 2000-10-20 |
| 23600 | Estudio de detalle: proposta de aliñacións | 1997-08-11 |
| 23601 | Estudio de detalle: UA-1 | 2003-02-21 |
| 23602 | Estudio de detalle: UA-8 | 1997-04-30 |
| 26391 | Normas subsidiarias históricas | 1984-12-13 |

`fecha_aprob` reproduce `fechaaddef` (aprobación definitiva según catálogo).
Las fechas de publicación BOP, DOG y normativa BOP, así como la del texto refundido,
se conservan separadamente. `fecha`, `fecha_acuerdo` y `fecha_publicacion` genérica
quedan nulas: no se confunde una fecha de publicación con la del acuerdo.
No se infiere vigencia actual ni se etiqueta una modificación como obra ejecutada.
La ficha 26391 está marcada `historico=true`.

Hay discrepancias originales que no se corrigen por inferencia: en 22367 el campo
de publicación de normativa BOP dice 1995-05-30, mientras varios rótulos documentales
dicen 30/06/1995. Ambos valores se retienen en sus respectivos campos y rótulos.

## Límites de cobertura y geometría

Cobertura parcial del inventario, no del conjunto del urbanismo local. Se comprobó
el anuncio oficial de la modificación puntual nº 4:
https://www.xunta.gal/dog/Publicados/2025/20250721/AnuncioL143-150725-0001_es.html
El DOG de 2025-07-21 acredita aprobación inicial el 2025-05-29 y remite al portal
municipal. Ese instrumento en tramitación no aparece en los arrays consultados y
no se incorpora como si perteneciera al inventario. Tampoco se equipara al antiguo
instrumento de centro de salud 25506. No se deduce ninguna concesión de licencia
del anuncio; contiene una suspensión de otorgamiento en el ámbito afectado.

No se extraen las categorías de ordenación territorial supramunicipal que también
ofrece SIOTUGA, ni se presume cobertura de obras físicas, contratos o licencias.
Las actualizaciones refrescan todo el catálogo, también documentos añadidos a
instrumentos antiguos, sin cursor de fecha de aprobación.

geometry_status: unavailable

SIOTUGA ofrece visor y enlace WMS en su índice municipal. Las fichas consultadas
enlazan planos raster y PDFs; no se ha verificado geometría vectorial atribuible a
cada ID. No se digitalizan planos ni se asigna el centro municipal. Coordenadas y
geometría nulas, `publication_ready=false`, jitter y programación deshabilitados.

## Validación reproducible y evidencia local

`python -m unittest municipio.test_malpica_de_bergantinos -v`: **7 pruebas pasan**.
Cubren agrupación documental, fechas, historial, ausencia de documentos, arrays
completos de más de diez elementos, duplicados, rechazo de otro municipio, errores
de procedencia y conservación del fichero anterior ante fallo. Las licencias
deshabilitadas escriben cero registros sin consultar la red.

Extracción live ejecutada con el adaptador resuelto por el manifiesto y
`portal.config.evidence_dir` inyectado localmente. Resultado en
`evidence/proyectos.jsonl`, informe en `evidence/validation.json`; arrays y fichas
en `evidence/live-*.json`, página pública redactada en `evidence/live-inventario.html`.
Se descargó una memoria de 22367 (`0207me001.pdf`): HTTP 200,
`application/pdf`, 1.673.998 bytes y cabecera PDF. Los demás enlaces se conservan
del catálogo; no se afirma haber descargado/verificado individualmente los 182.

La anotación compartida de entidades deja los nueve instrumentos como `unknown`;
no se fuerza una clasificación ni se inventa un número de expediente municipal
a partir del ID de catálogo. Quedan pendientes de evaluación independiente.
La evidencia es local y no forma parte de los cuatro ficheros fuente solicitados.
