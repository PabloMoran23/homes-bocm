# Chipiona — INE 11016

Investigación y ejecución real: 7 de noviembre de 2026.

## Fuente y cobertura

https://www.aytochipiona.com/delegaciones/urbanismo/

Inventario municipal vivo de paquetes WordPress Download Manager. Se seleccionan tarjetas h3.package-title con nombres de instrumentos/proyectos: PGOU, modificaciones, rectificaciones, planes especiales, estudios de detalle y proyectos de actuación/urbanización. Modelos de licencia, ordenanzas, memorias genéricas y normas sueltas se excluyen. Treinta y tres entradas reales: modificaciones Camacho Baños/Estación, planes Camarón/Tres Piedras, estudios CO3/CO9/CO10, proyectos Los Quemados/Vaqueras/Carnero y actuaciones nombradas. Cada registro representa una entrada documental publicada, sin afirmar concesión de licencia ni vigencia. La URL identifica la ficha concreta; el scraper no fija tokens temporales de descarga. Una comprobación puntual de la ficha Los Quemados descubrió data-downloadurl y descargó solo los primeros bytes, siguiendo redirección a https://aytochipiona.com/docs/quemados.pdf ; respondió200 application/pdf y firmaPDF válida. El inventario completo observado está servido en una página, sin paginación identificada.

Resultado: **33 registros** extraídos del inventario actual. No se devuelve un expediente literal precargado ni una página genérica como actuación sintética. La desaparición del contenedor/listado o ausencia de instrumentos/documentos provoca error.

## Semántica

Sin fechas de aprobación deducidas, sin coordenadas inventadas y sin inferir fases. Las fechas de actualización del CMS no son fechas de acuerdo. Todos los registros declaran `publication_ready: false` y `geometry_status: unavailable`. Los manifests desactivan `schedule.enabled` y `geocode.jitter_missing`. Licencias desactivadas: no se ha verificado un registro público de concesiones.

## Comprobaciones

`python3 -m unittest municipio.adapters.test_chipiona -v`: correcto. Tests de contenido específico, rechazo de vacíos y ausencia de metadatos inventados; Tolosa prueba también aislamiento de documentos entre modificaciones.

Ejecución directa de `backfill_proyectos`, sin base de datos, publicación o geocodificación. Evidencia externa: `chipiona/proyectos.jsonl` y `chipiona/validation.json` del directorio del orquestador. Muestra documental: HTTP200, `application/pdf`, firma PDF válida en https://aytochipiona.com/docs/quemados.pdf. Solo se leyó el inicio del archivo; no se descargó todo el inventario masivamente.
