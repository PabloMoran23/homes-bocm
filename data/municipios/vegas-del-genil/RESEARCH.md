# Vegas del Genil — INE 18911, provincia de Granada

Investigación y ejecución real: 7 de noviembre de 2026. El campo `provincia`
identifica Granada; «Vegas del Genil (Granada)» es una etiqueta del encargo,
no el nombre de la provincia.

## Fuentes oficiales descubiertas

La web municipal https://www.vegasdelgenil.es/ enlaza su sede electrónica y
el portal https://vegasdelgenil.sedelectronica.es/transparency/ . La navegación
pública ofrece «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» (130 documentos)
y «7.1. PLANEAMIENTO URBANÍSTICO» (122 documentos):

- https://vegasdelgenil.sedelectronica.es/transparency/02cea94f-c3ce-4e92-9c18-4eecdf076476/
- https://vegasdelgenil.sedelectronica.es/transparency/9092178d-b38b-469c-85b1-dedfbf8e942b/

El adaptador descubre estos destinos de nuevo en cada ejecución, resolviendo
los callbacks públicos Wicket mediante `Ajax-Location`; no fija tokens de sesión.
No necesita autenticación. «Mostrar más» devuelve componentes XML: se extrae
su HTML sin ejecutar JavaScript. Se recorren todas las páginas de planeamiento
y de cada carpeta documental hasta que desaparece el botón o su contenedor
queda explícitamente oculto. Se rechazan respuestas inesperadas, ciclos,
paginación detenida, carpetas anidadas nuevas y discrepancias con el número de
documentos anunciado. Los límites de seguridad fallan, nunca devuelven un
prefijo como extracción completa. La raíz del portal se consulta para navegar
por secciones; sus anuncios generales quedan fuera del inventario seleccionado.

La noticia https://www.vegasdelgenil.es/aprobacion-inicial-del-pgou/ enlaza
un visor externo, y la categoría https://www.vegasdelgenil.es/category/urbanismo/
contiene noticias heterogéneas. No se usan como inventarios de proyectos.
Se localizaron también anuncios oficiales BOP/BOJA, pero no se agregan como
registros independientes ni se afirma haber cubierto esas colecciones:
https://www.juntadeandalucia.es/boja/2026/14/71 y
https://www.juntadeandalucia.es/boja/2020/216/106 .

## Cobertura y agrupación

Resultado de la ejecución mediante el adaptador cargado desde el manifest:
**20 registros con 115 enlaces documentales**, 29 entradas de inventario
recorridas y 57 respuestas HTTP capturadas. El apartado 7.1 contiene 24 carpetas
y cinco documentos sueltos; se leen todas sus páginas y todas las carpetas,
incluso las posteriormente excluidas.

Se conservan el PGOU, las innovaciones de suelo docente, estudios de detalle
(Fresno, PUE8, BPP5 manzana 2, PUE2, BPP3, PP12, Calle Encina, Calle Real y
BUE18), el proyecto de uso deportivo, proyectos de urbanización (PP12, PUE26,
BPP7), el conjunto BPP7, P-PP8, la planta de residuos y AUE2 de Ambroz.
Cada documento conserva título, URL pública de previsualización y carpeta de
procedencia. No se colapsan documentos distintos solo por tener igual título.

La unidad es el paquete municipal de un instrumento o actuación, no cada PDF.
Se reúnen las dos carpetas del expediente 825/2024 P-PP8 y las dos del ámbito
PUE2, conservando ambos títulos y carpetas. Este último es un conjunto mixto
con estudio de detalle, urbanización y reparcelación: no se presenta como una
única aprobación. PUE26 permanece separado. Los dos decretos de Calle Encina
se agrupan por el expediente 4916/2022 identificado en sus metadatos; no se
copian los datos personales que también contienen esos atributos. Dos anuncios
sueltos del estudio PP12 se incorporan a la carpeta GE 4867/2021. El anuncio
suelto sin identidad se excluye.

Se excluyen normalización de fincas GE 3779/2021, la carpeta genérica de
consultas GE 796/2026 y admisión a trámite de críquet GE378/2022: sus rótulos
no bastan para establecer aquí un instrumento identificable. GE 3791 PP12 sí
se admite porque sus documentos nombran explícitamente el proyecto reformado
de urbanización. No se extraen formularios ni licitaciones como actuaciones.

Cobertura **parcial**: inventario documental actual del apartado 7.1, sin
promesa de exhaustividad histórica, vigencia jurídica, últimas fases o cobertura
de obras de otros apartados. El inventario incluye publicaciones hasta 2026.
No se ha revisado el contenido completo de todos los PDF. Los enlaces de
previsualización son procedencia documental, no URLs directas de descarga.

## Semántica y validación

No se deducen fechas desde nombres de archivo, fechas de noticia o años de
expediente: `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` quedan nulas.
Los títulos originales pueden mencionar aprobación; no se convierten en una
fase actual. No se crean coordenadas ni geometrías. `publication_ready` es
false y `source_entity_type` es documento: la política común reconoce los 20
como documentación, sin incidencias de identidad desconocida. No se afirma
que sean licencias concedidas ni obras ejecutadas. El manifest desactiva
licencias, programación y desplazamiento artificial de coordenadas.

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_vegas_del_genil -v`, ocho correctas.
Cubren agrupación y aislamiento PUE2/PUE26, P-PP8, decretos relacionados,
exclusiones, identidad documental, fin de paginación normal y oculto, cambios
de estructura, dominios externos, manifest y licencias desactivadas.

Ejecución real: `load_portal_adapter(load_manifest('vegas-del-genil'))` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `capture_dir`
apuntando a `evidence/live-captures`. No se usan servicios de publicación.

Evidencias locales no versionadas: `evidence/proyectos.jsonl`,
`evidence/validation.json`, `evidence/live-captures/source-*.txt`, capturas
adicionales de descubrimiento y `evidence/inventory.txt`. La validación incluye
recuento real, URLs de las fuentes, limitaciones y resultado de la política.
La muestra documental del proyecto de urbanización de Ambroz
https://vegasdelgenil.sedelectronica.es/preview-document/b0d7557e-8c7e-474b-986a-a8b30e2a9113
respondió con previsualización HTML y un PDF con firma `%PDF-` válida; solo se
leyeron sus primeros 2048 bytes. Captura y comprobación en
`evidence/sample-document-prefix.bin` y `evidence/sample-document-validation.json`.
