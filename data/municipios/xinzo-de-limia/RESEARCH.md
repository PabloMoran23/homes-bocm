# Xinzo de Limia — INE 32032, Ourense

Verificado el 2026-11-07 con extracción HTTP real. Identidad corroborada en la
[Axencia de Protección da Legalidade Urbanística](https://axenciaurbanistica.xunta.gal/gl/concellos/xinzo-de-limia)
(código 32032, provincia Ourense; captura local `evidence/identity.html`).

## Descubrimiento y fuente utilizada

La búsqueda de urbanismo/PXOM y obras municipales permitió descubrir la web
municipal https://www.xinzodelimia.gal/, su categoría
https://www.xinzodelimia.gal/obras-infraestruturas/ y la sede
https://xinzodelimia.sedelectronica.gal/. La web municipal ofrece noticias de obras,
actas y publicidad de subvenciones; la sede distingue trámites de anuncios.
Las solicitudes y formularios no son licencias concedidas. No se extraen esos
recursos ni anuncios de contratación como si fueran proyectos. La web municipal
con y sin `www` no fue accesible desde este runtime (Network is unreachable);
el buscador web sí mostraba contenido indexado. Ese contenido indexado no se usa
para producir registros ni para deducir aprobaciones.

Fuente reproducible utilizada: [Buscador del Registro de Ordenación del Territorio
y Planeamiento Urbanístico de la Xunta](https://territorioeurbanismo.xunta.gal/es/territorio-y-urbanismo/registro-de-ordenacion-del-territorio-y-urbanismo/buscador?provincia=32&concello=696).
La consulta inicial sin filtros permitió inspeccionar el formulario real, las
columnas y el paginador (`evidence/probe-3.html`). El selector identifica
`concello=696` como Xinzo de Limia, asociado a `provincia=32` Ourense. **696 es un
identificador interno de la Xunta, no el INE**. El adaptador comprueba los valores
y etiquetas seleccionados, la provincia y el municipio de cada fila y el esquema
completo de la tabla antes de aceptar datos. Los registros mantienen procedencia
`source=xunta`, no atribuyen su publicación al ayuntamiento. El manifiesto usa el
valor de contrato `proyectos.source=ayuntamiento` para cargar el adaptador local.

## Resultado y semántica

Extracción real: **6 instrumentos** registrados, **5 enlaces ZIP** oficiales:

| Registro | Instrumento | Aprobación indicada por el registro |
| --- | --- | --- |
| ROTPG/P/30/2023 | Estudo de Detalle Guntimil | 2022-11-03 |
| ROTPG/P/85/2022 | Estudo de Detalle Ganade | 2021-07-27 |
| RPG/00065/2019 | Estudo de Detalle, modificación de alineaciones en Baronzás | 2019-04-29 |
| RPG/00007/2018 | Estudo de Detalle Baronzás | 2017-12-04 |
| RPG/00028/2017 | MP/PXOM, Camiño da Cerámica | 2016-12-01 |
| RPG/00031/2017 | Estudo de Detalle edificio comercial Mercadona | 2016-04-28 |

El número oficial del registro da la identidad estable. No se fusionan los dos
instrumentos de Baronzás: tienen números y fechas distintos. Si aparecen varios
documentos para un mismo número se agrupan en `documentos`, conservando URL,
número y página de procedencia; no generan nuevas actuaciones. Ganade no tiene
enlace documental en la tabla y se conserva con lista vacía y estado explícito.
Se retienen las URL HTTP de descarga tal como las publica la Xunta. Los ZIP no
se han descargado ni inspeccionado; no se afirma su disponibilidad o contenido.

Las fechas se extraen de columnas expresas: `fecha_inscripcion`, `fecha_aprob`,
`fecha_publicacion_dog`, `fecha_publicacion_bop`. `fecha` y
`fecha_publicacion` quedan nulas para no convertir inscripción o una de las dos
publicaciones en una fecha genérica ambigua. Ejemplo Guntimil: aprobación
2022-11-03, DOG 2022-11-29, inscripción 2023-05-22, BOP 2023-06-08.
No se infiere fase definitiva, concesión ni vigencia actual de una inscripción.
Los títulos y clases gallegas se conservan literalmente. La política compartida
de entidades deja estos seis registros en `pendiente`: no reconoce el número
de inscripción como número de expediente. Se conserva esa distinción; no se
inventa un expediente municipal para superar la clasificación.

## Cobertura y paginación

Cobertura parcial: inventario actual del registro autonómico para este municipio,
no todo el planeamiento histórico, proyectos municipales, obras o licencias.
Los instrumentos retornados abarcan aprobaciones de 2016 a 2022. Una inscripción
no prueba que sigan vigentes ni implica construcción material de las propuestas.
El registro no devuelve aquí el PXOM completo de 2003; no se fabrica ese registro
a partir de referencias de terceros.

La consulta filtrada devuelve seis filas sin paginador. El adaptador recorre todos
los enlaces de paginación descubiertos, preserva los filtros incluso cuando el
enlace solo contiene `page`, y elimina visitas repetidas. Ante páginas con idéntico
contenido, cambio de filtros/esquema, datos contradictorios o límite de seguridad
de 100 páginas, falla antes de reemplazar el JSONL. No acepta un resultado vacío
como un borrado válido sin revisión. `update_proyectos` refresca la instantánea
completa; no promete un histórico incremental de bajas.

## Geometría y validación

`geometry_status: unavailable`. La tabla ofrece paquetes documentales, sin
geometría vectorial ni coordenadas verificadas vinculadas a cada instrumento.
No se han vectorizado archivos, asignado centroides ni inventado CRS.
`publication_ready=false`; licencias, programación y jitter desactivados.

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Seis pruebas pasan con `-m unittest municipio.test_xinzo_de_limia -v`: fechas y
procedencia, filtros/esquema/filas inválidas, recorrido de paginación, preservación
de salida ante errores, agrupación documental e integración del manifiesto con
licencias deshabilitadas. Las pruebas usan HTML sintético basado en la tabla real;
no requieren red. La extracción real utiliza el adaptador cargado por el registro
común y deja en `evidence/` los seis registros (`proyectos.jsonl`), validación con
conteo/URL/limitaciones (`validation.json`), informe de entidades y captura HTML
de la consulta (`xunta-inventory-0.html`). Evidencia local, fuera de los cuatro
archivos fuente entregables. Sin DB, publicación ni ejecución del pipeline global.
