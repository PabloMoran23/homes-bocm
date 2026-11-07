# A Estrada — INE 36017

Prueba 2026-11-07. Alcance: instrumentos publicados en inventario municipal de Urbanismo.

## Fuentes y extracción

https://aestrada.gal/urbanismo/ — HTTP200.
Se descubren enlaces a PXOM, Plan Especial Baiuca, Plan Parcial SUD-R06 y Estudo de
detalle SUD_R06. Se descargan realmente las cuatro páginas y se comprueba su
encabezado, agrupando documentos por instrumento. En el plan parcial se siguen dos
subpáginas documentales enlazadas, para obtener plan refundido, estatutos y bases.
No se recorren anuncios generales ni se convierte cada documento en proyecto.

Páginas actuales obtenidas HTTP200:
- https://aestrada.gal/urbanismo/pxom/
- https://aestrada.gal/urbanismo/plan-baiuca/
- https://aestrada.gal/urbanismo/plan-parcial-sud/
- https://aestrada.gal/estudo-de-detalle-sud_r06/

Resultado directo: **4 instrumentos, 6 documentos/archivos enlazados, 0 licencias**.
PXOM tiene un enlace ZIP completo de2,75GB: se conserva la URL, **no se descarga**.
Plan parcial y estudio de detalle SUD_R06 son instrumentos distintos, no documentos
duplicados; el detalle corresponde a Avenida Marín, el plan parcial a Avenida Vigo.
Las URLs de adjuntos/menús duplicadas se eliminan. No se infieren fechas desde años
del título o rutas WordPress ni se inventa descripción copiando el título.
No se afirma cobertura total de expedientes ni de todas las revisiones del PXOM.

## Geometría / visor

geometry_status: unavailable

El PXOM ofrece planos/documentación en directorios `/externas/pxom/`; los cuatro
instrumentos ofrecen PDF/ZIP, sin endpoint vectorial vinculado en sus páginas.
La búsqueda oficial `site:aestrada.gal visor urbanismo xeoportal` identifica visor
de franjas de prevención de incendios (https://mapas.xunta.gal/visores/faixas/),
que no acredita geometría de estos instrumentos y no se utiliza para localizarlos.
No se vectorizan planos ni se usan centroides municipales.

## Validación

2 pruebas pasan: descubrimiento de instrumentos, exclusión de navegación genérica,
deduplicación y enlaces externos no documentales. Import/check estático válidos.
HTTP timeout25s, pausa0,35s; límites30 instrumentos y10 subpáginas con fallo explícito.
Inventario revisado sin paginación. JSONL/validation.json conservados en
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/a-estrada/`.
`schedule.enabled: false`, licencias deshabilitadas, `geocode.jitter_missing: false`.
Sin orquestador/DB/publicación/cola. Pendiente geografía para validación de publicación.
