# Sotillo de la Adrada — Ávila — INE 05240

Verificado en vivo el 9 de noviembre de 2026. Se implementa exclusivamente el
inventario municipal de instrumentos de planeamiento: **3 registros reales y
13 enlaces documentales**, agrupados por instrumento. Es una cobertura parcial
municipal, no una certificación de vigencia consolidada, de obras ejecutadas ni
de licencias concedidas. `schedule.enabled`, `licencias.enabled` y
`geocode.jitter_missing` son `false`; `publication_ready` es `false`.

## Fuentes oficiales descubiertas

- [Web municipal](https://www.sotillo.net/): HTTP 200, enlaza Urbanismo.
- [Inventario de Urbanismo](https://www.sotillo.net/ayuntamiento/urbanismo.html):
  HTTP 200. Lista única sin paginación observada: tres instrumentos, ordenanzas,
  normativa sectorial y declaración responsable de obras. Los tres últimos
  recursos se excluyen porque son normativa genérica o un trámite reutilizable.
- [Sede electrónica](https://sotillodelaadrada.sedelectronica.es/info.0): HTTP 200,
  enlaza las Normas municipales y ofrece trámites y tablón. No se ha verificado
  aquí un inventario público de licencias concedidas. No se extraen solicitudes,
  declaraciones responsables, noticias ni anuncios de contratación.
- [Archivo autonómico PLAU, consulta INE 05240](https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=05&municipio=240):
  HTTP 200, identifica expresamente SOTILLO DE LA ADRADA, código 05240, y muestra
  resultados 1–15 de 17 con segunda página 16–17. Se descubre como inventario
  adicional de planeamiento y gestión urbanística, **fuera del alcance de este
  adaptador**. No se importan sus primeras 15 filas ni se presenta la extracción
  municipal como cobertura completa regional. Incluye sentencias y actuaciones
  distintas de los tres instrumentos municipales; requeriría su propio análisis
  de agrupación y vigencia. Captura de descubrimiento: `evidence/jcyl.html`.

## Instrumentos extraídos y procedencia

1. [Estudio de detalle de la ampliación del Polígono Industrial Las Ventillas](https://www.sotillo.net/estudio-de-detalle-de-la-ampliacion-del-poligono-industrial-las-ventillas.html).
   HTTP 200; cuerpo descriptivo y diez adjuntos PDF: anexos, ordenanzas, planos y
   textos. Se mantienen los diez enlaces incluso cuando sus nombres son parecidos;
   no se presume identidad binaria entre versiones. Un único instrumento, no diez
   proyectos. La página no declara fecha de acuerdo ni fase: quedan nulas.
2. [Modificación puntual 14 de las normas subsidiarias](https://www.sotillo.net/modificacion-puntual-14-de-las-normas-subsidiarias.html).
   HTTP 200; identifica «Obras e instalaciones en suelo rústico de especial
   protección», con un PDF adjunto. Sin fase, aprobación o publicación acreditadas
   en el cuerpo de la página: no se infieren de su título ni del nombre del archivo.
3. [Normas Urbanísticas Municipales de Sotillo de la Adrada](https://www.sotillo.net/normas-urbanisticas-municipales-de-sotillo-de-la-adrada.html).
   HTTP 200; declara aprobación definitiva por acuerdo de 7 de febrero de 2019 de
   la Comisión Territorial de Medio Ambiente y Urbanismo de Ávila. Se conserva como
   `fecha_acuerdo` y `fecha_aprob`, con fase de aprobación definitiva. Agrupa el
   [BOCyL enlazado](https://bocyl.jcyl.es/boletines/2019/03/29/pdf/BOCYL-D-29032019-17.pdf)
   y el [expediente PLAU 295692](https://servicios.jcyl.es/PlanPublica/openDocuIndice.do?cDocId=295692)
   del texto y planos. El adaptador conserva literalmente los enlaces HTTP de la
   página; la comprobación documental usa sus equivalentes HTTPS y registra ambas
   direcciones en `validation.json`.

Los doce PDF enlazados devolvieron HTTP 200, `application/pdf` y firma `%PDF` en
la comprobación en vivo; el índice PLAU devolvió HTTP 200 HTML. Estas comprobaciones
verifican disponibilidad y formato, no interpretan el contenido completo de los
documentos. Los textos y planos permanecen accesibles mediante `documentos`, con
el título y `source_page` de cada enlace.

## Semántica, cobertura y funcionamiento

Las fechas de creación/actualización de los artículos son metadatos de la web,
no del instrumento. `fecha` y `fecha_publicacion` permanecen nulas: la publicación
del boletín no se deduce de su URL ni se confunde con la aprobación. El adaptador
lee únicamente los cuerpos HTML y enlaces; extraer fechas adicionales de los PDF
queda fuera de esta cobertura.

Cada ID estable procede de la URL municipal del instrumento. Se descubren las
fichas desde el inventario, se comprueba la coincidencia del título y se exige
descripción con documentos. Formularios, páginas vacías, dominios inesperados,
redirecciones a otras páginas y falta de instrumentos provocan error. Los enlaces
documentales se deduplican por URL dentro de una ficha, sin dividir el instrumento.
Los documentos relacionados de otras fichas se excluyen mediante selectores del
cuerpo y del bloque de adjuntos.

El inventario municipal observado es una lista completa sin paginación. Si aparecen
controles de paginación se detiene con error explícito, para exigir adaptar el
recorrido; no se trunca silenciosamente. La actualización vuelve a leer el
inventario completo y reemplaza el snapshot solo tras obtener todas las fichas.
Cada petición tiene timeout de 40 segundos y límite de 3 MB para HTML; no hay límite
silencioso de filas ni dependencia nueva.

No se han extraído polígonos, parcelas ni coordenadas de los PDF. `geometry`, `lat`
y `lon` son nulos; no se usa un centroide municipal. La envoltura compartida del
registro de adaptadores clasifica estas tres filas como `pendiente` con
`insufficient_identity_evidence` porque no contienen un número de expediente
municipal acreditado en el HTML. No se inventa uno para alterar esa clasificación;
los registros, enlaces y esta limitación quedan disponibles para revisión. No están
habilitados para publicación.

## Validación reproducible y evidencia local

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```bash
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_sotillo_de_la_adrada -v
```

Resultado: **8 pruebas pasadas**. Cubren exclusión de trámites y noticias,
agrupación y procedencia de diez adjuntos, identidad estable, fecha de acuerdo
distinta de publicación y actualización web, ausencia de geometría y fechas
inventadas, rechazo de contenido incompleto o no oficial, detección de paginación,
actualización por snapshot, licencias deshabilitadas y configuración del manifest.

Extracción real mediante `load_manifest`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **3 registros**. El config
local `evidence_dir` permite capturar el HTML exacto leído por el adaptador.
`evidence/validation.json` contiene `live_records`, `source_urls`, limitaciones,
resultado de la envoltura compartida y comprobaciones de los trece enlaces.
`evidence/` es local y no se incorpora a los cuatro archivos fuente solicitados.
No se han usado credenciales, bases de datos, publicación ni herramientas de
despliegue, ni modificado fuentes compartidas o dependencias.
