# Markina-Xemein — Bizkaia — INE 48060

Verificación y extracción HTTP real: 2026-11-09. Python utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento y fuente elegida

Se revisaron primero `municipio/manifest.py`, `municipio/adapters/portal.py`,
el registro de adaptadores y los ejemplos Hernani, Manlleu y Chipiona.
El manifest identifica municipio, provincia y comunidad autónoma, con proyectos
habilitados, licencias y programación deshabilitadas y sin jitter geográfico.

La portada municipal redirige a la versión en euskera y ofrece poca navegación
textual. La ruta pública en castellano permite descubrir los enlaces en imágenes
mediante sus atributos `alt`:

- [Servicios municipales](https://www.markina-xemein.eus/es-ES/Servicios/Serviciosmunicipales/Paginas/default.aspx)
- [Inventario de Urbanismo](https://www.markina-xemein.eus/es-ES/Servicios/Serviciosmunicipales/Urbanismo/Paginas/default.aspx)

El adaptador parte de este último inventario, descubre sus enlaces de PGOU,
modificación del PGOU y Arretxinaga, y sigue sus páginas documentales. No utiliza
noticias individuales como semillas ni transforma formularios en licencias.

## Resultado y agrupación documental

La extracción real produjo **6 registros**, con **114 URLs PDF distintas** entre
documentos propios y de contexto, a partir de **17 páginas HTML**:

| Instrumento | Documentos propios | Cobertura |
| --- | ---: | --- |
| [PGOU](https://www.markina-xemein.eus/es-ES/Servicios/Serviciosmunicipales/Urbanismo/Paginas/plan-general-ordenacion-urbana.aspx) | 47 | Memoria, ordenanzas, sostenibilidad y viabilidad económica, más 43 planos |
| [Modificación Etxetic](https://www.markina-xemein.eus/es-ES/Servicios/Serviciosmunicipales/Urbanismo/Paginas/modificacion-puntual-pgou-equipamiento-social-etxetic.aspx) | 60 | 29 documentos en la sección inicial y 31 en la provisional |
| Estudio de detalle de Arretxinaga | 2 | Texto y planos adyacentes en el listado |
| Programa de Actuación Urbanizadora de Arretxinaga | 2 | Texto y planos identificados expresamente |
| Proyecto de reparcelación de Arretxinaga | 1 | Proyecto PDF |
| Proyecto de urbanización de Arretxinaga | 1 | Proyecto PDF |

Los cuatro últimos se descubren en la misma [página del ámbito RX–V-a.40](https://www.markina-xemein.eus/es-ES/Servicios/Serviciosmunicipales/Urbanismo/Paginas/area-rx-v-a-40-arretxinaga.aspx).
El convenio de concertación de ese ámbito se conserva como documento de contexto
común; no genera un quinto proyecto. Los títulos de estos cuatro registros
normalizan los rótulos documentales y añaden el ámbito, sin deducir obras ejecutadas.
Cada PDF conserva título, URL y página de procedencia. Etxetic conserva además la
sección documental y un resumen de las tres secciones descubiertas.

## Paginación, fechas y alcance

Se recorren todos los enlaces de paginación descubiertos, incluidos los que
aparecen al avanzar: PGOU páginas 1–9 y Etxetic provisional páginas 1–3.
Las cuatro piezas generales del PGOU se repiten en cada página y se deduplican.
Se comprueban los rangos y totales anunciados por cada listado: 43 planos y
31 documentos provisionales. Se rechazan páginas repetidas por el servidor,
totales cambiantes, documentos faltantes, nuevos formatos de paginación o el
límite de seguridad de 100 páginas, sin sobrescribir el resultado anterior.
Si las páginas de entrada adquieren paginación, el adaptador falla expresamente.

La sección municipal «Aprobación definitiva» de Etxetic devuelve una tabla vacía.
Su enlace **no acredita un acuerdo de aprobación definitiva**. Los rótulos de
sección describen documentación, sin poblar `fase`, `fecha_acuerdo` ni
`fecha_aprob`. Los HTML examinados no exponen fechas de publicación verificables;
`fecha_publicacion` también queda en null. No se usan fechas de ficheros,
cabeceras HTTP, extracción o consulta como fechas administrativas.

Cobertura parcial: inventario documental municipal seleccionado, sin asegurar
vigencia jurídica, exhaustividad histórica, aprobación o ejecución de cada obra.
Se conservan los enlaces a PDF sin analizar su contenido. Se verificó mediante
GET y cabecera `%PDF-` un documento representativo de cada uno de los seis
registros; no se comprobó la descarga completa de todos los PDF.
Los convenios generales, el inventario de caseríos y las subvenciones no se
transforman en proyectos. No se ha verificado un registro de licencias concedidas;
los métodos de licencias generan una salida vacía con estado deshabilitado.

## Otras fuentes oficiales y geometría

- [Open Data Bizkaia: planeamiento de Markina-Xemein](https://www.opendatabizkaia.eus/es/catalogo/planeamiento-urbanistico-markina-xemein):
  consultado en vivo, incluido el JSON de datos globales 2023–2026. Contiene
  estadísticas municipales por ejercicio, no expedientes concretos. Excluido de
  los registros. La fecha de extracción del conjunto no es una aprobación.
- [Registro de Planeamiento Urbanístico de Bizkaia](https://www.bizkaia.eus/es/planeamiento-urbanistico-buscador):
  inventario oficial complementario localizado; no integrado en esta extracción.
- [BOPV, anuncio de aprobación inicial de Etxetic](https://www.euskadi.eus/bopv2/datos/2025/05/2501930a.shtml):
  localizado durante el descubrimiento y enlaza la página municipal. No se usa
  para completar fechas ni fases de los registros del inventario documental.

`geometry_status: unavailable`. Los documentos contienen planos PDF, pero no se
ha verificado una geometría vectorial vinculada a los seis identificadores.
No se vectorizan planos ni se usan centroides, coordenadas inventadas o jitter.
Todos los registros llevan geometría y coordenadas null y `publication_ready=false`.

## Validación reproducible y evidencias locales

`python -m unittest municipio.test_markina_xemein -v`: **4 pruebas**, cubriendo
descubrimiento por imagen, exclusión de formularios, recorrido completo de
paginación, servidor que repite páginas, falta de siguiente página, agrupación
de instrumentos y fases, fechas vacías, IDs estables y preservación de una salida
anterior ante errores. Se verifica también la carga mediante manifest/registro.

La extracción real usa `load_manifest('markina-xemein')`,
`load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
La configuración opcional `capture_dir='evidence/live'` guarda los HTML recibidos;
el manifest no fija una ruta de evidencias ni activa programación.

- `evidence/proyectos.jsonl`: seis registros extraídos mediante este adaptador.
- `evidence/validation.json`: recuento real, URLs consultadas, mapa de capturas,
  comprobaciones PDF, resultados de pruebas y limitaciones.
- `evidence/live/`: las 17 capturas completas de la ejecución.
- `evidence/`: capturas adicionales del descubrimiento y estadísticas descartadas.

Las evidencias permanecen locales. No se han modificado fuentes compartidas,
dependencias, despliegues ni sistemas externos.
