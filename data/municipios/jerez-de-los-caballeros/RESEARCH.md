# Jerez de los Caballeros — INE 06070, Badajoz, Extremadura

Verificación: 2026-11-08. Adaptador único, extracción pública anónima.

## Descubrimiento y fuentes oficiales

- Ayuntamiento, inventario de Urbanismo y Obras Públicas:
  https://jerezcaballeros.es/urbanismo-y-obras-publicas/
  Contiene «Descarga el PGM», «Consultar Documentos» (SITEX) y «Acceso al PEPCH».
  Enlaza el PDF https://jerezcaballeros.es/pdf/urbanismo/PGM-Jerez-Caballeros.pdf
  y formularios de obras, comunicación previa, segregación y habitabilidad.
  Los formularios y el protocolo de paneles solares se excluyen.
- SITEX, Junta de Extremadura, inventario de seguimiento del planeamiento:
  https://sitex.juntaex.es/SITEX/planeamiento
  La opción «Jerez de los Caballeros» tiene identificador interno **98**, que no
  es el código INE. El adaptador comprueba ambas denominación e identificación.
  La consulta pública que usa la interfaz es POST a
  https://sitex.juntaex.es/SITEX/ptofiguras/listadoresultadossigcat
  con `municipioseleccionado=98`, `X-Requested-With: XMLHttpRequest` y
  `X-Update: planeamientosindex`. Un GET con ese parámetro devuelve un inventario
  vacío y NO sirve para esta extracción. Es una consulta, sin modificación remota.
- Los detalles se descubren del árbol completo, por ejemplo el PGM:
  https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/37263
  y el Plan Especial:
  https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/36823
- Inventario municipal PEPCH adicional:
  https://jerezdeloscaballeros.sedelectronica.es/transparency/9d4f86e1-2c3b-431c-899a-03bea4bb9694/
  HTTP 200; muestra carpetas PLANOS (49), DOCUMENTOS (15), MODIFICACIONES
  PUNTUALES (10) y expediente 3671/2025 (7). La navegación usa Wicket AJAX;
  no se recorre en este adaptador ni se convierten carpetas en proyectos.

## Cobertura y semántica

Se extraen **33 instrumentos** del inventario SITEX: 26 vigentes y 7 en trámite.
Se incluyen el PGM, el Plan Especial y sus modificaciones identificadas por
referencia completa. Se retienen 100 enlaces documentales. Se excluyen explícitamente los no vigentes (NV) y el Plan
Territorial de Tentudía-Sierra Suroeste por su ámbito supramunicipal. El árbol
contiene las ramas expandidas en HTML aunque la interfaz las muestre colapsadas;
no hay paginación en la respuesta revisada. Se inspeccionan todos los enlaces,
sin límite arbitrario de registros. Si aparece paginación, el parser falla
explícitamente; no acepta una extracción truncada.

Un instrumento = un registro, ID estable basado en el identificador SITEX.
El campo `expediente` usa el identificador oficial con prefijo `SITEX:`;
`referencia` conserva la referencia del detalle y `referencia_inventario` la del
árbol, sin confundirlas con un número de expediente del ayuntamiento.
Se conservan todos los enlaces documentales del detalle: archivos técnicos,
publicaciones DOE/BOP y otros documentos de los trámites. Se deduplican por URL
dentro del instrumento, preservando título y procedencia. El contenido de los
PDF no se interpreta para generar registros adicionales. Los vínculos se retienen
como los publica la fuente, incluidos los HTTP históricos.

`fecha_aprob` procede exclusivamente de «Fecha AD» y `fecha_publicacion` de
«Fecha de publicación AD», con diario separado. No se copian a `fecha_acuerdo`:
los acuerdos y sus fechas específicas se conservan en `tramites` junto a su
etiqueta original. Por ejemplo el PGM distingue aprobación definitiva 2023-04-27
y publicación DOE 2023-06-15:
https://doe.juntaex.es/pdfs/doe/2023/1140o/23AC0031.pdf
Los procedimientos incluyen también recursos y resoluciones posteriores.
SITEX mantiene algunos expedientes «En trámite» con «Fecha AD» informada:
se conservan los dos campos, sin deducir vigencia ni fase a partir de esa fecha.
El expediente 38816 declara no tener trámites definidos y se conserva con lista
vacía, sin inventar fechas ni documentos. Las fechas ausentes permanecen nulas.

La cobertura es parcial: no es un censo exhaustivo de proyectos constructivos,
obras físicas ni licencias concedidas. La sede municipal ofrece documentación
adicional del PEPCH que aquí no se integra. La información SITEX tiene carácter
informativo; no sustituye a los acuerdos y publicaciones oficiales. No se usan
noticias, anuncios de contratación ni formularios como proyectos o concesiones.

## Geometría

`geometry_status: unavailable`. El mapa SITEX carga Municipios.geojson y PT.geojson
con EPSG:25829 para seleccionar ámbitos territoriales. Esas capas no son geometrías
verificadas de cada instrumento. Los planos PDF tampoco se vectorizan. No se
asignan centroides, coordenadas ni geometrías inventadas; `publication_ready: false`.

## Validación y operación

Runtime usado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas offline: `python -m unittest municipio.test_jerez_de_los_caballeros -v`.
Siete pruebas cubren filtrado de ámbitos/estado, identidad y deduplicación,
separación de fechas, documentos agrupados, fechas ausentes, inventario sin
trámites, cambios de estructura/municipio, paginación y conservación del resultado
anterior ante fallo de red, además de las restricciones del manifest.

Extracción real a través de `load_manifest` y `load_portal_adapter`, invocando
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`. Las capturas de cada
respuesta del recorrido están en `evidence/live/`; `evidence/validation.json`
recoge recuentos, URLs, método/parámetro del inventario y limitaciones.
Evidencia local no destinada al commit. No se han modificado fuentes compartidas
ni dependencias. Actualización = instantánea completa, sin watermark por fecha;
fallos de red/parser impiden reemplazar el JSONL anterior. Licencias y programación
deshabilitadas; `geocode.jitter_missing: false`. Sin publicación ni operaciones DB.
