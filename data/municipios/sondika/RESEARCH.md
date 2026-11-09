# Sondika — INE 48904, Bizkaia

Verificación en vivo: 2026-11-09. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento y fuente oficial

La web oficial https://www.sondika.eus y su menú «Planeamiento Urbanístico»
conducen a https://www.sondika.eus/es-ES/Ayuntamiento/Normas-Subsidiarias/.
El menú público también se verificó mediante el REST anónimo de SharePoint:
https://www.sondika.eus/es-ES/_api/web/lists/getbytitle('Menu%20Segundo%20Nivel')/items?$top=500.
La sección contiene PGOU, planeamiento general histórico, desarrollo y Proyectos.
El inventario elegido es:
https://www.sondika.eus/es-ES/Ayuntamiento/Normas-Subsidiarias/Paginas/proyectos.aspx.
No se usan noticias individuales como semillas ni se confunden formularios o
anuncios de contratación con obras aprobadas.

También se localizó el catálogo foral
https://www.opendatabizkaia.eus/es/catalogo/planeamiento-urbanistico-sondika,
que declara información orientativa, agregados y calificación. No se transforman
sus filas agregadas en proyectos ni se mezcla su cobertura con este inventario.

## Cobertura implementada

Se descubren todos los enlaces de proyectos del inventario oficial y sus bibliotecas
documentales desde las fichas. Se recupera el inventario de bibliotecas del subportal
y cada colección de archivos mediante `/ _api/web/lists` (sin el espacio), en lectura
anónima. Los GUID se descubren en cada ejecución, no se fijan seis obras en código.
Las colecciones OData se recorren hasta agotar `d.__next`, con rechazo de ciclos,
fallos HTTP, esquema inesperado o enlaces ajenos al dominio oficial. No hay límite
de registros ni corte silencioso. El inventario HTML es una lista estática de enlaces;
un control de paginación nuevo se rechaza explícitamente para revisión.

La ficha HTML de abastecimiento expone solamente nueve documentos. Su biblioteca
REST contiene los 23, que se recuperan íntegros. Los archivos y subproyectos se
agrupan en la obra de su ficha; no generan proyectos separados. Cada documento
conserva título, URL y ficha de procedencia. Se conserva también la URL del inventario.

Resultado real:

| Proyecto | Documentos |
| --- | ---: |
| Rehabilitación del caserío Artxanda Zaharra | 3 |
| Parque del Encuentro en Artxanda, fase 1 (rótulo del índice: Arxanda) | 5 |
| Recuperación de la parcela de Pike | 4 |
| Reposición de la red de abastecimiento de agua en Ola Sangroiz | 23 |
| Rehabilitación del tejado de la Casa de Cultura | 2 |
| Ampliación y reforma del Centro de Salud | 10 |

Total: **6 proyectos, 47 enlaces documentales**. Se extrae la publicación de
proyectos técnicos; no se acredita su ejecución, aprobación o concesión de licencia.
Las fechas de publicación, acuerdo y aprobación son nulas: ni las fechas de archivo
ni los nombres que contienen números se interpretan como fechas de acuerdos.
No se ha hecho OCR ni lectura semántica de todos los PDFs. No se descargan los
47 archivos: se conserva su inventario público completo y sus enlaces oficiales.

La cobertura es parcial para el municipio: no se extraen aquí PGOU, modificaciones,
planes especiales ni un histórico de boletines, ni proyectos ausentes de esta sección.
La actualización repite la instantánea completa; no escribe estado ni deduce bajas.
Licencias deshabilitadas, sin registro público de concesiones verificado.

## Geometría y validación

`geometry_status: unavailable`. Las fichas examinadas ofrecen planos en documentos,
sin coordenadas ni geometría vectorial vinculada verificadas para estas seis obras.
No se geocodifican centroides, ni se vectorizan planos ni se inventan coordenadas.
`schedule.enabled=false`, `geocode.jitter_missing=false`, `licencias.enabled=false`.

Pruebas: `python -m unittest municipio.test_sondika -v` (cuatro pruebas).
Cubren descubrimiento/deduplicación, paginación OData y ciclos, exclusión de enlaces
externos, documentos agrupados, semántica de fechas, IDs estables y carga del manifest.
Extracción en vivo mediante `SondikaAyuntamientoAdapter.backfill_proyectos`.
Evidencias locales: `evidence/proyectos.jsonl`, `evidence/validation.json` y capturas
HTML/JSON en `evidence/captures/`. No se usan DB, publicación ni despliegue.
