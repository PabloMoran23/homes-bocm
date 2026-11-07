# Bolaños de Calatrava — investigación y cobertura

Comprobación en vivo: 2026-11-07. Municipio INE **13023**, provincia de
**Ciudad Real**, Castilla-La Mancha. Adaptador específico del municipio, sin
modificaciones de infraestructura compartida ni dependencias.

## Fuentes oficiales descubiertas

- [Área municipal de Urbanismo](https://bolanosdecalatrava.es/urbanismo):
  contacto y explicación de la tramitación, no registro de licencias otorgadas.
- [Entrada municipal POM](https://bolanosdecalatrava.es/pom): declara que contiene
  la información del Plan y enlaza el inventario, no es otro instrumento.
- [Inventario del Plan de Ordenación Municipal](https://bolanosdecalatrava.es/node/2352):
  fuente de extracción; enlaces Información, Ordenación, Anexos y 13 PDF de
  modificaciones/corrección. La búsqueda web oficial permitió localizar esta
  página; la extracción vuelve a solicitarla directamente.
- [Información](https://bolanosdecalatrava.es/node/2347),
  [Ordenación](https://bolanosdecalatrava.es/node/2348),
  [Planos de ordenación](https://bolanosdecalatrava.es/node/2349),
  [Textos de ordenación](https://bolanosdecalatrava.es/node/2350) y
  [Anexos](https://bolanosdecalatrava.es/node/2351): secciones recorridas completas.
  Publican enlaces a archivos Google Drive desde la propia web municipal.
  Se conserva cada URL con título y página de procedencia; no se presupone que
  el hospedaje externo sea un inventario oficial independiente.

## Extracción y unidad de registro

Resultado real: **6 instrumentos, 92 enlaces documentales**:

| Instrumento | Documentos |
| --- | ---: |
| POM (información, ordenación y anexos) | 79 |
| Modificación puntual 2 | 2 |
| Modificación puntual 3 | 3 |
| Modificación puntual 6 | 3 |
| Modificación puntual 7 | 3 |
| Corrección de errores 1 | 2 |

Los anuncios DOCM/BOP y normativa de una modificación integran un mismo
registro. No son proyectos de obra adicionales. El encauzamiento, las redes y
otros anexos del POM tampoco se multiplican como obras ejecutadas. La corrección
de errores conserva su identidad propia, sin confundirse con una modificación
puntual de igual número. Identificadores estables por instrumento, sin depender
del orden de presentación ni de la fecha de descarga.

No se ha observado paginación del inventario: es un artículo Drupal con archivos
y subsecciones. Se recorre el grafo de subsecciones hasta agotarlo y se eliminan
ciclos y enlaces documentales duplicados. Los paginadores del calendario del pie
no pertenecen al inventario. Si aparece paginación dentro del artículo, un archivo
no clasificable o se supera el límite de seguridad de secciones, se aborta antes
de escribir una salida parcial. Las actualizaciones vuelven a obtener la
instantánea completa; no se declara seguimiento incremental histórico.

## Semántica y límites

Cobertura **parcial**, circunscrita al inventario del POM publicado por el
Ayuntamiento. No acredita exhaustividad de instrumentos vigentes, obras,
proyectos ni licencias municipales. No se inventan las modificaciones 1, 4 o 5.
No se recopilan noticias genéricas, formularios ni anuncios de contratación.
Licencias desactivadas por ausencia de registro de concesiones verificado.

Se extraen metadatos del inventario HTML, no el contenido de los PDF ni de Drive.
Los nombres incluyen anuncios de aprobación definitiva y fechas, pero no permiten
atribuir con seguridad una fecha de acuerdo o publicación al instrumento
completo. Por ello `fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob`
y `fase` quedan nulos. Se conservan los títulos originales de cada archivo para
consulta documental. No se afirma aprobación actual o vigencia normativa.
Sin coordenadas ni geometría verificadas: valores nulos y
`publication_ready=false`. Sin jitter y sin ejecución programada.

El servidor HTTPS falló la validación de cadena de certificados tanto con el
almacén de requests como con `/etc/ssl/certs/ca-certificates.crt`. La descarga
pública se realizó con `verify_tls: false`, excepción explícita en el manifest
(la clase verifica TLS por defecto). No se oculta el aviso de requests en el
adaptador. Esta limitación impide considerar autenticada criptográficamente la
captura. No se utilizaron credenciales.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas ejecutadas:
`python -m unittest municipio.test_bolanos_de_calatrava -v` (6 correctas).
Cubren agrupación, corrección frente a modificación, procedencia, fechas nulas,
recorrido de subsecciones/ciclos, paginación, cambios de estructura, documentos
no clasificables, resolución por manifest y licencias desactivadas.

Extracción real ejecutada con `load_manifest`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`; incluye el guard de
entidades del registro común. Evidencia local no destinada a commit:
`evidence/proyectos.jsonl`, `evidence/validation.json` y capturas HTML de los seis
nodos, la entrada POM y Urbanismo. `validation.json` registra recuento,
fuentes, limitaciones y resultado de extracción. La clasificación de entidad
queda desconocida para estos instrumentos; no se fuerza una categoría de obra.
