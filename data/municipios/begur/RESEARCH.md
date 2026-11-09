# Begur — INE 17013, Girona

Verificación y extracción real: 2026-11-09. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Se revisaron `municipio/adapters/portal.py`, el cargador de manifests, el registro
por importación y los ejemplos Manlleu y Hernani antes de implementar.

## Descubrimiento oficial y cobertura

La entrada municipal https://begur.cat/serveis/urbanisme/ enlaza directamente
«Projectes municipals en execució», «POUM en tràmit», «Normativa» y «Cartografia».
No se usa un resultado de noticias como sustituto de un inventario.

Fuentes extraídas (HTTP 200 en la ejecución real):

- https://begur.cat/serveis/urbanisme/projectes-municipals-en-execucio/ : inventario
  actual, una ficha. Se descubren y siguen todos sus enlaces de proyectos, sin
  límite de registros ni selección por título.
- https://begur.cat/serveis/urbanisme/projectes-municipals-en-execucio/projecte-arquitectonic-del-sector-dequipaments-de-la-font-de-baix/ :
  Font de Baix, obra física del sector de equipamientos. La narración municipal
  informa de adjudicación a RUBAU-TARRÉS S.A. y ejecución con suspensión estival
  hasta el 15 de septiembre. No se deduce el año de esa suspensión ni se verifica
  independientemente el avance actual. Se conserva la narración completa y el
  enlace municipal a la carpeta pública de proyecto en Google Drive. No se genera
  un registro a partir de un mero anuncio de contratación.
- https://begur.cat/serveis/urbanisme/poum-en-tramit/ : un solo instrumento,
  nuevo POUM en redacción/tramitación, con **14 enlaces** agrupados por sus
  secciones originales: un cartel de participación, nueve enlaces de Etapa 1
  y cuatro de Etapa 2. Se retienen los enlaces municipales a SharePoint y sus
  parámetros originales. Los encabezados de Etapa 3 y Etapa 4 no contienen
  documentos; son una descripción del proceso, no prueba de aprobación inicial,
  provisional o definitiva. Los anuncios de aprobación del programa participativo
  tampoco son aprobación del POUM.
- https://begur.cat/serveis/urbanisme/normativa/poum/poum-begur/ : POUM oficial,
  distinto de su revisión en trámite, con referencia al expediente RPUC **205091**
  y enlace general a MUC. La página identifica expresamente las normas del POUM
  de Begur; no se atribuye una fecha o fase de aprobación que no aparece allí.

Resultado: **3 registros reales**, **17 enlaces documentales/de consulta**.
Los enlaces de carpetas y expedientes se conservan como tales, sin presentarlos
como PDFs descargados. No se han inspeccionado los contenidos internos de Drive,
SharePoint o RPUC, ni se afirma que el inventario de archivos de esas carpetas sea
completo. Cada enlace conserva `source_url`; los del nuevo POUM también `seccion`.
Los distintos documentos no se convierten en proyectos independientes.

La cobertura es parcial: estas páginas municipales actuales, no un censo completo
de modificaciones de planeamiento, histórico de obras o expedientes del tablón.
La sección de normativa diferencia el POUM oficial del consolidado sin efectos
legales; el consolidado no se convierte en otro instrumento. La sede y el tablón
aparecen en la navegación municipal, pero no están implementados como fuentes.
No se ha verificado un registro público de licencias concedidas. Los formularios,
las solicitudes y las noticias ajenas al inventario no se extraen como licencias.

## Fechas, paginación y actualización

Las páginas extraídas no aportan fechas explícitas de publicación, acuerdo o
aprobación para estos registros. `fecha`, `fecha_publicacion`, `fecha_acuerdo` y
`fecha_aprob` son null. No se usan fechas de subida de imágenes, encabezados
WordPress, fechas de rastreo ni días sin año como fechas administrativas.

No se observó paginación activa. El parser rechaza paginadores detectados
(`rel=next`, pagination, nav-links, page-links, a.next); si aparecen en el futuro,
la ejecución falla hasta implementar su recorrido. Un inventario vacío o un cambio
de estructura también exige revisión. Se deduplican los enlaces de la lista y los
documentos por URL. Los identificadores derivan de la URL estable de cada ficha.
`update_proyectos` refresca la instantánea completa cubierta, sin cursor temporal.
La extracción termina antes de escribir el JSONL; un fallo de fuente no sustituye
el archivo anterior por una instantánea parcial.

## Geometría

https://begur.cat/serveis/urbanisme/cartografia/ ofrece callejero y visor
cartográfico. El POUM oficial enlaza además al visor MUC general. No se ha
verificado una geometría asociada por identificador a los registros extraídos.
No se usan coordenadas del ayuntamiento como ubicación de una obra ni se
vectorizan documentos. `geometry`, `lat`, `lon` son null,
`geometry_status=unavailable`, `publication_ready=false`.

## Validación y límites operativos

`python -m unittest municipio.test_begur -v`: **6 pruebas pasan**. Comprueban
inventario/deduplicación/paginación, obra física y procedencia, agrupación de
etapas sin inferir aprobaciones, referencia del POUM oficial, manifest y licencias
deshabilitadas y preservación de la salida previa ante fallo.

Extracción real mediante `load_manifest('begur')`, `load_portal_adapter(manifest)`
y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, activando únicamente la
captura local con `portal.config['evidence_dir']`. Resultado: 3 filas. Evidencias
locales: `evidence/proyectos.jsonl`, `evidence/validation.json` y capturas HTML
(capturas del adapter identificadas por hash de URL). `validation.json` enumera
las URLs realmente consultadas, recuentos y limitaciones. La anotación compartida
de política de entidades clasifica los tres registros como `unknown`; esto no
supone una categoría validada ni habilita su publicación.

`schedule.enabled=false`, `geocode.jitter_missing=false`, `licencias.enabled=false`.
No hay cambios compartidos, dependencias nuevas ni ejecución de publicación.
