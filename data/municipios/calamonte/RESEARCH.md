# Calamonte — INE 06025, Badajoz, Extremadura

Verificación y extracción real: 2026-11-09. Adaptador exclusivo de este municipio.

## Inventario oficial actual

- Oficina Técnica: https://calamonte.org/servicios/oficina-tecnica/
- Representación pública WordPress de esa misma página: https://calamonte.org/wp-json/wp/v2/pages?slug=oficina-tecnica
- Acuerdo del Plan General: https://doe.juntaex.es/otrosFormatos/html.php?anio=2024&doe=510o&xml=2024AC0022

La página municipal contiene inventarios de planeamiento y, después, modelos para trámites urbanísticos. Su API devuelve una página publicada (id 426), `X-WP-Total: 1` y `X-WP-TotalPages: 1`. Se exige esa cardinalidad y la URL/slug exactos; no se descartan páginas adicionales. El parser comprueba que no haya paginación HTML. La respuesta completa se conserva en evidencia. Una solicitud inicial sin User-Agent recibió 403; las consultas posteriores con User-Agent explícito respondieron 200. No se necesita sesión ni credenciales.

## Cinco instrumentos, 18 enlaces documentales

1. **Plan General Municipal**: enlace municipal al documento de Google Drive y acuerdo del DOE. El DOE establece **aprobación definitiva parcial**, acuerdo de **2023-05-25**, publicación de **2024-03-13**. Queda en suspenso la ordenación de UA-9 de las NNSS y terrenos colindantes incluidos en UA-1. No se verifica la subsanación posterior, caducidad ni vigencia consolidada. No se usa la fecha de modificación del CMS como acuerdo.
2. **Normas Subsidiarias, documentación histórica**: cinco enlaces (Término Municipal, Calificación NU, Alineaciones Catastral, UA-11 y Ordenanzas 2015_06_23). Se agrupan bajo su encabezamiento original, separados del nuevo PGM. El nombre del archivo no es una fecha de aprobación. Sin afirmación de vigencia ni fechas deducidas.
3. **Plan Parcial Dehesa del Rey**: ocho planos y sus ordenanzas, agrupados en un instrumento. Sin fechas o fase deducidas.
4. **Modificación del Plan Parcial de los Sectores SUP-I1 y SUP-I2**: el PDF identifica la resolución 2010060841, acuerdo **2009-06-25**, publicación DOE **2010-04-15**.
5. **Modificación n.º 1/2014 de NNSS y Plan Parcial Industrial Dehesa del Rey**: el PDF identifica la resolución 2015060595, acuerdo **2015-01-29**, publicación DOE **2015-03-20**. Un solo instrumento aunque modifica dos normas.

### Discrepancia comprobada en los enlaces municipales

Los títulos de los dos enlaces de modificaciones están intercambiados:

- https://calamonte.org/wp-content/uploads/2015/05/Publicaci%C3%B3n-DOE-AD-Modif_PP.pdf está etiquetado como NNSS 1/2014, pero contiene la modificación del PP SUP-I1/SUP-I2 de 2009, publicada en 2010.
- https://calamonte.org/wp-content/uploads/2015/05/AD-DOE-2015_03_20.pdf está etiquetado como PP SUP-I1/SUP-I2, pero contiene NNSS 1/2014 y PP Industrial, resolución de 2015.

Ambos documentos se descargaron completos (HTTP 200, application/pdf, firma `%PDF-`). El adaptador identifica cada instrumento por el texto del PDF, conserva su URL y `titulo_enlace`, registra `titulo_documento`, `source_label_mismatch` y procedencia de fechas. No reasigna silenciosamente una fecha al documento equivocado. Utiliza `/usr/bin/pdftotext`, ya disponible; no se ha instalado software ni cambiado dependencias. La falta de esa utilidad o una identidad documental desconocida provoca error. El DOE del PGM se consulta también en cada extracción para verificar el alcance parcial.

## Exclusiones y límites

Cobertura parcial municipal: inventario íntegro actualmente publicado en esta página, no un histórico completo de expedientes, proyectos de obra o licencias. No se consulta exhaustivamente el tablón electrónico ni toda la contratación pública. No se convierten formularios, ordenanzas de tramitación, anuncios de contratación o noticias generales en proyectos o licencias concedidas. Licencias desactivadas por falta de registro público verificado de concesiones.

Se conservan los enlaces documentales originales, incluidos los antiguos HTTP. Salvo las dos modificaciones y el acuerdo DOE, no se ha descargado ni comprobado individualmente la accesibilidad o contenido de todos los planos, ordenanzas o el archivo de Drive. Su pertenencia procede de los encabezamientos del inventario; no se afirma que sean versiones consolidadas. Los documentos históricos y modificaciones pueden estar superados. No hay geometrías de proyecto verificadas: lat/lon/geometry nulos, `publication_ready: false`, sin coordenadas municipales de sustitución. `schedule.enabled: false`, `geocode.jitter_missing: false`.

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `python -m unittest municipio.test_calamonte -v`: seis pruebas offline correctas. Agrupación documental, aislamiento de formularios y NNSS históricas, fechas y alcance parcial, identidad de PDF frente a enlaces erróneos, IDs estables, rechazo de cambios/paginación y restricciones de manifest.
- Ejecución real de `CalamonteAyuntamientoAdapter.backfill_proyectos` (también mediante el cargador del manifest): cinco registros, sin publicar, geocodificar ni acceder a bases de datos.
- Evidencia local no destinada a commit: `evidence/proyectos.jsonl`, `evidence/validation.json`, capturas API/DOE/PDF, textos PDF y salida de pruebas.

Las pruebas usan fragmentos reducidos para ejercitar el parser; la extracción real siempre descarga las fuentes y no emplea esos fragmentos ni registros precargados.
