# Carlet — INE 46085, Valencia

Investigación y extracción en vivo: 7 de noviembre de 2026. Se revisaron primero
`municipio/adapters/portal.py`, `municipio/manifest.py`, el registro de adaptadores
y los ejemplos Chipiona y Hernani. Solo se añade el adaptador de Carlet; no se
modifican fuentes compartidas, dependencias ni configuración de publicación.

## Identidad y descubrimiento

El [Registro de Entidades Locales de la Generalitat](https://www.entidadeslocales.gva.es/index.php?Itemid=9&id=46085&lang=es&option=com_reglocal_entloc&task=muestraEntidad&tipo=1)
identifica Carlet, código INE 46085, provincia València/Valencia y web carlet.es.
Las peticiones a la web principal, con y sin www y por HTTP/HTTPS, cerraron la
conexión desde este entorno. No se usan resultados de buscador como registros.

La [sede electrónica municipal](https://carlet.sedelectronica.es/) enlaza su
[portal de transparencia](https://carlet.sedelectronica.es/transparency).
La [rama 7 de urbanismo](https://carlet.sedelectronica.es/transparency/29de08a5-fa03-401e-92eb-7aa7ba6e63cf/)
indica 453 elementos descendientes; no son 453 proyectos. Contiene análisis de
agua, normativa, información pública de licencias ambientales y otras materias
fuera de alcance. Tiene doce carpetas directas, diez visibles inicialmente y
dos recuperadas mediante el botón Wicket «Veure'n més». Se verificó esta carga
real con el mismo método de navegación del adaptador; captura y resultado en
`evidence/pagination-captures/` y `evidence/pagination-validation.json`.

## Fuentes implementadas y resultado

Cobertura deliberadamente parcial de dos ramas documentales actuales:

* [7.1 Planeamiento urbanístico](https://carlet.sedelectronica.es/transparency/589a7057-d378-4c62-af6c-dad93cd7d7ed/).
  Se recorren todas sus subcarpetas. Modificación puntual 8: cuatro documentos;
  modificación 9: cinco; catálogo de protecciones del patrimonio cultural: tres;
  modificación 11 (Ausias March): seis; modificación 10 (Fornals): cuatro;
  PP Ausias March II: un documento, «PLAN PARCIAL AUSIAS MARCH II (CON MODIF
  INCLUIDAS)». La carpeta PP Ausias March I está vacía y no genera un registro.
  El enlace externo «Pla General d'Ordenació» apunta a
  http://www.carlet.es/va/content/pla-general-dordenacio y queda excluido,
  sin sustituirlo por una actuación sintética.
* [7.10 PAI Ausias March II UE-2](https://carlet.sedelectronica.es/transparency/8787db3a-7f67-4cd4-8086-6b2ce4e90270/).
  Un único instrumento con dos documentos: alternativa técnica/proposición
  jurídico-económica y proyectos de urbanización. Son documentación sustantiva
  de una actuación identificada, no una mera convocatoria contractual.

Resultado en vivo: **7 instrumentos, 25 enlaces documentales**. Cada instrumento
conserva su URL estable de carpeta y todos sus documentos municipales asociados,
con títulos literales y enlaces `/preview-document/UUID`. Los acuerdos, edictos,
estudios ambientales y documentos técnicos de una misma carpeta se agrupan;
no son proyectos independientes. Las carpetas contenedoras no generan registros.
Los identificadores se derivan de las URLs estables, no de tokens de sesión.

Se abrió la previsualización municipal y se comprobó la firma `%PDF-` y respuesta
HTTP de una muestra técnica de la modificación 11 y del proyecto de urbanización
del PAI. Se conservan HTML, URL final y primeros 4096 bytes en evidencia; no se
ha descargado ni interpretado jurídicamente todo el corpus.

## Navegación y semántica

Se usa una sesión HTTP pública. Los enlaces de carpetas se descubren leyendo el
argumento URL de `wicketAjaxGet`, sin ejecutar JavaScript. La navegación resuelve
a URLs estables `/transparency/UUID/`. La paginación consume todos los componentes
HTML de las respuestas XML de carga adicional; ignora scripts, detecta falta de
progreso y falla si cambia el esquema, aparece paginación desconocida o se supera
un límite de seguridad. Esos límites producen error, nunca salida parcial.

No se afirma cobertura histórica completa, vigencia, aprobación final de todos
los instrumentos ni ejecución de obras. El PAI y el plan parcial son instrumentos
distintos, aunque compartan el ámbito Ausias March. Otras ramas, como proyectos
arqueológicos o la agenda de reconstrucción, no están implementadas.

No se fabrican coordenadas, fechas o fases. Los títulos de algunos documentos
contienen fechas, entre ellas «Certificat acord Ple 21-07-2022», pero no se toma
una fecha de archivo o de documento como aprobación de todo el instrumento.
No se asigna `fecha`, `fecha_publicacion`, `fecha_acuerdo` ni `fecha_aprob` sin
extraer y comprobar el contexto del documento. Esas fechas permanecen en los
títulos originales. La fecha de extracción aparece solo en la validación local.

Licencias desactivadas: los formularios y la información pública ambiental no
constituyen un inventario de concesiones verificadas. Los métodos de licencias
fallan explícitamente si se invocan. `schedule.enabled=false`,
`geocode.jitter_missing=false`, `publication_ready=false` y geometría no disponible.

## Reproducción y evidencia

Runtime preinstalado utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_carlet -v`. Ocho pruebas de parser,
agrupación/aislamiento documental, exclusión de títulos genéricos, navegación,
paginación XML, metadatos no inferidos, fallo sin sobrescritura y carga de manifiesto.

Extracción: `load_manifest('carlet')`, `load_portal_adapter(manifest)` y
`adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con
`manifest.portal.config['capture_dir']='evidence/captures'`. Se ejecutó el adaptador
a través del registro compartido existente. Su política de entidades anota las
siete filas como categoría desconocida; esto no acredita idoneidad para publicación.
No se ejecutó el pipeline completo ni ninguna operación de base de datos,
geocodificación, publicación o despliegue.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, capturas HTML/XML del recorrido, muestra de documentos
y comprobación adicional de paginación. La validación incluye conteo real,
fuentes, exclusiones y limitaciones.
