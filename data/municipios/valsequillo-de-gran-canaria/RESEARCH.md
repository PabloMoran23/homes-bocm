# Valsequillo de Gran Canaria — INE 35031

Verificado el 2026-11-07. Municipio de Las Palmas, Canarias.

## Descubrimiento y fuentes oficiales

La búsqueda de inventarios oficiales localizó la página municipal de
[Política territorial y medio ambiente](https://www.valsequillogc.es/ayto3/politica-territorial-y-medio-ambiente/).
El resultado indexado anuncia PGO vigente, documento aprobado en 2005,
alteraciones y desarrollo SUNCU 26 Calle Salvia, y remite a IDECanarias/GRAFCAN.
No se utiliza ese resultado como datos extraídos: el acceso directo falló por
certificado TLS (también con CA del sistema); HTTP y una petición diagnóstica sin
verificación cerraron la conexión. El adaptador mantiene verificación TLS activa.

Se localizó el [inventario municipal de planeamiento de SITCAN](https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-valsequillo-de-gran-canaria),
producido y mantenido por el Gobierno de Canarias, normalizado por GRAFCAN.
Es una fuente autonómica oficial para este municipio, no un portal municipal ni
un agregador privado. El adaptador declara `source: gobierno_de_canarias`.
`proyectos.source: ayuntamiento` en el manifest selecciona el contrato de adaptador
local existente; la procedencia real está explícita en cada registro y documento.

[API CKAN package_show](https://opendata.sitcan.es/api/3/action/package_show?id=planeamiento-urbanistico-de-valsequillo-de-gran-canaria):
HTTP 200, 21 recursos, última modificación de catálogo 2025-10-10. Devuelve el
paquete completo, sin paginación: se verifica `num_resources == len(resources)`.
Cada instrumento tiene una consulta GRAFCAN, un ZIP SIPU y un índice IDECanarias
marcado PDF en catálogo pero de MIME text/html. Se preservan ambas etiquetas
originales para no confundir un índice con un PDF descargado.

También se descubrieron la [sede electrónica](https://valsequillodegrancanaria.sedelectronica.es/info.0)
y la [página municipal de transparencia](https://www.valsequillogc.es/ayto3/transparencia/).
Los resultados muestran trámites, convocatorias y contratación; no se verificó un
registro de licencias concedidas ni un inventario completo de obras. No se convierten
formularios, anuncios de contratación o noticias en proyectos o concesiones.

## Cobertura comprobada

Extracción real mediante el adaptador cargado desde manifest: **7 instrumentos**,
**21 recursos de catálogo + 114 enlaces PDF de índices = 135 enlaces documentales**.

| Consulta GRAFCAN | Instrumento | Índice oficial |
| --- | --- | --- |
| 656 | Adaptación plena PGO al DL 1/2000 y Ley 19/2003 | [PGO](https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/GC/Vals/PGO/indice.html) |
| 1132 | Corrección de errores PGO número 1 | [CEPGO N1](https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/GC/Vals/CEPGO_N1/indice.html) |
| 1135 | Corrección de errores PGO número 2 | [CEPGO N2](https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/GC/Vals/CEPGO_N2/indice.html) |
| 1137 | Modificación puntual PGO número 4 | [MP N4](https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/GC/Vals/MP_N4/indice.html) |
| 1139 | Modificación puntual PGO número 6 | [MP N6](https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/GC/Vals/MP_N6/indice.html) |
| 1360 | Modificación menor artículo 80.3.2 | [Modificación menor](https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/GC/Vals/mmpgo-num2/indice.html) |
| 1473 | Plan Parcial SUNCU 26 Calle Salvia | [Plan parcial](https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/GC/Vals/pp-suncu26/indice.html) |

Se agrupan los recursos por denominación del instrumento sin narrativa temporal;
los IDs usan el identificador persistente de consulta GRAFCAN. Los planos, memorias,
anuncios y ZIP no generan registros adicionales. Se conservan títulos, descripciones,
IDs CKAN, URLs y procedencia. Se recorren todos los índices descubiertos y todos
sus enlaces PDF, resolviendo rutas relativas y deduplicando URLs. Ante paginación,
enlaces a subíndices o recursos de estructura desconocida se falla explícitamente;
no hay límite silencioso de páginas, registros ni enlaces. Una extracción fallida
no sustituye el JSONL previo por una instantánea parcial. Update refresca el paquete
completo; no hay cursor ni inferencia de bajas históricas.

Cobertura **parcial municipal**: sólo este catálogo, con instrumentos publicados
entre 2005 y 2023. La accesibilidad actual y actualización del catálogo no demuestran
que incluya todas las alteraciones posteriores, que todos los instrumentos sigan
vigentes o que exista actividad constructiva actual. No es un backfill universal
municipal y no contiene obras ni licencias.

## Semántica de fechas y documentos

`fase` expresa aprobación definitiva según la denominación oficial. `fecha` y
`fecha_publicacion` quedan nulas; las publicaciones múltiples se almacenan en
`publicaciones`, con boletín, número, fecha y fuente API. No se elige arbitrariamente
una fecha BOC/BOP como fecha de acuerdo. Sólo se rellena `fecha_acuerdo` cuando
la descripción dice expresamente «por Pleno COTMAC el»: 2006-12-20 y 2013-05-27
para las correcciones 1 y 2. No se deducen acuerdos de nombres de ZIP, fechas de
metadatos CKAN ni fechas de publicación. `catalogo_actualizado` no es una aprobación.

La modificación puntual número 4 contiene en catálogo BOC 211/15 con fecha
29/11/2015 y BOP 003/15 con fecha 07/01/2015. Se conserva literalmente esta
atribución en las descripciones y publicaciones: no se corrige ni valida de forma
independiente la cronología del catálogo. Los enlaces finales PDF, SIPU y consulta
se retienen, pero no se descargan ni verifican individualmente todos sus contenidos.
Los siete índices documentales sí se descargaron en la extracción real.

## Geometría

`geometry_status: unavailable` en esta extracción. El catálogo ofrece SIPU y consultas
GRAFCAN, y el índice PGO contiene planos PDF. No se han interpretado archivos ZIP,
vectorizado planos ni verificado geometrías por expediente y CRS. No se afirma que
la administración carezca de geometría. `geometry`, `lat` y `lon` son nulos y
`publication_ready` es falso; no se asigna centroide municipal ni jitter.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_valsequillo_de_gran_canaria -v`:
**5 pasan**, cubriendo agrupación, fechas, IDs, recursos incompletos/ajenos/formularios,
resolución de enlaces, duplicados, paginación, refresco, fallo sin salida parcial y
licencias deshabilitadas. Las pruebas usan fixtures sintéticos, no registros de producción.

Extracción ejecutada con `load_manifest`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, añadiendo únicamente
`capture_dir: evidence` en memoria. La anotación compartida de categorías informó
7 categorías desconocidas; son instrumentos urbanísticos sin categoría inmobiliaria
inferida. Esto no significa que falten registros.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, `evidence/sitcan-package.json` y siete capturas
`evidence/valsequillo-plan-*-index.html`. El informe incluye número real de registros,
URLs consultadas, enlaces y limitaciones. No hubo instalación, cambios compartidos,
publicación ni acceso a credenciales o servicios privados.
