# Borja (Zaragoza), INE 50055

Investigación y extracción en vivo: **9 de noviembre de 2026**. Se revisaron
`municipio/manifest.py`, `municipio/adapters/portal.py`, el registro dinámico de
adaptadores y los ejemplos de Manlleu y Chipiona antes de implementar.

## Inventarios oficiales consultados

- Mapa del portal municipal de transparencia:
  https://www.cumpletransparencia.es/borja/MapaWeb
  Identifica al Ayuntamiento de Borja y enlaza las secciones siguientes.
- Planeamiento, fuente efectiva del adaptador:
  https://www.cumpletransparencia.es/borja/Ordenacion/planes-de-ordenacion-urbana-y-publicacion-del-plan-general-d
  HTTP 200. Contenido HTML completo en una página, sin paginación observada.
  El PGOU se remite mediante instrucciones de búsqueda al archivo del Gobierno
  de Aragón (`idearagon.aragon.es/SIUa/`, municipio Borja, procedimiento de
  adaptación a PGOU). Esa referencia no se convierte en un expediente sintético
  ni se considera cubierto el archivo autonómico.
- Convenios:
  https://www.cumpletransparencia.es/borja/Ordenacion/planes-de-ordenacion-urbana-y-convenios-urbanisticos-del-ayu
  HTTP 200. Ofrece un PDF denominado genéricamente «Convenios urbanísticos»;
  no se transforma ese enlace en un proyecto sin identificar su actuación.
- Obras:
  https://www.cumpletransparencia.es/borja/Ordenacion/informacion-obras-publicas-proyectos-pliegos-y-criterios
  HTTP 200. La sección «Pliegos» enumera fotovoltaica municipal,
  Casa-Palacio de los Frances y climatización de la Casa de la Música, con
  documentos de contratación de 2023/2024 y un enlace a años anteriores.
  No se extraen esos anuncios/pliegos como proyectos ni como obras adjudicadas.
  El enlace histórico no se recorre; esta sección completa queda fuera de la
  cobertura, no se declara agotado su histórico.

`https://borja.es` y `https://www.borja.es` fallaron la verificación TLS por
discordancia del nombre del certificado. No se desactivó la verificación. El
portal de transparencia y sus PDF respondieron mediante HTTPS verificado.
El subdominio `borja.cumpletransparencia.es/MapaWeb` devuelve una página
`Error/NotEntity`; el inventario correcto es la ruta `/borja/` del host `www`.

## Registro extraído y documentos

**Un registro real: Plan Integral del Casco Histórico de Borja (PICH)**. Su
encabezado se lee del HTML; no es una fila precargada. La lista inmediatamente
asociada contiene tres documentos, conservados juntos en `documentos`:

1. [Memoria](https://borja.cumpletransparencia.es/Entidades/borja/Ordenacion/PLANES%20DE%20ORDENACION%20URBANA%20Y/Publicaci%C3%B3n%20del%20Plan%20General%20d/MEMORIA%20APROBADO_plan_casco_historico.pdf).
2. [Planos, parte 1](https://borja.cumpletransparencia.es/Entidades/borja/Ordenacion/PLANES%20DE%20ORDENACION%20URBANA%20Y/Publicaci%C3%B3n%20del%20Plan%20General%20d/PLANOS_plan_casco_historico_Parte1.pdf).
3. [Planos, parte 2](https://borja.cumpletransparencia.es/Entidades/borja/Ordenacion/PLANES%20DE%20ORDENACION%20URBANA%20Y/Publicaci%C3%B3n%20del%20Plan%20General%20d/PLANOS_plan_casco_historico_Parte2.pdf).

Todos respondieron HTTP 200 y firma `%PDF-`; se descargaron completos (1.690.216,
3.322.835 y 9.343.050 bytes). El adaptador calcula SHA-256 y conserva el enlace
HTTP original junto a su versión HTTPS verificada y la página de procedencia.
No depende del encabezado Content-Type, ausente en esas respuestas.

Se leyó la memoria con `pdftotext -layout` (captura local `evidence/plan-0.txt`).
Su apartado 1.1 identifica al Ayuntamiento de Borja como promotor y su apartado
1.3 describe el PICH como documento de intenciones para definir actuaciones en
el casco histórico. Se registra como **plan integral**, sin afirmar que sea un
plan especial estatutario, licencia concedida, proyecto constructivo aprobado
ni obra en ejecución. No se convierten sus propuestas internas en obras
independientes. Las fechas históricas del BIC y del PGOU mencionadas en los
antecedentes no se atribuyen al PICH.

## Semántica y límites

La página muestra «Última actualización el jueves, 13 de junio de 2024 a 16:27».
Se conserva exclusivamente en `fuente_actualizacion_texto`: no acredita fecha
de publicación del instrumento, acuerdo ni aprobación. `fecha`,
`fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` y `fase` son nulos. El nombre
`MEMORIA APROBADO` tampoco basta para atribuir una fase administrativa.

Cobertura parcial, limitada a planes nombrados con documentos directamente
agrupados en la página de planeamiento. No cubre todas las modificaciones del
PGOU, el archivo SIUa, convenios, contratación, noticias ni concesiones de
licencias. Sin coordenadas o geometrías verificadas: `lat`, `lon`, `geometry`
nulos y `publication_ready=false`. Manifest con `licencias.enabled=false`,
`schedule.enabled=false` y `geocode.jitter_missing=false`.

El parser exige identidad municipal, sección de planeamiento y documentos
agrupados; falla ante inventario vacío, documentos sin grupo o de otra entidad,
encabezados duplicados y paginación detectada. No aplica límites de filas ni
cortes temporales. Si el portal introduce páginas adicionales habrá que adaptar
el recorrido; el código actual las rechaza explícitamente. El refresco es una
instantánea completa y no altera el fichero de estado. Las respuestas tienen
límites de tamaño explícitos que causan error, nunca truncamiento de registros.

## Validación reproducible

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_borja -v`
— **10 pruebas correctas**: agrupación, separación entre instrumentos,
procedencia, fechas y geometrías ausentes, exclusión de formularios, rechazo de
cambios/paginación/documentos ajenos, estabilidad del identificador, refresco y
validación del PDF antes de escribir, manifest y licencias desactivadas.

Extracción real mediante `BorjaAyuntamientoAdapter`, configurado con
`capture_dir=evidence/live`, ejecutando
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **1 registro, 3 PDF**.
`evidence/validation.json` contiene `live_records`, `source_urls`, limitaciones,
runtime, resultado y huellas de los documentos. `evidence/live/inventory.html`
y los PDF nombrados por SHA-256 son las capturas de esa ejecución; las otras
capturas HTML documentan la exploración. Evidencias locales, fuera de los cuatro
archivos fuente. No hubo publicación, geocodificación, acceso a bases de datos,
instalación ni cambios de dependencias o código compartido.
