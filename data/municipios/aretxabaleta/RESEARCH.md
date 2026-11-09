# Aretxabaleta — INE 20013, Gipuzkoa, País Vasco

Revisión y extracción en vivo: 2026-11-09. Adaptador único:
`municipio.adapters.aretxabaleta:AretxabaletaAyuntamientoAdapter`.

## Fuentes oficiales y alcance

Inventario de partida, no una noticia fijada como semilla:
https://www.aretxabaleta.eus/es/departamentos/participacion/normas-en-proceso-de-creacion

La página municipal publica dos secciones, «Normas en tramitación» y «Normas
tramitadas», con enlaces a fichas individuales. Se recorre íntegramente la página
y todas las fichas de las familias seleccionadas: estudios de detalle,
modificaciones puntuales, PGOU, movilidad y convenios urbanísticos ligados a
urbanización o infraestructura física. Son instrumentos concretos, no licencias
concedidas. Se excluyen ordenanzas generales, normativa de servicios, formularios,
registro electrónico para alegaciones, noticias y anuncios de contratación.

Resultado observado: **11 instrumentos**, 7 en la sección en tramitación y 4 en
tramitadas, con **68 enlaces documentales únicos dentro de cada instrumento**.
Los documentos de sucesivas etapas se agrupan; no son proyectos adicionales:

- Estudio de detalle para ampliar Iturrigorri: ficha narrativa, sin adjunto.
- 12ª modificación NNSS, ámbito 1-b: 3 enlaces.
- Plan de movilidad 2026-2030: 5 enlaces.
- 11ª modificación NNSS, zona industrial 33: 4 enlaces.
- Convenio parcela D del área A-4a, Ortubos/HUHEZI: 2 enlaces.
- Estudio de detalle Mitarte 12, área 13B: 4 enlaces.
- PGOU: 3 enlaces.
- 10ª modificación NNSS, instalaciones de combustible: 10 enlaces.
- Estudio de detalle área 16: 22 enlaces.
- 9ª modificación NNSS, área 13-b: 10 enlaces.
- Convenio ascensor de Iturrizar: 5 enlaces.

Los títulos se toman del contenido visible. La URL del plan de movilidad termina
en `2026-2033` pero el título y contenido dicen 2026-2030. La URL del convenio de
Ortubos/HUHEZI reutiliza un slug de Iturrizar con sufijo `-1`: no se interpreta el
slug como descripción ni se fusionan ambos convenios.

Otra fuente oficial revisada:
https://www.aretxabaleta.eus/es/departamentos/urbanismo
Publica el corpus de Normas Subsidiarias (memoria, catálogo, normas y planos).
Queda fuera de esta extracción del inventario de participación: la cobertura no
es un censo completo de planeamiento vigente ni de obras municipales. Tampoco
se recorre un histórico de noticias para completar obras.

## Fechas, procedencia y límites

Se conservan `descripcion`, `titulo_inventario`, `situacion_inventario` y el URL
canónico de cada ficha. Los documentos tienen título, URL oficial y `source_url`
de la ficha que los enlaza. Se aceptan PDFs municipales/BOG y resolutores
`/PortalV/r/0/13/` de las sedes oficiales de Gipuzkoa. Los destinos documentales
se conservan como enlaces publicados; no se descargan ni se garantiza su
accesibilidad. Los recuentos describen enlaces, no PDFs validados.

Las fechas completas se guardan en `eventos` con `tipo_fecha`, `fechas`, texto de
la frase, contexto y URL. Se distingue acuerdo, publicación y firma. Una frase
con varias fechas completas ambiguas se conserva como mención. Los campos
superiores `fecha`, `fecha_aprob`, `fecha_acuerdo`, `fecha_publicacion` y `fase`
quedan nulos: una ficha reúne distintos actos y no hay una única fecha/fase que
los represente fielmente. No se usa una fecha de acuerdo de inicio/participación
como aprobación definitiva, ni una fecha de captura como publicación.

Ejemplo: la 10ª modificación registra acuerdo definitivo de 18/12/2024 y
publicación BOG de 13/01/2025 por separado. La propia fuente también contiene
una discrepancia entre el inicio narrado de 17/01/2024 y el campo «Fecha del
acuerdo: 17/04/2024»; se retienen ambos con su contexto, sin corregirlos por
suposición. El convenio de Iturrizar mezcla encabezado de aprobación definitiva
y narrativa de aprobación inicial: tampoco se resuelve esa ambigüedad inventando
un acto. Fechas como «31 de mayo», sin año explícito, permanecen sólo en texto.

No hay paginación activa observada. Ante enlaces o contenedores de paginación,
el adaptador falla explícitamente, sin truncar a la primera página. También
rechaza inventarios vacíos/incompletos, errores HTTP, redirecciones inesperadas,
fichas sin contenido sustantivo o cambios de tipo de instrumento. Se escribe la
instantánea sólo tras completar todas las fichas; un fallo conserva la anterior.
La actualización vuelve a recorrer el inventario completo, sin límite de filas.

`geometry_status: unavailable`: no se ha verificado geometría vectorial vinculada
a estos instrumentos. Se conservan los planos como documentos; no se vectorizan
PDFs ni se asignan coordenadas o centroides. `publication_ready: false`.

La política compartida de entidades clasifica los 11 registros como `pendiente`
(`insufficient_identity_evidence`) y señala `unknown_entity_spike`: las fichas
no exponen número administrativo de expediente. Los identificadores estables
son hashes del URL de la ficha, no números de expediente inventados. Esa
clasificación se conserva en la evidencia y requiere revisión independiente;
no invalida la existencia documental de los instrumentos ni habilita publicación.

## Validación reproducible

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_aretxabaleta -v`: **8 pruebas**, incluyendo
filtrado, deduplicación, agrupación documental, fechas completas/publicación vs
acuerdo en un mismo párrafo, rechazo de paginación, narrativa sin adjuntos,
recorrido de todas las fichas, conservación de instantánea ante fallos y manifest.

Extracción real mediante `load_manifest('aretxabaleta')`,
`load_portal_adapter(manifest).backfill_proyectos(Path('evidence/proyectos.jsonl'))`,
con `manifest.portal.config['capture_dir']='evidence/captures'`.
`evidence/validation.json` conserva recuento, URLs, limitaciones, clasificación,
fecha UTC y hashes SHA256 de las 12 capturas HTML (inventario y 11 fichas).
Se guarda además la página de Urbanismo en `evidence/urbanismo.html`.
Las evidencias son locales, no archivos fuente a incorporar.

Licencias deshabilitadas: los métodos devuelven cero filas con estado `disabled`.
`schedule.enabled=false`, `geocode.jitter_missing=false`. Sin cambios compartidos,
dependencias, base de datos, despliegue ni publicación.
