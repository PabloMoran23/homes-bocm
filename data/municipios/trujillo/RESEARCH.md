# Trujillo — Cáceres — INE 10195

Investigación y extracción: 8 de noviembre de 2026. Se inspeccionaron el contrato
`municipio/adapters/portal.py`, el cargador de manifests y los ejemplos Manlleu,
Chipiona y Hernani antes de implementar el adaptador.

## Fuentes oficiales descubiertas

- https://www.trujillo.es/ — identifica Trujillo, Cáceres, código 10195.
- https://www.trujillo.es/urbanismo — la sección observada solo enlaza estudios
  ambientales; no ofrece un inventario de licencias concedidas ni planeamiento.
- https://www.trujillo.es/inversion-municipal — sin actuaciones en el contenido
  observado. El acceso HTTP directo con requests a la portada devolvió 403;
  las páginas municipales fueron inspeccionadas mediante la herramienta web.
- https://sitex.juntaex.es/SITEX/planeamiento — consulta oficial de planeamiento
  de la Junta de Extremadura. Su selector identifica **Trujillo con ID interno
  482**, que no se confunde con el código INE. La consulta comprende árboles
  de instrumentos anteriores a LSOTEX y bajo LSOTEX.

El adaptador utiliza el filtro público que ejecuta la interfaz:
`POST https://sitex.juntaex.es/SITEX/ptofiguras/listadoresultadossigcat`, cuerpo
`municipioseleccionado=482`. Es una consulta sin autenticación, no una mutación.
La respuesta AJAX deja el selector vacío: se verifica la identidad mediante
el enlace de refundido 482 y los rótulos `Trujillo - ...` de todas las figuras.
Cada figura se consulta en `/SITEX/ptofiguras/viewsigcat/{id}` y se exige que el
campo Ámbito territorial sea exactamente Trujillo. No se usan noticias,
formularios, anuncios de contratación ni resultados de búsqueda como registros.

## Unidad de extracción y semántica

Un registro por figura SITEX, ID estable `trujillo-sitex-{id}`. Las modificaciones
son instrumentos separados de su plan matriz. Todos los documentos de una ficha
(memoria, anejos, planos y publicaciones de trámites) se agrupan en `documentos`,
con sus enlaces y etiquetas. Se conservan todos los trámites fechados de la ficha.
Las fichas sin documentos descargables también son instrumentos identificados,
no registros sintéticos creados a partir de una página genérica.

Ejemplo contrastado: https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/40299
rotula la figura `Normas Subsidiarias, modificación 029`, referencia `NNSS.M-029`,
y su descripción dice **modificación puntual n.º 27**, UE-6.2, ampliación del
cuartel de la Guardia Civil. Se conserva esa discrepancia de numeración, sin
corregir ni fusionar instrumentos por número. La ficha distingue aprobación
definitiva 29/09/2022 y publicación DOE 29/12/2022; enlaza memoria y anexo:

- https://sitex.juntaex.es/SITEX/ptofiguras/downloaddocumento/11740
- https://sitex.juntaex.es/SITEX/ptofiguras/downloaddocumento/11741
- http://doe.juntaex.es/pdfs/doe/2022/2480o/22AC0095.pdf

`fecha_aprob` procede exclusivamente del campo Fecha AD; `fecha_publicacion`
del campo Fecha de publicación AD y se conserva Diario de publicación AD.
No se confunde una fecha de publicación con el acuerdo; `fecha_acuerdo`, fecha
genérica y fase quedan nulas. El estado publicado se conserva como `estado`.
No se afirma que un instrumento en trámite esté aprobado, ni que SITEX garantice
su vigencia jurídica actual. La fuente material figura como
`junta_extremadura_sitex`; el manifest usa el canal compatible `ayuntamiento`.

## Cobertura, límites y paginación

Se recorre la totalidad de ambos árboles entregados por el filtro municipal,
sin límite de número de fichas, sin seleccionar solo instrumentos vigentes ni
solo los primeros resultados. El árbol observado no tiene paginación; el parser
rechaza indicadores de paginación si aparecen para evitar truncamiento silencioso.
Cualquier error de identidad, estructura, fecha o descarga de ficha aborta antes
de escribir el snapshot. Update refresca el inventario completo; no usa fechas
de publicación como cursor y no escribe estado incremental ficticio.

Cobertura parcial del municipio: solo instrumentos existentes en SITEX, que
puede incluir fichas históricas, estados desactualizados y documentación incompleta.
No se promete un inventario completo de obras ni licencias municipales. No se
extraen textos de todos los PDF ni geometrías. Las coordenadas quedan nulas,
`publication_ready=false`, `geocode.jitter_missing=false`. Licencias y ejecución
programada están desactivadas. Los enlaces documentales se conservan tal como
los publica la fuente; su disponibilidad no se certifica para cada documento.

## Verificación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_trujillo -v` (7 pruebas): identidad municipal,
deduplicación, rechazo de paginación/cambios de estructura, agrupación y aislamiento
de documentos, distinción y ausencia de fechas, fallo sin escritura parcial,
carga real del manifest y licencias desactivadas.

Extracción real mediante `load_manifest('trujillo')`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, configurando localmente
`capture_dir='evidence'`. El JSONL pasa también por la anotación de política de
entidades del cargador compartido. Resultado y URLs consultadas se conservan en
`evidence/validation.json`; cada ficha y el inventario se guardan en HTML bajo
`evidence/`. Estos artefactos son evidencia local, no fuentes a incorporar al repo.

Resultado verificado: **60 instrumentos**, **194 enlaces documentales**, 57 fichas
con enlaces y 3 sin ellos; estados publicados Vigente, No vigente y En trámite.
Se guardaron las 60 fichas, el filtro y el JSONL real. Muestra descargada:
`downloaddocumento/11741`, HTTP 200, 29.318.615 bytes, firma `%PDF` válida,
Content-Type `application/octet-stream`; conservada como `evidence/memoria-11741.pdf`.
No se interpreta esa descarga como validación de todos los restantes enlaces.
