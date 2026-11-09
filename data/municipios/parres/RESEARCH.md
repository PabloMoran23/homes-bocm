# Parres — investigación y alcance

Verificado el 9 de noviembre de 2026. Municipio: Parres, provincia de Asturias,
INE **33045**. Se revisaron `municipio/manifest.py`, el contrato
`municipio/adapters/portal.py` y los ejemplos Manlleu y Chipiona antes de implementar.

## Fuentes oficiales descubiertas

- [Normativa urbanística](https://www.ayto-parres.es/normativa-urbanistica):
  inventario municipal utilizado. Bajo «PLANEAMIENTO DE PARRES» reúne documentos
  de instrumentos identificados por encabezados, no simples noticias.
- [Urbanismo](https://www.ayto-parres.es/urbanismo): confirma las normas
  subsidiarias y enlaza el registro regional. La mención a BOPA 25/05/2002
  corresponde a una publicación, no acredita una fecha de acuerdo.
- [Mapa web](https://www.ayto-parres.es/mapa-web): permite descubrir las páginas
  municipales de proyectos y obras concluidas.
- [Proyectos](https://www.ayto-parres.es/proyectos): descripción histórica de
  actuaciones de talleres de empleo; no se incorpora a este inventario.
- [Obras concluidas](https://www.ayto-parres.es/obras-concluidas): rehabilitaciones
  históricas de fuentes, lavaderos y escuelas. Consultada, pero fuera del alcance
  elegido; no representa una cartera actual exhaustiva.
- El inventario enlaza el [registro autonómico](https://www54.asturias.es/rpgur/action/publico/welcome)
  y el [visor regional](https://sigvisor.asturias.es/visorurbanismo/).
  No se extraen sus bases ni se afirma cobertura de ellas.

## Registros extraídos y agrupación

La extracción en vivo produjo **11 instrumentos y 151 enlaces distintos**:

| Instrumento / sección municipal | Documentos |
| --- | ---: |
| NSP de los Suelos Urbanos y Aptos para Urbanizar | 18 |
| NSP Suelo No Urbanizable | 36 |
| Plan Parcial Caxidi | 2 |
| Plan Parcial SAU-2 Santianes de Terrón | 13 |
| Plan Parcial SAU-3 Santianes de Terrón II | 23 |
| Plan Parcial Parque Empresarial de Prestín | 24 |
| PERI del Puente Romano | 9 |
| Estudio Detalle parcelas 1, 2 y 3, Polígono Residencial de Castañera | 7 |
| Estudio Detalle Prestín, suelo urbano residencial | 14 |
| Estudio Implantación renovación de abastecimiento de Bodes | 3 |
| CAU, catálogo urbanístico | 2 |

Una fila representa una sección/instrumento del inventario. Memorias, planos,
ordenanzas, consultas, anexos y modificaciones documentales de esa sección se
conservan juntos en `documentos`. El catálogo y las dos secciones NSP mantienen
la separación que hace la fuente; no se desglosan sus láminas como proyectos.
Los identificadores utilizan la carpeta documental municipal y no dependen del
orden, numeración del encabezado ni del parámetro de actualización `t`.

Los enlaces originales completos se mantienen junto a sus rótulos. Los duplicados
se agrupan por URL conservando todos los rótulos no vacíos. La fuente enlaza el
mismo PDF para dos fichas de sectores de las NSP y para los planos 08 y 09 de
Prestín; no se inventan documentos de sustitución. Hay enlaces repetidos sin texto
junto a otras anclas: tampoco producen nuevos registros.

## Semántica y límites

La página es un inventario consultable actualmente, con documentación histórica;
no acredita que todos los instrumentos estén vigentes, aprobados o ejecutados.
No se convierte presencia en el inventario en fase administrativa.
`fecha`, `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` quedan nulas.
Los parámetros `t` no son fechas de aprobación ni publicación. Tampoco se toma
una fecha de edición de documento como fecha del instrumento.

Los PDF pueden contener fechas y distintas fases: el documento inicial de Bodes,
por ejemplo, tiene una diligencia de aprobación inicial, mientras la sección
contiene también documentación definitiva y BOPA. El adaptador extrae el índice,
no interpreta ni consolida el ciclo administrativo dentro de los PDF. Esas fechas
no se atribuyen globalmente al instrumento. No se han contrastado todos los PDF.

Se excluyen explícitamente la evaluación ambiental estratégica independiente
(no se adscribe a Bodes únicamente por proximidad visual), las declaraciones IPCA
de patrimonio y el plan de emergencia frente a inundaciones. No son instrumentos
urbanísticos adicionales dentro de este alcance. Las solicitudes de licencia,
licitaciones y noticias no se usan como licencias concedidas ni como proyectos.
No se ha verificado un registro público de licencias concedidas.

No hay geometría verificada: coordenadas y geometría nulas,
`publication_ready=false`, `geocode.jitter_missing=false`. Licencias y ejecución
programada están desactivadas.

El inventario inspeccionado contiene todas estas secciones en una sola respuesta
HTML, sin paginación. No se aplican límites de filas ni de documentos. Si aparecen
controles de paginación reconocidos o enlaces `rel=next`, se falla explícitamente;
no se entrega una primera página como extracción completa. Encabezados o tipos
inesperados, secciones sin documentos, carpetas ambiguas, destinos documentales
ajenos y redirecciones inesperadas también producen error.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_parres -v` — **8 pruebas correctas**.
Incluyen agrupación, rótulos duplicados, exclusiones, estabilidad del identificador,
fechas/geometría ausentes, errores de estructura y paginación, configuración,
actualización de instantánea, licencias desactivadas y redirecciones.

Extracción real ejecutada llamando:

```python
from pathlib import Path
from municipio.adapters.parres import ParresAyuntamientoAdapter
adapter = ParresAyuntamientoAdapter(config={'capture_dir': 'evidence'})
result = adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))
```

Evidencia local (no destinada a commit): `evidence/proyectos.jsonl`,
`evidence/validation.json`, cinco capturas HTML y tres PDF de muestra
(NSP urbana, ordenanzas de Caxidi y estudio inicial de Bodes). Los tres PDF
respondieron HTTP 200 y tienen cabecera PDF; los hashes y URL exactos se guardan
en la validación. Caxidi no ofrece texto en su primera página mediante
`pdftotext`; no se hace OCR ni se infiere contenido ausente. También se conserva
texto de la primera página de Bodes como comprobación documental.
