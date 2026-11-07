# Etxebarri — Bizkaia — INE 48029

Verificado el 2026-11-07 con el runtime preinstalado. No confundir Etxebarri
(48029) con Etxebarria. La ficha institucional del Gobierno Vasco identifica el
municipio, territorio y dominio municipal:
https://www.euskadi.eus/entidad-local/etxebarri/web01-a2tokiad/es/

## Descubrimiento y fuentes oficiales actuales

- Área municipal de Urbanismo y Vivienda:
  https://www.etxebarri.eus/es-ES/Areas-Servicios/Urbanismo-Vivienda
- Página del nuevo PGOU, enlazada desde esa área:
  https://www.etxebarri.eus/es-ES/Areas-Servicios/Urbanismo-Vivienda/Paginas/PGOU-Etxebarri.aspx
- Inventario documental, enlazado desde el PGOU:
  https://www.etxebarri.eus/es-ES/Areas-Servicios/Urbanismo-Vivienda/Paginas/PGOU-Documentacion.aspx

Las tres responden HTTP 200 y son las fuentes recorridas por el adapter en vivo.
La portada española devuelve una carcasa JavaScript. Para descubrir el área se
examinaron las colecciones públicas de navegación y Servicios que usa la web,
mediante GET anónimo a su API web SharePoint. Capturas en evidence/; el adapter
final sólo requiere las tres páginas HTML anteriores, sin autenticación.

Se examinó también el catálogo oficial de datos abiertos:
https://www.opendatabizkaia.eus/es/organizacion/etxebarri/catalogo/planeamiento-urbanistico-etxebarri
Ofrece datos globales 2023–2026, históricos 2019–2022 y calificación pormenorizada
2019–2022. Sus cifras o filas de clasificación no se convierten en proyectos.
El catálogo advierte del carácter orientativo de la información frente a los
documentos normativos aprobados. Se localizó además el resumen de actividad
urbanística autonómico:
https://www.geo.euskadi.eus/cartografia/DatosDescarga/Planeamiento/Inbentarioa/PDF/res_48029_es.pdf
No se mezcla ese resumen con el nuevo PGOU ni se extrae de él en este adapter.
Las noticias externas y anuncios de contratación sólo sirvieron para búsqueda;
no generan registros. El trámite municipal «307. Obra mayor. Licencia» es un
formulario, no una concesión: licencias deshabilitadas.

## Cobertura y semántica

**Una entidad real: nuevo Plan General de Ordenación Urbana de Etxebarri**, con
16 documentos enlazados: prediagnóstico; memoria y dos grupos de planos de
estudios previos; informe del avance; avance; dos grupos de planos de información;
dos grupos de ordenación; presentación pública; tres documentos/planos de inicio
de evaluación ambiental y su solicitud EA; resumen del avance.
Los PDF son documentos del mismo instrumento, no 16 proyectos. El inventario
conserva títulos, enlaces completos y página de procedencia para cada documento,
deduplicando por URL. Identificador estable municipal del instrumento.

La página presenta documentación de fases 1–3 y enumera fases posteriores como
«Siguientes fases». Esa enumeración no acredita aprobación inicial, provisional
o definitiva. No se asigna una fase jurídica actual. Tampoco se convierten fechas
de talleres (incluido noviembre de 2026), nombres de archivo o fechas técnicas de
modificación web en fechas de acuerdo o publicación. Los cuatro campos de fecha
quedan nulos. No se considera que el nuevo PGOU sustituya ya al planeamiento
vigente. Cobertura parcial: no incluye todas las NNSS, modificaciones, planes
especiales, obras ni histórico de anuncios. No es un registro de licencias.

El inventario observado es una única página con todos sus enlaces, sin paginación.
Se extraen todos los PDF/ZIP del bloque documental sin límite de registros; si se
introduce navegación siguiente, se falla explícitamente para revisar el recorrido.
También se falla si desaparece la identidad, el bloque, el avance sustantivo o
cambia la procedencia de los documentos. La salida sólo se reemplaza después de
validar todo el recorrido. Actualización = instantánea completa del mismo ámbito.

## Geometría

geometry_status: unavailable

El inventario enlaza planos PDF, no geometría vectorial asociada por identificador
al nuevo PGOU. Los datos agregados de clasificación del catálogo provincial no
acreditan geometría de este instrumento. No se ha verificado una capa vectorial
atribuible al nuevo PGOU ni se vectorizan planos. Coordenadas y geometry nulas;
publication_ready=false y geocode.jitter_missing=false. Sin CRS inventado.

## Validación reproducible y evidencia local

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Pruebas: `-m unittest municipio.test_etxebarri -v`: **6 pruebas pasan** (agrupación,
deduplicación, fechas/geometría nulas, rechazo de formularios, pérdida de inventario,
paginación, cambio de procedencia, integración del manifest y conservación de
salida ante fallo).

Extracción real mediante `load_manifest('etxebarri')`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **1 registro, 16 documentos**.
Se ejecutó también la política compartida de entidades mediante el registry;
clasificación unknown, sin inferir un tipo residencial a partir del PGOU.
`evidence/validation.json` conserva recuento, URLs consultadas, limitaciones y
resultado de pruebas. Las capturas HTML del adapter se nombran con hash de URL;
las capturas de investigación conservan nombres legibles. Se descargó y comprobó
la firma PDF del resumen del avance (138747 bytes); hash SHA256 en validation.json.
Los otros 15 enlaces se conservan del inventario, sin descargar/verificar íntegramente
su contenido. Las evidencias son locales y no se incorporan a fuentes versionadas.

Schedule deshabilitado; sin publicación, base de datos, despliegue ni dependencias
nuevas. Sólo se añaden manifest, investigación, adapter y pruebas de Etxebarri.
