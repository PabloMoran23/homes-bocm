# Villafranca de los Barros — INE 06149, Badajoz

Verificación: 2026-11-07. Adaptador real de cobertura parcial: anuncios del
Ayuntamiento en el Diario Oficial de Extremadura (DOE), con «planeamiento» en
el título y aprobación inicial de una modificación de planeamiento. Ventana
predeterminada: desde 2026-01-01 hasta el día de extracción; `end_date` permite
repetir una ventana cerrada. No representa todo el planeamiento vigente ni todas
las obras municipales. No se extraen licencias concedidas.

## Descubrimiento de fuentes oficiales actuales

- https://www.villafrancadelosbarros.es/ — HTTP 200; aplicación Gatsby sin
  contenido visible en el HTML inicial. Sus módulos JavaScript públicos indican
  la API municipal, sin necesidad de autenticación.
- https://smart.villafrancadelosbarros.es/api/menu?slug=navbar y
  https://smart.villafrancadelosbarros.es/api/menu?slug=footer — HTTP 200;
  inventario actual de navegación. Enlaza sede, tablón, actas y ordenanzas.
- https://smart.villafrancadelosbarros.es/api/documents?slug=ordenanzas-municipales
  — HTTP 200; ordenanzas generales, fiscales y no fiscales. No es un inventario
  de proyectos ni un registro de licencias; sus documentos no generan registros.
- https://smart.villafrancadelosbarros.es/ — redirige al formulario de acceso.
  No se inició sesión ni se consultaron rutas privadas.
- https://sede.villafrancadelosbarros.es/portal/tablonVirtual.do?campo=2&ent_id=49&idioma=1&opc_id=175&pes_cod=8&subseccion=TAB_AYU
  — tablón municipal actual. La conexión inicial fallaba por cadena TLS
  incompleta. Para investigarlo se obtuvo el certificado intermedio público
  indicado en AIA, https://www.cert.fnmt.es/certs/ACSS1.crt, y se añadió a un
  contexto SSL con las raíces del sistema, manteniendo verificación de cadena y
  nombre de servidor. La respuesta HTTP 200 actual muestra dos expedientes
  ajenos al planeamiento y documentos administrativos. El buscador web conservaba
  una versión anterior con Sector 5, que ya no aparece en el listado vivo.
  No se utiliza esa versión indexada para fabricar un inventario actual.
- https://doe.juntaex.es/busquedas/bus_avanzada.php — formulario oficial que
  define la consulta por fechas, organismo y palabras del título.
- https://doe.juntaex.es/busquedas/disposiciones.php — inventario operativo del
  adaptador. POST con `fecha1=2026-01-01`, `fecha2=2026-11-07`,
  `orgabus=VILLAFRANCA DE LOS BARROS`, `textobus=planeamiento`, `yuo=0`,
  `rango=00`, `descriptor=00`, `buscardesc=nodesc`, `tipo= `.
  HTTP 200: anuncia **2 disposiciones**, con dos enlaces HTML y dos PDF.
  El organismo exacto se verifica además en cada ficha, evitando confundirlo
  con Villafranca de Navarra u otros municipios homónimos.

## Instrumentos extraídos en vivo

1. **2026/2/S871**, modificación de las NNSS sobre Ordenanza IX, zona de
   almacenaje vinculado al sector primario (Pol. Cholaica), ampliación de usos
   terciarios compatibles. Acuerdo plenario: **2026-03-26**; anuncio firmado:
   **2026-03-31**; publicación DOE: **2026-04-13**.
   - https://doe.juntaex.es/otrosFormatos/html.php?xml=2026080529&anio=2026&doe=690o
   - https://doe.juntaex.es/pdfs/doe/2026/690o/26080529.pdf
