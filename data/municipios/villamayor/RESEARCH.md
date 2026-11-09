# Villamayor — Salamanca — INE 37354

Verificado el 8 de noviembre de 2026. Adaptador específico:
`municipio.adapters.villamayor:VillamayorAyuntamientoAdapter`.

## Descubrimiento y fuentes oficiales

- [Urbanismo municipal](https://www.villamayor.es/atencion-al-ciudadano/urbanismo.html):
  información de oficina y modelos de autoliquidación. No acredita concesiones.
- [Documentación municipal](https://www.villamayor.es/documentos.html): formularios
  de tasas/licencias, excluidos. No se convierten trámites en proyectos.
- [Portal de transparencia municipal](https://villamayor.sedelectronica.es/transparency/):
  carpetas documentales, incluida Urbanismo, obras públicas y medio ambiente.
  Se descubrió, pero no se incluye su contenido en esta cobertura.
- [Información urbanística de la Diputación](https://www.lasalina.es/Aplicaciones/GestorInter.jsp?codMunicipio=354&funcion=VerNormasUrbanisticas&nombre=Villamayor&prestacion=NormasUrbanisticas):
  identifica Villamayor y enlaza el archivo autonómico con provincia=37 y municipio=354.
  Indica que no dispone de información urbanística adicional.
- [PLAU, archivo oficial de la Junta de Castilla y León](https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=354):
  identifica expresamente VILLAMAYOR, Código INE 37354. Actualización indicada:
  06-nov-2026. Esta es la fuente efectiva del extractor, `source: jcyl`.
  El manifest usa `proyectos.source: ayuntamiento` como vía de adaptador de portal;
  no implica que el alojamiento del archivo sea municipal.

## Cobertura y paginación

Se recorre **todo el inventario PLAU con “Mostrar históricos” desmarcado**:
52 entradas en cuatro páginas (1–15, 16–30, 31–45, 46–52). Esto describe la vista
consultada, no certifica la vigencia jurídica actual de cada instrumento antiguo.
La página inicial sin parámetros muestra un orden distinto al de los fragmentos
AJAX. Por eso se verifica allí la identidad municipal y se inicia nuevamente el
recorrido con orden explícito `fPublicacion`, `pager.sortindex=-3`, offset 0.
Los offsets siguientes se calculan desde los rangos devueltos, sin máximo silencioso.
Se comprueban rangos, total estable, número de filas e identificadores únicos.
Un fallo de red, cambio de formato, página repetida o inventario incompleto impide
reemplazar el JSONL anterior. No se utiliza el estado incremental para saltar páginas.

Resultado real: **46 registros**, 52 entradas examinadas y 6 excluidas (3 convenios
CU y 3 anuncios de entidades colaboradoras EU). Se conservan 22 PP, 9 ED, 6 PGOU,
4 PN, 2 PAU, 1 PEX, 1 PE y 1 PERI. Son instrumentos/proyectos urbanísticos
identificados por el archivo, no anuncios de contratación ni noticias genéricas.
No se afirma que correspondan a obras ejecutadas o a licencias concedidas.

Cada `cDocId` conserva su título y fechas originales. Sus archivos no se convierten
en nuevos proyectos: **137 enlaces documentales agrupados**, de ellos 95 ficheros
y 42 accesos a boletines. Las revisiones/modificaciones registradas con distintos
identificadores permanecen separadas; compartir sector o número de expediente no
basta para afirmar que son el mismo instrumento. Los enlaces eliminan únicamente
el `jsessionid` transitorio. Cada fichero conserva el URL de su listado de origen.
Seis registros no tienen ficheros depositados en el archivo; se conservan con su
boletín y `documentacion_status: sin_ficheros_en_archivo`.

## Fechas y comprobación documental

`fecha_publicacion` y `fecha_acuerdo` proceden de sus columnas independientes.
Las fechas ausentes quedan nulas. No se asignan `fecha_aprob`, fases ni fechas de
concesión a partir de esas columnas. Algunas fechas antiguas del archivo presentan
publicación anterior al acuerdo; se conservan, sin corregirlas por conjetura.

Se descargaron además dos muestras documentales reales:

- [BOCyL del proyecto de expropiación del Camino de Gudino](https://bocyl.jcyl.es/boletines/2026/01/14/pdf/BOCYL-D-14012026-8-22.pdf),
  descubierto mediante `openBoletinDoc.do?cDocId=301277`. Verifica acuerdo de
  30/10/2025, publicación 14/01/2026 y expediente 1720/2022. El título del archivo
  escribe “GUINDO”; se conserva literalmente ese título, sin sustituirlo por el
  del boletín. El parser no extrae datos adicionales del texto del PDF.
- [Guía del documento del Plan Parcial Sector 9](https://servicios.jcyl.es/PlanPublica/openFichero.do?cFicheroId=45492),
  descubierto en el listado de cDocId=281549. Devuelve un PDF real que identifica
  Villamayor de Armuña, Salamanca y la modificación del sector 9.

Las demás URLs documentales se conservan desde los listados oficiales; no se han
leído todos los PDFs ni comprobado individualmente todos los destinos de descarga.

## Límites y geometría

Cobertura parcial del urbanismo municipal: no se extraen la totalidad del tablón,
carpetas de transparencia, noticias, contratación ni el histórico marcado de PLAU.
No hay registro de licencias concedidas verificado. `licencias.enabled: false` y
sus métodos generan salida vacía con estado deshabilitado.

geometry_status: unavailable

El archivo enlaza [SIUR para 37354](https://idecyl.jcyl.es/siur/index.html?id=37354).
No se ha verificado una geometría individual asociable a cada `cDocId`; no se
vectorizan PDFs ni se usan coordenadas del centro municipal. `lat`, `lon` y
`geometry` quedan nulos; `publication_ready: false` y `geocode.jitter_missing: false`.

La carga mediante el registro común anota las 46 entradas como `pendiente`, con
`adapter_incident / unknown_entity_spike`: la política compartida no reconoce
el identificador de catálogo PLAU como identidad de actividad. Se conserva
`archivo_id` sin disfrazarlo de número de expediente. No se modifica la política
compartida ni se considera esta extracción apta para publicación automática.
Este límite figura también en la evidencia de validación para el revisor.

## Validación reproducible

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_villamayor -v
```

**7 pruebas pasan**: fechas separadas, ausencia de datos, procedencia y agrupación
documental, paginación completa, exclusión de EU, rechazo de páginas repetidas o
totales cambiantes, conservación de salida ante errores, identidad municipal,
manifest y licencias deshabilitadas. Fixtures sintéticas sólo en las pruebas.

La extracción real se ejecutó con `load_manifest('villamayor')`,
`load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`,
con `portal.config.evidence_dir` apuntando localmente a `evidence/captures`.
Se realizaron 45 consultas HTML: identidad, cuatro páginas y 40 listados de ficheros.
Evidencias locales no destinadas a commit:
`evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/captures/`,
las páginas de descubrimiento y dos muestras PDF con texto extraído.
La validación conserva el recuento real, todas las URLs consultadas y las limitaciones.
`schedule.enabled: false`. Sin ejecución de publicación, sincronización o despliegue.
