# Pasaia — INE 20064, Gipuzkoa

Verificación: 2026-11-07. Adaptador único de catálogo municipal de planeamiento.

## Descubrimiento y alcance

Desde https://www.pasaia.eus/es/ se accede a «Urbanismo y Medio Ambiente»:
https://www.pasaia.eus/es/ordenanzas-urbanismo . El bloque **PLANEAMIENTO**
contiene cuatro entradas documentales (no noticias ni formularios):

- https://www.pasaia.eus/es/nnss — Normas subsidiarias, documentos A/B/C/D.
- https://www.pasaia.eus/es/plan-especial-cascos-historicos — memoria y normativa.
- https://www.pasaia.eus/es/plan-especial-portuario — documentos y carpeta de planos.
- https://www.pasaia.eus/es/plan-berezia-poblado-salinas-eta-andonaegi — plan especial,
  documentos técnicos y resoluciones.

Se descubren las entradas en cada ejecución, se recorren las subpáginas A/B/C y
**todas** las carpetas `?folder=` alcanzables. Se controlan ciclos y duplicados,
conservando cada URL de procedencia documental. Las carpetas que identifican
modificaciones, planes especiales/parciales y programas de actuación se convierten
en instrumentos separados, con sus subcarpetas. La modificación de Villa Ana
Mary–Izarra–Salinas–Azkuene Goia–Trintxerpe Goia aparece enlazada desde dos áreas:
se agrupa por su denominación idéntica, reteniendo las dos procedencias.
Los demás documentos se agrupan bajo el instrumento del catálogo correspondiente.
La resolución del proyecto de urbanización 2.06.04 Andonaegi es un registro separado
del Plan Especial Poblado–Salinas–Andonaegi; no acredita la aprobación de este último.
El plan portuario tiene alcance supramunicipal; sus planos se mantienen como documentos
del instrumento municipalmente enlazado, sin atribuir toda su superficie a Pasaia.

Cobertura parcial del planeamiento publicado en este catálogo, sin afirmar que sea
un registro legal completo o que cada versión documental esté vigente. No incluye
el PGOU en elaboración enlazado desde la portada ni inventario histórico completo.
https://www.pasaia.eus/es/obrak-eta-proiektuak es un archivo de noticias de 214
resultados y 22 páginas en la consulta; **no se utiliza ni se extrae su primera página
como si fuese el inventario completo**. Contiene también avisos de cortes de agua.
No se extraen licencias: las ordenanzas de obras menores no son concesiones.

## Fechas y procedencia

No se usa una fecha genérica ni timestamps de descarga como fecha de publicación.
La narración municipal acredita aprobación inicial del plan especial por resolución
2022/161 de 2022-01-31 y aprobación definitiva del proyecto de urbanización por
resolución 2023/2134 de 2023-12-14. Se conserva la descripción literal y los enlaces
respectivos. Para el plan se explicita que `fecha_aprob` corresponde a aprobación
**inicial**, sin inferir su estado definitivo actual. Otros instrumentos carecen de
fechas verificadas en las páginas HTML: sus fechas quedan nulas.

La página del plan especial dice que el anuncio del BOG es del **6 de febrero de
2022**, pero el PDF enlazado `BOG.pdf` tiene cabecera **16 de febrero de 2022**.
Se han capturado ambos y extraído el texto del PDF para revisar la discrepancia.
`fecha_publicacion` permanece nula: el parser HTML no resuelve esa discrepancia ni
convierte la fecha del acuerdo en publicación. Los PDFs se conservan como enlaces,
no se inventan datos de su interior. La extracción normal no descarga ni interpreta
todos los archivos: verificar cada binario queda fuera de esta cobertura.

## Paginación y errores

El bloque de planeamiento y las carpetas examinadas no muestran paginación activa.
El widget independiente «Últimas noticias» de la página de urbanismo sí está paginado
y está fuera del bloque extraído. El parser rechaza paginación activa dentro del
inventario o las páginas documentales, respuestas vacías, estructura desaparecida,
instrumentos sin documentos y recorrido que supere 200 páginas por entrada. Ese
límite provoca error; nunca produce una muestra truncada. La salida se reemplaza
atómicamente únicamente al completar todo el recorrido. `update_proyectos` refresca
la instantánea completa; no simula un historial incremental ni escribe estado.

## Geometría

`geometry_status: unavailable`. Desde la navegación municipal se descubre
https://www.pasaia.eus/es/mapa-interactivo, con cartografía DWG, planos PDF y el mapa
de recursos https://herrigis.gis-cdn.net/pasaia_berria/index_es.html . No se ha
verificado una capa vectorial vinculable mediante identificador a los instrumentos
extraídos. Los documentos contienen planos, pero no se vectorizan ni geocodifican
por centroides municipales. Latitud, longitud y geometría quedan nulas;
`publication_ready: false`, `geocode.jitter_missing: false`.

## Reproducción y evidencia local

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_pasaia -v
```

Cinco pruebas offline: catálogo acotado y duplicados, carpetas y títulos documentales,
rechazo de contenido/paginación inesperados, separación del proyecto y sus fechas,
agrupación de modificaciones con subcarpetas/ciclos y múltiples procedencias,
preservación de salida ante error, manifest y licencias deshabilitadas.

Extracción real mediante `PasaiaAyuntamientoAdapter(config={'capture_dir':
'evidence/captures'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
Resultado: **16 instrumentos/proyectos**, **462 enlaces documentales únicos**,
**78 páginas HTML recorridas**. Incluye cuatro entradas principales, once
instrumentos anidados y el proyecto de urbanización separado.
Las capturas HTML usan el SHA256 de la URL (primeros 16 caracteres) como nombre.
`evidence/validation.json` registra conteo final, fuentes recorridas, documentos y
limitaciones. Evidencia local excluida del código. No se activa planificación,
publicación ni servicios externos; `schedule.enabled: false`, licencias deshabilitadas.
