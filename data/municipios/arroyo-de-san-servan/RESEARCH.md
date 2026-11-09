# Arroyo de San Serván — INE 06012, Badajoz, Extremadura

Comprobación: 2026-11-09. Adaptador único de instrumentos municipales vigentes,
con fuente efectiva en el registro público regional SITEX de la Junta de Extremadura.

## Descubrimiento y fuentes

- Web oficial: https://arroyodesanservan.org/ . La navegación ofrece documentos,
  plenos, perfil del contratante y trámites. No se interpreta contratación como obra
  ejecutada ni formulario como licencia concedida.
- https://arroyodesanservan.org/ayuntamiento/documentos-on-line/ muestra en la
  consulta web solicitudes y comunicaciones previas. El acceso directo con requests
  recibió HTTP 403. No se usa como inventario de concesiones.
- Consulta oficial de planeamiento: https://sitex.juntaex.es/SITEX/planeamiento .
  El selector identifica Arroyo de San Serván con ID interno **13**, distinto del INE.
  El JavaScript público usa `municipioseleccionado` y el endpoint
  https://sitex.juntaex.es/SITEX/ptofiguras/listadoresultadossigcat .
  El adaptador reproduce esa búsqueda de solo lectura mediante POST con valor 13;
  GET no aplica ese filtro. La opción vacía permanece seleccionada en el HTML de
  respuesta; la identidad se verifica por opción ID/nombre, árbol y ámbito de ficha.
- Registro de contraste: https://sitex.juntaex.es/SITEX/ptofiguras/ripu .
  Incluye ocho filas del municipio, siete no vigentes y el PGM vigente. El extractor
  usa el árbol municipal, no esas ocho filas como supuesto histórico exhaustivo.

## Cobertura y agrupación

La búsqueda descubre dinámicamente los enlaces `viewsigcat` del árbol; se incluyen
los instrumentos **Vigente** cuyo rótulo empieza por el nombre exacto municipal.
No se fija una noticia o un ID de instrumento como semilla. Se excluyen instrumentos
no vigentes y el Plan Territorial de Mérida y municipios de su entorno en trámite.
El árbol revisado no tiene paginación: su expansión es local. Ante controles de
paginación el extractor falla explícitamente, sin aceptar una primera página parcial.
Un resultado vacío, ficha incoherente o ausencia de documentos también causa error,
y se conserva la salida anterior si falla la extracción.

Resultado vivo: **1 instrumento**, Plan General Municipal, SITEX **38878**, referencia
PGM, depósito **BA/058/2017**. Ficha:
https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/38878 .

- Aprobación definitiva: **2017-07-13** (`Fecha AD`).
- Publicación de aprobación definitiva en DOE: **2017-12-14**.
- Depósito: **2017-11-15**. La publicación en sede de **2018-01-12** se conserva como
  trámite, no reemplaza la publicación DOE ni la aprobación. `fecha` genérica nula.
- **25 documentos** agrupados bajo ese instrumento: 22 descargas SITEX (planos de
  información, memorias justificativa e informativa) y tres publicaciones DOE de
  trámites. Se retienen sus URLs originales y ficha de procedencia; no se crean
  25 proyectos. Los PDFs se enlazan, sus contenidos no se analizan ni se presupone
  que constituyan toda la documentación normativa del PGM.

La fuente no constituye inventario completo de proyectos, obras o expedientes
urbanísticos. La búsqueda oficial DOE detectó anuncios adicionales del sector SUB
2.1 (UA 2.1.1), entre ellos:
https://doe.juntaex.es/otrosFormatos/html.php?anio=2026&doe=1510o&xml=2026081346
(información pública de reparcelación/urbanización) y
https://doe.juntaex.es/otrosFormatos/html.php?anio=2025&doe=2380o&xml=2025081992 .
No están incluidos en este adaptador de planeamiento municipal vigente SITEX.
El segundo presenta divergencia entre título y cuerpo; no se infiere un nuevo
instrumento ni fecha de aprobación a partir del título. Cobertura expresamente parcial.

## Geometría y licencias

`geometry_status: unavailable`. El visor enlaza cartografía de contexto municipal
(GeoJSON de municipios, CRS del visor EPSG:25829), que no acredita una geometría
específica del instrumento. No se asigna centroide, coordenadas o geometría a partir
del mapa de contexto o de planos PDF. `publication_ready: false`.
No se ha verificado registro público de licencias concedidas; métodos de licencias
vacíos y deshabilitados. `schedule.enabled: false`, `geocode.jitter_missing: false`.

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_arroyo_de_san_servan -v`: **7 pruebas**, todas pasan.
Cubren descubrimiento/deduplicación, exclusiones, cambio de municipio, errores de
fuente, paginación, fechas, agrupación de enlaces, preservación de salida y manifest.
Extracción real invocando `load_portal_adapter(load_manifest('arroyo-de-san-servan'))`
y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `capture_dir=evidence`
en la configuración de esa ejecución. Resultado: **1 registro**, 25 documentos.

Evidencia local: `evidence/proyectos.jsonl`, `evidence/validation.json`,
`evidence/sitex-inventory.html`, `evidence/sitex-38878.html`, `evidence/planeamiento.html`
y `evidence/ripu.html`. Las capturas de sondeo GET también se conservan para explicar
por qué se requiere POST. Evidencias excluidas de los cuatro archivos fuente.
