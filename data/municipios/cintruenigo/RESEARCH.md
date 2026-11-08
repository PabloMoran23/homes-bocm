# Cintruénigo — Navarra — INE 31072

Verificación en vivo: 2026-11-08. Implementado un único adaptador municipal.

## Descubrimiento y procedencia

La página oficial de [Urbanismo municipal](https://www.cintruenigo.com/cintruenigo/urbanismo/)
enlaza «Planeamiento Urbanístico / ACCEDER» al
[SIUN del Gobierno de Navarra](https://administracionelectronica.navarra.es/SIUN_Consulta/Index.html#/instrumentos).
El otro acceso es «Tramitación-Solicitudes», no un registro de licencias concedidas.
No se extraen formularios, contratación ni noticias como proyectos.

La aplicación Angular pública revela los endpoints en
`Angular/services/siunConsultaPublicaDataFactory.es5.min.js`, los filtros en
`Angular/services/utilsService.es5.min.js` y la paginación en
`Angular/controllers/instrumentosController.es5.min.js`, todos bajo
`https://administracionelectronica.navarra.es/SIUN_Consulta/`.
`api/Municipios` identifica CINTRUÉNIGO como `idMunicipio: 72`.
Cada detalle confirma `idProvincia: 31`, `idMunicipio: 72` y el nombre municipal.
Esto corresponde al INE 31072, no al código municipal 72 aislado.

## Inventario y recorrido

Se consulta mediante POST `api/Instrumentos/PG/default/false/{offset}/25`:

```json
{"municipios":[72],"entidadesPoblacion":[],"tiposInstrumento":[],"aprobadoPosterior":false}
```

`aprobadoPosterior: false` elimina la restricción a instrumentos posteriores al
plan general vigente. Se recorren las siete páginas, offsets 0, 25, 50, 75, 100,
125 y 150: **167 instrumentos**, sin límite silencioso. Se valida el total declarado;
una página vacía prematura, IDs repetidos o un total cambiante provocan error.
Después se consulta `api/Instrumentos/{id}` por cada instrumento. El fichero final
se reemplaza atómicamente sólo tras completar todos los detalles.

Se conserva un registro por ID oficial SIUN, con todos sus documentos agrupados:
**364 enlaces documentales y 347 trámites**. Incluye planes, modificaciones,
estudios de detalle, reparcelaciones y urbanización. Ejemplo: instrumento 3451,
PLAN MUNICIPAL, con memoria, normativa, ordenanzas y planos vinculados. Se ha
capturado y comprobado HTTP 200 / application/pdf de su Memoria Justificativa.
No se generan proyectos separados para cada PDF o trámite.

## Semántica y cobertura parcial

El inventario incluye histórico: las fechas `fechaDefinitiva` abarcan 1977–2026.
165 instrumentos tienen `vigencia: true` y dos `false`; se retienen los estados
originales y no se presume vigencia jurídica a partir de la mera presencia.
Los 113 instrumentos sin documentos enlazados se conservan como registros del
inventario, con `documentos: []`. No se inventan enlaces ausentes.

La plantilla pública `Angular/views/instrumentos/view.html` identifica `tramite.fecha`
como **Fecha BON** y `tramite.fechaResolucion` como **Fecha de resolución**. Se
exportan por separado dentro de cada trámite, con fase, resolución y número BON.
`fechaDefinitiva` se retiene como `fecha_definitiva_segun_siun`: no se transforma
en fecha de acuerdo, aprobación verificada o concesión. Por ejemplo, el plan
3451 muestra 1998-12-28 en ese campo y en Fecha BON, sin fecha de resolución.
`numExpediente`, cuando existe, se conserva como `numero_expediente_segun_siun`;
el ID SIUN no se hace pasar por un número de expediente original.

No se cubre la pestaña OT, que incluye ordenación territorial supramunicipal,
ni todo el catálogo de obras físicas municipales, ni licencias. La actualidad y
exhaustividad registral dependen de SIUN. Actualizar realiza una extracción completa;
no se afirma disponer de historial incremental de cambios o bajas.

## Geometría y clasificación

Se conservan los enlaces originales de documentos escritos y de visores gráficos
georreferenciados, incluido su tipo SIUN y escala cuando existen. No se ha extraído
una geometría vectorial asociada al instrumento ni se han vectorizado planos.
`geometry_status: unavailable`; sin coordenadas, centroide o jitter inventados.
No se han verificado individualmente todos los enlaces documentales.

La política compartida de entidades permanece intacta: clasifica los 167 registros
como `pendiente / insufficient_identity_evidence` y reporta `adapter_incident`
porque no reconoce la identidad SIUN y muchos carecen de número de expediente.
Esta limitación se conserva en la evidencia; no invalida su procedencia registral,
pero todos llevan `publication_ready: false` y requieren revisión antes de publicar.

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `python -m unittest municipio.test_cintruenigo -v`: siete pruebas del parser,
  agrupación documental, fechas, identidad municipal, paginación completa y sus
  errores, escritura y licencias deshabilitadas.
- Extracción real mediante `load_manifest('cintruenigo')`, `load_portal_adapter` y
  `backfill_proyectos(Path('evidence/proyectos.jsonl'))`. El parámetro opcional
  `evidence_dir` captura las respuestas reales sin alterar el manifest.
- `evidence/validation.json`: recuentos, URLs, filtros, resultado del adaptador y
  limitaciones; `evidence/captures/`: siete páginas y 167 detalles JSON.
  También se guardan la página municipal, plantilla y scripts públicos, un PDF
  de muestra y el resultado de pruebas. Estas evidencias son locales, no fuentes
  para ejecutar el scraper y no se deben incorporar al commit.

`schedule.enabled: false`, `licencias.enabled: false`,
`geocode.jitter_missing: false`. Sin modificaciones compartidas ni dependencias.
