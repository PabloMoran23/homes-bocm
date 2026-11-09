# Piedrabuena — Ciudad Real — INE 13063

Investigación: 9 de noviembre de 2026. Adaptador único:
`municipio.adapters.piedrabuena:PiedrabuenaAyuntamientoAdapter`.
Se revisaron primero `municipio/manifest.py`, `municipio/adapters/portal.py`
y los ejemplos Chipiona y Hernani. No se cambia el contrato compartido.

## Fuentes oficiales e inventarios actuales

- [Urbanismo](https://piedrabuena.es/areas-y-servicios/urbanismo): normas de
  edificación y catálogo de caminos con mapas y publicaciones de 2019. No
  constituyen por sí solos proyectos concretos ni licencias concedidas; excluidos.
- [Información pública](https://piedrabuena.es/ayuntamiento/administraci%C3%B3n-y-gesti%C3%B3n/informaci%C3%B3n-p%C3%BAblica):
  pliego/informe para concesión de dominio público destinada a puntos de recarga
  y Plan de Igualdad 2025–2029. El PDF de recarga fue descargado y examinado:
  expediente PIEDRABUENA2024/924, informe técnico firmado el 17/04/2024,
  junto a documentación de la concesión. Se excluye: no se transforma la
  convocatoria de concesión en una obra ejecutada ni en una licencia.
- [Actualidad municipal](https://piedrabuena.es/ayuntamiento/actualidad-municipal):
  archivo oficial Joomla, fuente de extracción. En la revisión se recorrieron
  **93 páginas y 372 entradas**. Cuatro noticias por página, enlaces
  `?start=4`, `?start=8`, etc., hasta `?start=368`. El orden no es estrictamente
  cronológico; no se detiene por antigüedad ni por haber encontrado candidatos.
  El scraper sigue todos los enlaces de paginación, exige el total anunciado y
  rechaza páginas repetidas, inventarios vacíos y cambios de estructura.

## Cobertura temática deliberadamente parcial

Se seleccionan tres actuaciones revisadas con evidencia de intervención física,
mediante asunto del título y comprobaciones adicionales del cuerpo. Todos los
títulos, descripciones, fechas y enlaces se obtienen de las respuestas HTTP de
cada ejecución; no hay registros de reserva ni resultados precargados.

1. [Rehabilitación de la Plaza de Toros / Taller +](https://piedrabuena.es/ayuntamiento/actualidad-municipal/817-el-ayuntamiento-de-piedrabuena-clausura-el-taller-rehabilitaci%C3%B3n-de-patrimonio-tras-seis-meses-de-formaci%C3%B3n-y-trabajo).
   Publicación del **01/10/2026**. El cuerpo identifica expresamente trabajo
   efectivo de albañilería y rehabilitación en la Plaza de Toros de Piedrabuena.
   No se registra el programa de empleo genérico como obra: la inclusión se apoya
   en esta intervención física identificada.
2. [Construcción Aula de Naturaleza y Deporte](https://piedrabuena.es/ayuntamiento/actualidad-municipal/812-construcci%C3%B3n-aula-de-naturaleza-y-deporte).
   Publicación del **10/08/2026**. Incluye cartel de la actuación y fotografías.
   Se descargó y revisó visualmente el cartel municipal: identifica la construcción
   de un aula para recepción de visitantes de actividades al aire libre y su
   cofinanciación. El scraper conserva los enlaces a las cuatro imágenes, sin
   convertir los porcentajes de ayuda en presupuesto ni inferir fase o aprobación.
3. [Renovación de redes de agua en cinco calles](https://piedrabuena.es/ayuntamiento/actualidad-municipal/272-el-ayuntamiento-de-piedrabuena-inicia-las-obras-para-renovar-redes-de-abastecimiento-de-agua-en-cinco-nuevas-calles).
   Publicación del **11/03/2022**. El cuerpo afirma comienzo y ejecución de obras
   en Eloy Gonzalo, Mónico Sánchez, Serna, General Sabariego y Castillo. Se mantiene
   el enlace a la comunicación original que el propio Ayuntamiento reproduce.

El archivo contiene otras noticias sobre museo, parque, adjudicación de gimnasio,
presupuestos, ayudas y actividades culturales. No se pretende cubrir todas las
obras municipales. Estas otras noticias quedan fuera de los tres asuntos
revisados. Tampoco se incluyen premios, exposiciones, formularios, licitaciones
ni anuncios genéricos de empleo. Esta limitación temática es explícita aunque
la navegación del archivo sí sea completa.

## Semántica y documentos

`tipo: obra_publica` describe la actuación física, sin usarlo como fase.
`descripcion` conserva el texto del cuerpo municipal, no un resumen inventado.
`origen: noticia_municipal_obra_fisica` aclara la naturaleza de la evidencia.
`fecha_publicacion` procede exclusivamente de `time[itemprop=datePublished]`.
No se extraen fechas de calendarios, modificación del CMS, firmas, comienzos
relativos ni finalizaciones previstas como fechas de aprobación/acuerdo.
No se emite `fecha`, `fecha_acuerdo`, `fecha_aprob`, fase, geometría o coordenadas.

Los avisos del mismo asunto y año se agrupan en un registro; cada noticia conserva
su URL y fecha de publicación en `documentos`, junto con imágenes y enlaces del
cuerpo. La fecha del registro es la primera publicación recuperada del grupo.
Los distintos años se mantienen separados para no fundir ciclos del taller.
Las imágenes son `imagen_municipal`, no se presentan como planos aprobados.
El documento informativo principal se identifica como `noticia_municipal`.
Los enlaces externos citados se retienen como `enlace_del_articulo`, sin atribuirles
autoría municipal ni rastrearlos como inventarios adicionales.

Licencias, programación y desplazamiento aleatorio de coordenadas desactivados.
`publication_ready: false`, `geometry_status: unavailable`. No se garantiza
vigencia jurídica, terminación de las obras ni cobertura de expedientes internos.
Algunas peticiones exploratorias sin User-Agent dieron 403; la ejecución emplea
`Mozilla/5.0`, timeout, reintentos limitados y validación de redirecciones. Si la
fuente falla, se aborta sin sustituir el último resultado por un parcial.

## Verificación y evidencia local

Runtime autorizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_piedrabuena -v`: **11 correctas**.
Cubren manifiesto, paginación completa, fallo por páginas ausentes/repetidas,
conservación del resultado anterior ante fallo, validación del cuerpo, exclusión
de contratación/formularios/noticias ajenas, procedencia documental, agrupación,
fechas, ausencia de coordenadas/acuerdos inventados y licencias desactivadas.

La extracción real llama directamente a `backfill_proyectos` con el manifiesto,
sin base de datos ni publicación. Resultado y métricas verificables en
`evidence/proyectos.jsonl` y `evidence/validation.json`. Las respuestas de esa
ejecución se capturan en `evidence/live-sources/`; investigación adicional en
`evidence/archive/`, `urbanismo.html`, `informacion-publica.html`,
`puntos-recarga.pdf`, `puntos-recarga.txt` y `cartel-aula.jpg`.
La evidencia es local y no forma parte de los cuatro archivos fuente entregados.
