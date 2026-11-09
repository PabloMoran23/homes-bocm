# San Cibrao das Viñas — INE 32075, Ourense

Verificado con peticiones HTTP reales el 2026-11-09. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento y alcance

La portada oficial https://sancibrao.es/ enlaza la sede electrónica y Vortal.
La sección municipal [Obras e urbanismo](https://sancibrao.es/concello/solicitudes-e-comunicacions/obras-e-urbanismo/)
contiene solicitudes/comunicaciones (obras, ocupación, segregación, etc.). Son
formularios, no concesiones. No se extraen como licencias ni proyectos.
La sede y Vortal no se afirman aquí como inventarios de licencias verificadas.

Se descubrió mediante búsqueda pública el registro autonómico oficial de
ordenación del territorio y planeamiento urbanístico (ROTPG), servido por la Xunta:

- https://territorioeurbanismo.xunta.gal/es/territorio-y-urbanismo/registro-de-ordenacion-del-territorio-y-urbanismo/buscador
- [Filtro Ourense / San Cibrao das Viñas, página 1](https://territorioeurbanismo.xunta.gal/es/territorio-y-urbanismo/registro-de-ordenacion-del-territorio-y-urbanismo/buscador?provincia=32&concello=677)
- [Página 2](https://territorioeurbanismo.xunta.gal/es/territorio-y-urbanismo/registro-de-ordenacion-del-territorio-y-urbanismo/buscador?provincia=32&concello=677&page=1)

El formulario identifica explícitamente `concello=677` como San Cibrao das Viñas
con provincia 32. Ese identificador interno no es el INE: el municipio es **32075**.
El adaptador comprueba los filtros seleccionados, el nombre y la provincia de las
filas; no depende de que todos los títulos repitan el topónimo.
El inventario actual contiene **15 instrumentos en 2 páginas (10 + 5)**, con
inscripciones que la fuente sitúa entre 2018 y 2026. Se recorren todos los enlaces
del paginador, preservando el filtro y rechazando páginas repetidas o saltos.
No existe un límite de registros que trunque los resultados.

Cobertura parcial: fichas de planeamiento inscritas y devueltas por ese filtro.
Incluye estudios de detalle, planes especiales, modificaciones del PXOM y de plan
parcial y modificación de proyecto sectorial. Por ejemplo, ED na rúa Aldea de
Abaixo, A Carballeira (`ROTPG/P/2/2026`), MP/PXOM nº6 (`ROTPG/P/59/2024`) y MP/PP
SUR-I2, SUR-I3 e SUR-I4 (`ROTPG/P/38/2024`). Son instrumentos identificados mediante
referencias oficiales, no anuncios de contratación ni noticias genéricas.
No se afirma que este registro constituya todo el histórico municipal, ni que cada
instrumento siga vigente, ni se obtiene el PXOM consolidado. El inventario ambiental
de la Xunta https://medioambiente.xunta.gal/en-curso también apareció en búsqueda,
pero no se mezcla en esta extracción para evitar duplicar trámites del mismo plan.

## Documentos, fechas y geometría

Una referencia registral es una entidad. Todos los enlaces de su celda Documento
se agrupan en `documentos`; filas repetidas de la misma referencia se fusionan y
conservan las URLs de procedencia. Metadatos contradictorios provocan error.
Actualmente son 15 enlaces a archivos ZIP, uno por instrumento, con los enlaces
originales publicados por la Xunta. No se descompone cada plano/PDF en un proyecto.

Se comprobó el primer enlace publicado de `www.planeamentourbanistico.xunta.es`:
redirige a `http://siotuga.xunta.gal/siotuga/rexistro/index.php?...` y devuelve HTML
con CAPTCHA antes de la descarga. La captura local `document-landing.html` lo
acredita; no se ha descargado ni interpretado el archivo ZIP, ni evitado el CAPTCHA.
La variante HTTPS del host antiguo dio error TLS; no se deshabilita su validación.
Los metadatos de los proyectos proceden de la tabla pública, no del contenido ZIP.

Se conservan por separado `fecha_inscripcion`, `fecha_aprob`,
`fecha_publicacion_doga` y `fecha_publicacion_bop`, junto con los textos originales.
`fecha`, `fecha_publicacion` genérica y `fecha_acuerdo` son nulas. La fecha de
aprobación es la expresamente etiquetada así en el registro: no se deduce una fase
inicial/definitiva, fecha de acuerdo del Pleno o concesión de licencia.

Dos fichas presentan incoherencias originales:

- `ROTPG/P/38/2024`: BOP 26/06/2023, anterior a aprobación 30/04/2024.
- `RPG/00002/2019`: inscripción 30/01/2018, aprobación 29/11/2019,
  DOGA 14/12/2018 y BOP 06/02/2019; el nombre del ZIP contiene otra fecha.

Se mantienen esos valores y se añaden `advertencias_fechas`; no se corrigen con
el nombre del fichero ni con suposiciones. `tipo_asiento_original` conserva
«Modificación», «Instrumentos» o vacío, sin usarlo como fase.

`geometry_status: unavailable`. Las fichas no contienen geometría ni coordenadas.
La portada municipal enlaza el callejero
https://callejero.gestionpatrimonio.es/inicio.php?municipio=sancibrao ; no se ha
verificado allí una geometría enlazable por referencia ROTPG. No se geocodifican
centroides ni se vectorizan archivos. `publication_ready: false` en cada ficha.

## Implementación y comprobación

Solo se añaden el manifiesto, esta investigación, el adaptador y sus pruebas.
Se respeta `AyuntamientoAdapter` y se carga por el registro existente, sin cambios
compartidos ni dependencias nuevas. Las actualizaciones vuelven a leer la instantánea
completa: no aplican un corte por fecha que pierda correcciones de fichas antiguas.
Los errores HTTP, filtros, esquema, identidad, documentos o paginación se propagan;
la salida solo se reemplaza cuando termina la extracción completa.

Comando de pruebas:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_san_cibrao_das_vinas -v
```

**6 pruebas pasan**: identidad/semántica y agrupación de documentos; conservación
de inconsistencias cronológicas; rechazo de formularios, referencias ajenas y
filtros/esquema cambiados; alcance del paginador; recorrido de varias páginas y
rechazo de repetición sin sobrescribir la salida previa; ajustes del manifiesto.

La ejecución real usa `load_manifest('san-cibrao-das-vinas')`,
`manifest.portal.config['capture_dir'] = 'evidence'`,
`load_portal_adapter(manifest).backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
Resultado: **15 registros**, **2 páginas**, **15 enlaces documentales**, 0 entidades
sin identificar con la política compartida (`entity_policy.status=ok`).
Evidencia local no comprometida: `evidence/proyectos.jsonl`,
`evidence/validation.json`, capturas `registro-live-0.html` y `registro-live-1.html`,
capturas de descubrimiento y resultado de pruebas.

Licencias deshabilitadas (métodos devuelven salida vacía y estado `disabled`),
`schedule.enabled: false`, `geocode.jitter_missing: false`. Sin publicación,
conexión a bases de datos ni cambios de producción.
