# Los Silos — INE 38042

Verificado el 9 de noviembre de 2026. Municipio de Los Silos, provincia de
Santa Cruz de Tenerife, Canarias. Un único adaptador municipal; licencias y
programación deshabilitadas; sin jitter ni coordenadas inventadas.

## Descubrimiento y fuentes oficiales

Desde https://www.lossilos.es/ se descubre «Plan Urbanístico»:
https://www.lossilos.es/plan-urbanistico-3/ (HTTP 200).
Su contenido Divi organiza dos instrumentos, no noticias ni formularios:

- **Plan General de Ordenación vigente** (título literal de la web): 49 enlaces
  PDF, incluyendo memoria, normas, ordenanzas, ordenación pormenorizada y planos.
- **Plan Especial de Protección del Casco Historico** (título literal): 10 PDF,
  incluyendo memoria, estudio económico, normas, tres partes de catálogo y planos.

El PGO enlaza cuatro índices documentales, todos recorridos íntegramente:

- https://www.lossilos.es/ordenacion-pormenorizada/
- https://www.lossilos.es/planos-alineaciones-rasantes/
- https://www.lossilos.es/planos-de-informacion/
- https://www.lossilos.es/planos-de-ordenacion/

Se agrupan todos los PDF bajo su instrumento; cada documento conserva URL,
título y procedencia (página y sección). Los índices también se conservan.
Los planos de barrios, normas y catálogos no se convierten en proyectos nuevos.
Un enlace de Alineaciones y Rasantes apunta al icono `descargar-1.png`:
se conserva en `incidencias_fuente`, sin tratarlo como documento urbanístico.
No se observó paginación en ninguna de las cinco páginas. El adaptador rechaza
paginación detectada, formatos nuevos, páginas vacías y cambios de estructura.
Recorre los índices descubiertos, evita ciclos y aborta si excede el límite de
seguridad de 40 páginas por instrumento; nunca entrega un truncamiento por límite.

## Cobertura parcial y fuentes no incorporadas

La sede oficial https://lossilos.sedelectronica.es/info.0 enlaza la modificación
sustancial del PGO (Avance y Estudio Ambiental):
https://lossilos.sedelectronica.es/transparency/087404cf-b6c8-4c05-b12c-887d51c74dfc/
La página muestra enlace al acuerdo plenario de 1 de octubre de 2026 y un índice,
además de cuatro carpetas Wicket con 24, 10, 32 y 5 elementos. Esta fuente dinámica
**no se incorpora**: la cobertura se limita al inventario documental de la web
municipal, sin presentar el PGO publicado allí como consolidación completa de
modificaciones ni como relación de expedientes en tramitación. La captura de esta
página se conserva en evidencia para mostrar expresamente esa limitación.

Como contraste se consultó el inventario autonómico oficial:
https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-los-silos
API: https://opendata.sitcan.es/api/3/action/package_show?id=planeamiento-urbanistico-de-los-silos
Devuelve 15 recursos, agrupables en cuatro instrumentos/versiones: PGO, Plan
Especial, modificación Sibora-El Puertito y corrección Manzana 4.8. No se mezcla
con el inventario municipal: sus fechas, identificadores y versiones requieren
reconciliación propia. Captura JSON local `evidence/discovery-2.txt`.

No se extraen licencias concedidas, contratación, formularios, noticias ni obras
físicas como categoría separada. No se afirma una cobertura histórica completa.
El rótulo municipal «vigente» se conserva en el título, sin certificar vigencia
jurídica actual. No hay fechas de publicación o acuerdo explícitas en este
inventario: no se usan las rutas de carga `/2017/08/` como fechas de aprobación.
No se copia la fecha del acuerdo de 2026 a ninguno de los instrumentos anteriores.

## Geometría y semántica

`geometry_status: unavailable`. Los planos son documentos PDF: no se ha verificado
una geometría vectorial vinculada a estos instrumentos ni se han vectorizado.
No se generan centroides ni latitud/longitud. `publication_ready: false`.
La política compartida anota ambos registros como `pendiente` por falta de una
referencia formal de expediente; no se inventa esa referencia para hacerlos
aptos para publicación. Son inventarios documentales reales de instrumentos.

## Validación reproducible

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_los_silos -v`, **4 pasan**.
Cubren agrupación, deduplicación, procedencia múltiple, enlaces sin texto, ciclos,
rechazo de paginación y enlaces no cubiertos, ausencia de fechas/coordenadas,
conservación de salida anterior ante error, carga de manifest y licencias vacías.

Extracción real mediante `load_manifest('los-silos')` y
`load_portal_adapter(manifest).backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
Para reproducir capturas, configurar antes
`manifest.portal.config['capture_dir'] = 'evidence/live-captures'`.

Resultado: **2 registros, 59 enlaces PDF**, cinco páginas HTTP 200 recorridas.
Se descargó una muestra PDF por instrumento (memorias, HTTP 200 y cabecera `%PDF-`),
no se validaron individualmente los otros 57 enlaces. Evidencias locales no
versionadas: `evidence/proyectos.jsonl`, `evidence/validation.json`, capturas HTML
por hash de URL en `evidence/live-captures/` y dos PDF de muestra.
Las actualizaciones reconstruyen el inventario completo: no existe cursor ni
fecha incremental fiable. La escritura se realiza tras completar la extracción.
Sin ejecución de pipeline, publicación, bases de datos ni despliegues.
