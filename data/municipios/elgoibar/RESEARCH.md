# Elgoibar — INE 20032, Gipuzkoa

Revisión en vivo: 2026-11-07. Python utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento e inventario oficial

La portada https://elgoibar.eus/es/ enlaza Urbanismo y el PGOU.
El inventario utilizado es https://elgoibar.eus/es/servicios/urbanismo/ (HTTP 200).
Se recorren las secciones «Plan General de Ordenación Urbana (PGOU)», «Planes de
Ordenación Pormenorizada» y «Planes en proceso de tramitación»; esta última estaba
vacía. La sección contiene noticias generales ajenas al planeamiento, que se excluyen.
PIAU y movilidad quedan fuera del alcance declarado. No se extraen contratos,
formularios de solicitud ni supuestas licencias concedidas.

Se descubren 10 páginas de detalle, sin seeds de noticias individuales:

- https://elgoibar.eus/es/plan-general-de-ordenacion-urbana-pgou/
- https://elgoibar.eus/es/ekiola-parke-fotovoltaikoaren-plan-berezia-2/
- https://elgoibar.eus/es/modificacion-del-plan-parcial-del-ambito-ua10a-leruntxiki-morterika/
- https://elgoibar.eus/es/plan-especial-de-ordenacion-urbana-de-la-u-e-2-del-area-arriaga-1/
- https://elgoibar.eus/es/plan-especial-de-ordenacion-urbana-de-la-parcela-docente-ies-elgoibar-bhi/
- https://elgoibar.eus/es/plan-parcial-del-sector-9-f-alkorta/
- https://elgoibar.eus/es/plan-parcial-de-urruzuno-ambito-4b-urruzuno-2-y-3/
- https://elgoibar.eus/es/plan-especial-de-la-subestacion-electrica-del-barrio-azkue/
- https://elgoibar.eus/es/plan-especial-de-proteccion-y-ordenacion-del-parque-de-karakate/
- https://elgoibar.eus/es/santa-klara-19ko-plan-berezia/

## Semántica y cobertura

Resultado: **15 registros reales y 136 enlaces documentales**. PGOU y primera
modificación; Ekiola; tres modificaciones Leruntxiki-Morterika; dos de Arriaga;
IES Elgoibar; Alkorta; dos modificaciones Urruzuno; Azkue; Karakate; Santa Klara.
Cada pestaña municipal identifica un instrumento o una modificación numerada.
Memoria, normativa, planos y anuncio se agrupan bajo ese instrumento, sin crear
un proyecto por documento. Cuando no hay pestañas, la página identifica el plan.
Los IDs derivan de URL de detalle y título de pestaña, no del orden de documentos.
URLs repetidas dentro de un instrumento se deduplican conservando sus etiquetas.
Una etiqueta «(BOG)» de Leruntxiki apunta al texto refundido, no al boletín:
se conserva la etiqueta original sin reinterpretarla como procedencia del archivo.

Se conservan URL del inventario, URL de detalle y URL de procedencia de cada
documento. Las fechas de publicación, acuerdo y aprobación quedan **nulas**:
las páginas no ofrecen fechas semánticas explícitas y el extractor no interpreta
los PDF. Tampoco transforma una fecha de WordPress o de archivo en aprobación.
La fase queda nula, aunque varias etiquetas anuncian aprobación definitiva;
no se asegura vigencia actual ni ejecución material por esa etiqueta.
Se comprobaron HTTP 200 y cabecera PDF en anuncios de Ekiola y Santa Klara,
con copias locales. El resto de enlaces se conserva sin afirmar disponibilidad
individual comprobada. No es un histórico exhaustivo ni un registro de obras.

No se observó paginación en el inventario ni los detalles. El adaptador falla
explícitamente ante indicadores de paginación; no acepta silenciosamente una
primera página. No hay límite que corte registros. Cambios de pestañas, documentos
faltantes, secciones perdidas o nuevos enlaces no PDF requieren revisión y fallan
antes de reemplazar el JSONL anterior. La actualización refresca el inventario
completo; no mantiene un archivo histórico de instrumentos retirados.

## Geometría y clasificación posterior

geometry_status: unavailable

https://geo.elgoibar.eus/es/info/ identifica el servicio municipal y su apartado
PGOU. Se revisó esa descripción y se guardó captura; no se verificó una capa
vectorial asociable a cada instrumento. Los planos PDF no se vectorizan y no se
usan coordenadas del ayuntamiento como localización del plan. Coordenadas y
geometría nulas, `publication_ready: false`, jitter deshabilitado.

La ejecución a través de `load_portal_adapter(load_manifest('elgoibar'))` añade
la política compartida: 15 entidades «pendiente», `adapter_incident` por
`unknown_entity_spike`. Los instrumentos están documentados, pero el clasificador
exige referencias de expediente que este HTML no proporciona de forma verificada.
Se conserva esta incidencia para revisión; no se inventan expedientes ni se
modifica el clasificador compartido. «Ready» describe la implementación y evidencia
del scraper, no elegibilidad para publicación o aceptación del revisor.

## Validación reproducible

`python -m unittest municipio.test_elgoibar -v`: **6 pruebas pasan**. Comprueban
agrupación, deduplicación y etiquetas originales, independencia de IDs del listado
documental, fechas y geometría nulas, exclusión de noticias, rechazo de paginación
y estructura inesperada, escritura atómica ante fallo y licencias deshabilitadas.

Extracción en vivo con adaptador cargado desde manifest, timeout 30 segundos,
pausa 0,25 segundos y capturas de todas las páginas consultadas. Evidencia local
no destinada al commit: `evidence/proyectos.jsonl`, `evidence/validation.json`,
HTML y dos anuncios PDF. Validation incluye URLs, conteo, limitaciones, política
de entidades y comprobaciones PDF. Sin instalación, servicios de datos ni publicación.
