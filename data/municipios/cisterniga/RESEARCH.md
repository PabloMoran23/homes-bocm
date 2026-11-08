# Cistérniga — Valladolid — INE 47052

Investigación y extracción real: 7 de noviembre de 2026. Nombre municipal del encargo: Cistérniga; el ayuntamiento se presenta como La Cistérniga. No confundir el código INE 47052 con el CIF municipal.

## Fuentes oficiales y alcance

- [Urbanismo documental](https://www.lacisterniga.es/normativa-urbanistica-pt?page=0): inventario Drupal municipal efectivamente utilizado. Se siguieron todos los enlaces «Siguiente página»: `?page=0`, `?page=1`, `?page=2`. Las tres páginas exponen 21 fichas (10, 10, 1), siete seleccionadas. La última no tiene siguiente página. No se fija un límite silencioso; se rechazan ciclos, secuencias inesperadas o enlaces a páginas posteriores sin enlace siguiente.
- [Urbanismo](https://www.lacisterniga.es/urbanismo): consultado, pero la página de taxonomía no ofreció inventario útil en su contenido principal.
- [Área de Urbanismo](https://www.lacisterniga.es/areas/urbanismo): localizada en búsqueda oficial; noticias sobre obras. No se incorpora ese archivo de noticias a la cobertura del adaptador.

La cobertura es el inventario documental publicado actualmente, no todo el planeamiento vigente ni un histórico exhaustivo de obras. No se extraen actas, sede electrónica, contratación, bases de datos ni portales privados. La autorización minera en información pública se excluye del alcance: la ficha anuncia una solicitud, no una licencia concedida. También se excluyen el procedimiento de ruina y los trece formularios/instrucciones de trámites. Una ficha elegible debe tener documentos adjuntos reales; su desaparición o cambios de marcado provocan error antes de escribir el resultado.

## Resultado y agrupación

Cinco registros, nueve enlaces documentales, siete fichas originales:

1. [Proyecto de Actuación del Plan Parcial modificado Sector 10, expediente 932/2024](https://www.lacisterniga.es/doc/urbanismo/aprobacion-inicial-del-proyecto-de-actuacion-por-el-sistema-de-compensacion-del-plan): anuncio de aprobación inicial como documentación del instrumento, no contratación ni licencia.
2. [Proyecto de normalización de fincas, finca registral 775](https://www.lacisterniga.es/doc/urbanismo/proyecto-normalizacion-de-fincas-relativo-la-finca-registral-775): certificación adjunta, sin extraer una fecha jurídica del nombre del archivo.
3. [Adecuación de parques Plaza Junquera y avenida Diego Velázquez](https://www.lacisterniga.es/doc/urbanismo/proyecto-urbanistico-adecuacion-parque-plaza-junquera-y-parque-avda-velazquez): proyecto físico con documento técnico adjunto.
4. Modificación Puntual Nº1 del Plan Parcial Sector 10: [parte 1](https://www.lacisterniga.es/doc/urbanismo/documentos-modificacion-puntual-no1-plan-parcial-sector-10-parte-1) y [parte 2](https://www.lacisterniga.es/doc/urbanismo/documentos-modificacion-puntual-no1-plan-parcial-sector-10-parte-2) agrupadas, cuatro documentos. Se mantiene separado del proyecto de actuación del mismo sector.
5. Plan Parcial Sector 13 del SUD del PGOU: [Anejo IV](https://www.lacisterniga.es/doc/urbanismo/aprobacion-definitiva-plan-parcial-sector-13-del-sud-del-pgou-de-la-cisterniga) y [Anejo V](https://www.lacisterniga.es/doc/urbanismo/aprobacion-definitiva-plan-parcial-sector-13-del-sud-del-pgou-de-la-cisterniga-0) agrupados. El título municipal dice aprobación definitiva; estos dos anexos no constituyen el expediente completo ni acreditan por sí solos su vigencia actual.

La agrupación normaliza títulos y elimina únicamente el prefijo «Documentos», sufijos de parte y puntuación; conserva cada ficha, descripción y rango temporal, y los adjuntos con su ficha de procedencia. No fusiona actuaciones distintas por compartir sector. Los identificadores derivan del título normalizado; un cambio sustancial del título puede cambiar el identificador.

## Semántica y límites

`field_date_range` no etiqueta explícitamente fecha de acuerdo, aprobación o publicación. Se conserva como `source_date_ranges` y `source_date_values` dentro de cada ficha, sin interpretar ni siquiera su primera fecha como publicación. `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` quedan nulas. Las fechas en nombres de archivos tampoco se convierten en fechas jurídicas. No se infiere fase actual, ejecución, licencia concedida o vigencia a partir de un título. Los encabezados y descripciones son afirmaciones de la fuente.

Sin coordenadas ni geometrías verificadas; valores nulos, `geometry_status: unavailable`, `publication_ready: false`. `schedule.enabled`, `geocode.jitter_missing` y `licencias.enabled` son falsos. Los métodos de licencias rechazan su ejecución. Las actualizaciones regeneran la instantánea completa, sin almacenar historial de bajas ni usar `state_path` como cursor.

## Validación reproducible

Runtime preinstalado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_cisterniga -v
```

Cinco pruebas correctas: selección/exclusión, agrupación y aislamiento documental, preservación de rangos sin fechas inventadas, rechazo de fuentes vacías/cambiadas, paginación completa, fallo de red sin fichero parcial y contrato del manifest. Fixtures sintéticas locales; no dependen de las evidencias ni de acceso a red.

Ejecución real: `CisternigaAyuntamientoAdapter('cisterniga', config={'capture_dir': 'evidence/captures'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`. Resultado: 5 registros, 3 páginas, 21 entradas, 7 fichas y 9 adjuntos. Los nueve adjuntos respondieron HTTP 200, `application/pdf` y firma `%PDF-`; se guardaron solamente sus primeros 1024 bytes, sin descargar ni interpretar todo su contenido.

Evidencias locales no destinadas a commit: `evidence/proyectos.jsonl`, `evidence/validation.json` (recuento, URLs, limitaciones, pruebas y comprobaciones documentales), `evidence/document-checks.json`, HTML de descubrimiento, las diez capturas de la ejecución del adaptador en `evidence/captures/` y prefijos PDF. No se han ejecutado publicación, geocodificación, sincronización ni despliegue. Solo se añaden los cuatro archivos fuente autorizados.
