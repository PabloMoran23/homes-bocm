# Manzanares (Ciudad Real), INE 13053

Investigación y extracción en vivo: 7 de noviembre de 2026. Python utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes oficiales y alcance

El [inventario municipal de Urbanismo](https://www.manzanares.es/ayuntamiento/urbanismo)
expone una vista Drupal `view-urbanismo`, con documentos enlazados directamente
bajo «Plan de Ordenación Municipal», «Otros» e «Instrucciones». La consulta en vivo
respondió HTTP 200. Todo el inventario observado está en una sola página, sin
paginación visible. El adaptador rechaza paginación o enlaces de continuación si
aparecen; no impone un número máximo de registros ni recorta resultados. Un
cambio de estructura, una sección POM desconocida o la desaparición del POM y sus
modificaciones provoca error antes de reemplazar la salida.

Se inspeccionó también el [tablón de documentos expuestos](https://www.manzanares.es/ayuntamiento/documentos-expuestos).
La página observada mezclaba formularios, cuenta general, reglamentos y
procedimientos relativos a exhumaciones. No forma parte de la extracción; no se
presenta como inventario íntegro de obras ni de licencias. No se extraen noticias,
anuncios de contratación ni solicitudes como proyectos o licencias concedidas.

## Resultado y agrupación

La ejecución del adaptador a través de `load_portal_adapter(load_manifest('manzanares'))`
produjo **14 registros reales y 25 enlaces documentales**:

- Un POM, con 12 documentos: catálogo, fichas, planos, alineaciones, texto refundido,
  documentación sobre barreras y nuevas alineaciones del polígono que el municipio
  incluye en esa sección, y cuatro DWG de «Otros» inequívocamente cartográficos.
  Se conservan títulos, enlaces y sección de procedencia. Las piezas no se cuentan
  como doce proyectos distintos ni se afirma que sean una única versión consolidada.
- Doce modificaciones puntuales del POM: 10, 11, 12, 13, 15, 16, 18, 19, 20, 21,
  22 y 23. Un registro por número publicado, sin inventar los números ausentes.
  Si aparecen varios documentos con el mismo número se retienen en ese instrumento.
- Un Plan Parcial del PAU del Sector 5, representado por su documento «Normas
  Urbanísticas … (anuncio del BOP)». Es documentación de un instrumento concreto,
  no un anuncio de contratación ni una concesión de licencia.

La identidad se obtiene de la sección y títulos del inventario vivo. No hay
registros precargados. Los identificadores internos no son números de expediente
administrativo. `source_entity_type: documento` refleja la naturaleza documental;
la política común devuelve 14 documentos, cero identidades desconocidas y estado
`ok`. No se atribuye actividad elegible mediante referencias inventadas.

Se excluyen ordenanzas, código de accesibilidad, instrucciones de licencias,
formularios y los documentos de viabilidad/anteproyectos del contrato del agua.
Estos últimos no se convierten en una obra física individual a partir de un título
contractual. La cobertura es parcial para el municipio: no se recorren actas,
archivo histórico, contratación ni todas las fuentes posibles de obra pública.

## Fechas, geometría y procedencia

Las fechas de publicación, acuerdo y aprobación quedan separadas y nulas. La
mención de la introducción a enero de 2004 no identifica un acuerdo concreto ni
sirve para fechar todas las modificaciones. Tampoco se toman fechas del nombre
del PDF, metadatos CMS o búsquedas como fechas de aprobación. No se afirma vigencia
actual o aprobación definitiva a partir del título de un archivo.

Cada documento conserva `url`, `titulo`, `url_fuente` y `seccion_fuente`. Los enlaces
proceden del Ayuntamiento, incluso cuando el documento es una reproducción de un
BOP. No se afirma haber verificado individualmente todo el contenido documental.
Se descargaron íntegramente tres muestras oficiales (HTTP 200, `application/pdf`,
firma `%PDF-`):

- [Modificación 10](https://www.manzanares.es/sites/default/files/docs/urbanismo/mod10.pdf),
  19.777 bytes. Su texto identifica «MODIFICACIÓN PUNTUAL Nº 10» y contiene columnas
  de modificaciones propuestas y ordenanzas vigentes; no se deduce aprobación.
- [Eliminación de barreras](https://www.manzanares.es/sites/default/files/docs/urbanismo/eliminacionbarreras.pdf),
  779.365 bytes, sin texto útil mediante `pdftotext`.
- [Nuevas alineaciones del polígono](https://www.manzanares.es/sites/default/files/docs/urbanismo/nuevasalineacionespoligono.pdf),
  1.369.703 bytes, sin texto útil mediante `pdftotext`.

Los dos documentos sin texto se conservan como piezas de la sección POM, sin
inferir un expediente independiente, obra ejecutada, fecha o estado. Los DWG se
retienen como enlaces, sin extraer geometrías. Coordenadas y geometría nulas;
`publication_ready: false`, `geometry_status: unavailable`. Licencias, ejecución
programada y jitter de coordenadas están desactivados en el manifest.

## Verificación y evidencia local

Comando ejecutado:

```
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_manzanares -v
```

Cuatro tests correctos: agrupación y aislamiento entre instrumentos, duplicados,
procedencia y ausencia de fechas/coordenadas, exclusión de formularios/estudios,
rechazo de estructura vacía/cambiada, paginación, documentos desconocidos y URLs
inválidas; carga del manifest, licencias desactivadas y refresco completo mediante
`update_proyectos`.

Extracción real con `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, usando
el cargador común y `capture_dir=evidence`. Resultado: 14 registros, 25 enlaces.
`evidence/validation.json` registra fuentes, limitaciones, resultado y comprobaciones.
`evidence/urbanismo.html` es la captura de la propia ejecución del adaptador;
`evidence/documentos-expuestos.html`, los tres PDF y sus extracciones de texto
completan la investigación local. Evidencia sin incorporar al código fuente.
No se ejecutaron publicación, geocodificación, base de datos ni despliegue.
