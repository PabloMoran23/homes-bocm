# Urduña / Orduña — INE 48074, Bizkaia

Verificación y extracción en vivo: 2026-11-09. Runtime usado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento y fuente elegida

Web oficial: https://www.urduna.com/es-ES/Paginas/default.aspx . La portada
renderiza navegación mediante JavaScript. El script público
https://www.urduna.com/style%20library/serantes/js/serantes.js consulta las listas
SharePoint del menú. Se consultó, sin autenticación:
https://www.urduna.com/es-ES/_api/web/lists/getbytitle('Menu%20Segundo%20Nivel')/items .
Su entrada «Urbanismo» lleva a Servicios/Urbanismo y redirige al inventario:

https://www.urduna.com/es-ES/Servicios/Urbanismo/Paginas/default.aspx

El inventario y sus páginas 2–10 respondieron HTTP 200. Se extraen los enlaces PDF
de las secciones PGOU 2004, Plan Especial de Rehabilitación del Casco Histórico y
Modificaciones de planeamiento pormenorizadas. El parser sigue los enlaces de
paginación descubiertos, incluidos los que aparecen al avanzar, hasta agotar el
grafo. Contrasta rangos y total declarado con los documentos únicos obtenidos.
Falla ante rangos repetidos, huecos, cambio de total, documento sin clasificación,
marcado desconocido o exceso del límite de seguridad (1000 páginas). Escribe el
resultado sólo después de comprobar integridad; no se fija un límite de 10 páginas.

## Cobertura real y agrupación

Extracción mediante el adaptador cargado desde el manifest: **4 instrumentos,
54 enlaces documentales, 10 páginas**; los 50 documentos de la sección paginada
se recuperaron completos:

| Instrumento | Documentos | Identificación |
| --- | ---: | --- |
| PGOU 2004 | 34 | Memoria, normas, programa, listado y planos numerados |
| Revisión del PGOU | 16 | Participación, diagnóstico, avance, alternativas, DIE, alcance y certificados |
| Plan Especial de Rehabilitación del Casco Histórico | 3 | Dos partes de fichas y normativa general y particular |
| 1ª Modificación Puntual del PEOU U.E. 11.1 «La Estación» | 1 | Título explícito del enlace municipal |

La sección «PGOU 2004» también aloja documentos de la revisión. Se separan mediante
familias de archivos verificadas (`fase-1/2/3-*` y tres certificados/documentos
administrativos identificados en el código). No se generan proyectos por plano,
alternativa, fase de participación o certificado. Se conservan títulos y URLs de
todos los documentos y su sección de procedencia. Los identificadores de los
instrumentos no dependen del orden ni del número de página. Un documento nuevo
que no pertenezca a las familias conocidas exige revisión, evitando asignarlo
automáticamente al PGOU 2004.

Se descargaron como comprobación documental la memoria del PGOU 2004, el avance
de la revisión, el certificado de criterios y el PDF de La Estación. Capturas en
`evidence/`; no se incorporan PDFs al código ni se requiere un lector PDF en ejecución.
El avance se identifica en su portada como PGOU Urduña-Orduña, fase de avance,
diciembre de 2023. El archivo `20250915-10_aprobarcion-criterios.pdf` certifica un
acuerdo del **19 de diciembre de 2024**, con firmas de septiembre de 2025: demuestra
por qué no se deben convertir nombres de archivo en fechas de aprobación.

El índice no declara fechas de publicación/acuerdo/aprobación. El extractor deja
`fecha`, `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` a null; tampoco
atribuye aprobación definitiva ni estado vigente a partir de la mera presencia de
un PDF. Las fechas anteriores son observaciones de investigación documental, no
constantes inyectadas en los registros. La fase se deja a null porque una carpeta
mezcla fases y documentos de distintos momentos.

Cobertura **parcial** del municipio: biblioteca urbanística, no registro exhaustivo
de expedientes, licencias u obras. Se excluyen el estudio de tráfico de «Estudios»,
ordenanzas generales, información de ayudas y atención de rehabilitación. No se
han convertido noticias, formularios ni anuncios de contratación en proyectos o
licencias concedidas. Métodos incrementales: refresco completo de esta biblioteca;
no afirman un histórico de altas/bajas ni modifican un estado temporal.

## Otras fuentes oficiales examinadas

https://www.opendatabizkaia.eus/es/dataset/planeamiento-urbanistico-orduna
publica datos globales trimestrales y calificación del suelo. Su descarga JSON
https://www.opendatabizkaia.eus/es/dump/f87b2ad9-5a1b-404d-bc92-471cfdc565f1/datos-globales-planeamiento-orduna-2023-2026?format=json
identifica `URDUÑA/ORDUÑA`, código local `=074`. Se capturó el contenido, pero sus
filas son estadísticas de suelo/vivienda por periodo: **no son instrumentos ni
proyectos**, y no forman parte de la extracción. La fecha de extracción del dato
no es una fecha de acuerdo municipal.

También se examinó el inventario foral de evaluación ambiental:
https://www.bizkaia.eus/es/medio-ambiente/administracion-ambiental/evaluacion-ambiental .
La vista inicial de consultas no contiene instrumentos de Orduña. No se utiliza
esa vista como evidencia de ausencia de expedientes en todo su archivo.

## Geometría y límites

`geometry_status: unavailable`. La biblioteca enlaza documentos y planos PDF,
sin geometría vectorial asociada por identificador de instrumento. No se han
vectorizado planos, usado centroides municipales ni inventado coordenadas.
`lat`, `lon` y `geometry` son null; `publication_ready` es false. No se afirma que
no existan servicios GIS en otros portales; no se verificó uno enlazable a estos
cuatro instrumentos. Los enlaces del índice se conservan; no se descarga ni
interpreta automáticamente cada PDF en cada extracción.

## Validación reproducible

`python -m unittest municipio.test_urduna -v`: 5 pruebas correctas. Cubren agrupación
sin duplicar documentos, identidad municipal, exclusiones, conservación de fechas
nulas, recorrido completo, rangos repetidos, huecos, total cambiante, duplicados,
marcado/URLs/documentos desconocidos y conservación de la salida previa ante error.

La extracción real usó `load_manifest('urduna')`, `load_portal_adapter(...)` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`. Resultado: 4 registros,
con comprobación de los 50 archivos paginados y 4 archivos de otras secciones.
`evidence/validation.json` contiene conteo, URLs consultadas y limitaciones;
`evidence/live/inventory-*.html` conserva cada página de esa ejecución. Evidencia
local, excluida del commit. El manifest desactiva schedule, licencias y jitter.
Sin cambios compartidos, dependencias, publicación ni despliegue.
