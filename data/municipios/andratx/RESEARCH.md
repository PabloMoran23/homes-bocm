# Andratx — INE 07005, Illes Balears

Verificación: 2026-11-07. Adaptador único de inventario de planeamiento municipal.

## Fuentes oficiales y descubrimiento

- Área municipal de Urbanismo: https://andratx.es/ca/arees-municipals/urbanisme
  Describe competencias y ofrece acceso al portal de transparencia. Su navegación
  también enlaza la ficha municipal Ibestat con identificador 07005.
- Inventario: https://transparencia.andratx.es/t/planeamiento
  HTTP 200, HTML completo con paneles y tablas de documentos. Es la fuente de
  extracción, no una noticia individual ni una lista de licitaciones.
- Visor municipal: https://andratx.es/ca/visor-urbanistic
  Advierte expresamente: «La normativa urbanística publicada en aquest visor ja
  no és vigent». Enlaza SITMUN
  http://sitmun.idelma.cat/visorSitmun/visor_urb.jsp?app=7&ter=24.
  No se utiliza como prueba de vigencia ni para inventar geometrías.

## Cobertura y agrupación

Extracción real: **16 instrumentos**, **401 enlaces documentales** asociados:

- Un registro NNSS 2023 y refós, agrupando 7.1.1.A y 7.1.1.B: 201 documentos.
  Son versiones/documentación del mismo planeamiento, no 201 proyectos.
- Seis modificaciones de las NNSS 2023, sección 7.1.1.C: 1.A/2024, 1.B/2024,
  2/2024, 3/2025, 4 y 5/2026. Se unen las tablas repetidas de 1.A y 1.B.
- Un estudio de detalle de Sant Elm, parcela en Avenida Jaume I y Es Pantaleu
  (7.1.1.E).
- Ocho instrumentos de gestión/ejecución (7.2.1–7.2.8): juntas de compensación
  La Mola, Seldwyla y UA/1 SE Sant Elm; proyectos de expropiación ANS/1.A,
  ANS/3.PA, SUDO 4A y ANS/2A; estudio de detalle del vial Can Borràs.
  Los estatutos y bases de juntas se identifican como instrumentos de gestión,
  sin atribuirles ejecución de obras ni concesión de licencia.

Se recorre cada tabla de cada panel admitido. Las dos tablas bilingües de 7.2.8
se unen bajo el mismo identificador; los enlaces repetidos se deduplican por URL.
Cada documento conserva título, enlace, panel y grupo de procedencia. Los grupos
alternativos permanecen en `grupos_fuente`. Los identificadores internos se basan
en los números del inventario, no se presentan como números de expediente.

Se excluye 7.1.1.D, explícitamente «NNSS 2007 (Derogades)», incluidas sus
modificaciones históricas. Sí se conservan planos de 2007 incorporados como
información contextual dentro de la documentación de NNSS 2023. No se ha extraído
un histórico completo municipal, licencias concedidas, contratación ni noticias.
No se ha verificado un registro público reutilizable de licencias concedidas.

## Fechas, procedencia y geometría

No se transforma el texto `Fecha : ...` en fecha de publicación ni de acuerdo:
la página no define su significado. Se conserva literalmente por documento en
`fecha_fuente_texto`. Las fechas de los títulos también quedan en su contexto.
En particular, varias modificaciones posteriores citan el BOIB 62 de mayo de
2023 de las NNSS originales; esa fecha no se atribuye a la modificación.
`fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` y `fase` quedan null.
La fase jurídica puede ser distinta entre documentos de un mismo instrumento.

Los PDF no se analizan automáticamente. Se comprobaron manualmente mediante
descarga HTTP 200 y primera página las memorias de SUDO 4A, estudio de detalle de
Sant Elm y MP4; son documentos de los instrumentos indicados, no formularios.
Las fechas de acuerdos contenidas en PDF no se propagan desde esta comprobación
puntual al parser. Los títulos del inventario no constituyen una comprobación
independiente de vigencia jurídica, aprobación final ni ejecución física.

`geometry_status: unavailable`. Sin coordenadas, geometrías ni CRS verificados
por instrumento; lat/lon/geometry son null, `publication_ready` es false.
Las imágenes y planos PDF se retienen como documentos, no como vectores.

## Paginación, fallos y actualización

La respuesta revisada contiene todos los paneles en el HTML, sin paginación ni
carga adicional. El adaptador no usa límites de filas ni cortes de documentos.
Si aparece paginación o continuación reconocible, falla para exigir implementar
el recorrido. Cambios de sección, tablas sin documentos, enlaces fuera del
almacenamiento oficial y pérdida de paneles provocan error. Se valida la etiqueta
de derogación antes de excluir el panel histórico. Se requiere revisión si cambia
el formato; no se pretende descubrir secciones de formatos arbitrarios.

La actualización vuelve a leer el inventario completo. No registra bajas ni
mantiene versiones históricas. Escritura atómica después de validar el contenido.
Licencias deshabilitadas: los métodos generan salida vacía con estado disabled.
`schedule.enabled=false`, `geocode.jitter_missing=false`.

## Validación reproducible y límites de integración

Runtime usado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_andratx -v` — seis pruebas correctas:
agrupación bilingüe y versiones, exclusión histórica, fechas y coordenadas
ausentes, URLs codificadas, rechazo de paginación/cambios y conservación de salida
previa ante error; carga del manifest mediante registry y licencias vacías.

Extracción real realizada mediante
`load_portal_adapter(load_manifest('andratx')).backfill_proyectos(...)`, con
`config['capture_dir']='evidence'`. Evidencias locales: `evidence/proyectos.jsonl`,
`evidence/validation.json`, tres capturas HTML, tres PDF y sus primeras páginas
en texto. La validación incluye recuento, fuentes, limitaciones, política de
entidades y hashes de los PDF comprobados. No se verificaron individualmente los
401 enlaces documentales.

La política compartida de entidades clasifica los 16 registros como `pendiente`
(`unknown_entity_spike` / `adapter_incident`): estos instrumentos agrupados no
aportan un número administrativo de expediente extraído. No se han inventado
referencias para evitar ese resultado ni modificado la política compartida.
Los registros y documentos son reales; su clasificación y cualquier publicación
requieren revisión independiente. No se ejecutaron publicación, DB ni pipeline
global. Las evidencias quedan locales y no forman parte de las fuentes a entregar.