2. **2026/1/S871**, modificación del Plan Parcial del Sector 5 para recalificar
   viales como suelo industrial y compensar dotaciones públicas. Acuerdo
   plenario: **2026-07-30**; resolución de Alcaldía y anuncio: **2026-08-04**;
   publicación DOE: **2026-08-21**.
   - https://doe.juntaex.es/otrosFormatos/html.php?xml=2026081420&anio=2026&doe=1620o
   - https://doe.juntaex.es/pdfs/doe/2026/1620o/26081420.pdf

Los textos identifican instrumentos concretos y sus expedientes: no son
formularios, noticias ni anuncios de contratación. `fase` describe la aprobación
inicial comunicada por esos anuncios; no acredita su situación administrativa
posterior. `fecha_aprob` queda nula: se conservan explícitamente las fechas de
acuerdo, resolución, anuncio y publicación, sin resolver por inferencia cuál
constituye la fecha de aprobación efectiva. Las fechas de redacción técnica no
se convierten en fechas de acuerdo.

## Extracción, agrupación y límites

La consulta se realiza en cada ejecución, no contiene títulos ni registros
precargados. El parser exige estructura DOE, organismo exacto, título de
aprobación inicial de planeamiento, descripción del instrumento, expediente real,
fecha de publicación y enlace al PDF auténtico. La versión HTML es informativa;
el DOE identifica el PDF como versión oficial. Se retienen HTML, PDF y XML en
`documentos[].formatos`, junto con la descripción y fechas de cada anuncio.
Los distintos anuncios del mismo expediente se agrupan en un registro con ID
estable derivado del expediente, sin perder documentos. Los campos superiores
reflejan el anuncio más reciente dentro de la ventana consultada.

La suma de fichas únicas debe coincidir exactamente con el total anunciado por
el buscador. Si hay paginación, faltan formatos o cambia la estructura, falla
antes de escribir resultados; no se implementa recorrido automático de páginas
ni se entrega silenciosamente una primera página parcial. Una consulta vacía
también falla explícitamente. La actualización refresca toda la ventana y no
adelanta cursores, para permitir documentos indexados con retraso.

Se excluyen expresamente los acuerdos de CUOTEX publicados por la Junta, aunque
afecten a este municipio, otros títulos, fases y periodos, anexos técnicos,
actas, inventarios de obras y registros de licencias. Por ejemplo, el acuerdo
regional de 2025 sobre DOT-1/La Herrera y El Ejido, publicado en 2026, es real
pero queda fuera del filtro de organismo municipal; no se afirma cubrirlo:
https://doe.juntaex.es/otrosFormatos/html.php?anio=2026&doe=590o&xml=2026AC0019.
Las futuras disposiciones que pasen el filtro del buscador pero no el contrato
semántico del parser producirán error explícito y requerirán revisión.

No hay geometría verificada en las fichas utilizadas: `lat`, `lon` y `geometry`
son nulos, `publication_ready=false`. No se asignan centroides, parcelas ni
coordenadas inventadas. `schedule.enabled=false`, `geocode.jitter_missing=false`
y `licencias.enabled=false`. El adaptador del DOE utiliza TLS estándar; la
investigación del certificado de la sede no forma parte de la extracción.

## Validación y evidencia local

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_villafranca_de_los_barros -v`: **6 pruebas OK**.
  Fechas diferenciadas/ausentes, municipio exacto, rechazo de formularios y
  contratación, agrupación e identidad, total del inventario, esquema y licencias
  desactivadas.
- `VillafrancaDeLosBarrosAyuntamientoAdapter.backfill_proyectos` con la
  configuración del manifest y fecha final 2026-11-07: **2 registros reales**.
- Ambos PDF descargados con HTTP 200 y cabecera `%PDF`; sus tamaños y SHA-256
  constan en `evidence/validation.json`.
- `evidence/proyectos.jsonl`, `evidence/validation.json` y capturas originales
  HTML/PDF en `evidence/captures/`. Los parámetros POST están en validation;
  el HTML de resultados capturado corresponde a la petición real del adaptador.
- Evidencia exclusivamente local. No se modifican fuentes compartidas,
  dependencias ni configuración git; no se realizan operaciones de publicación.
