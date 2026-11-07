# Garrucha — INE 04049, Almería, Andalucía

Revisión y extracción en vivo: 2026-11-07. Adaptador dedicado:
`municipio.adapters.garrucha:GarruchaAyuntamientoAdapter`.

## Descubrimiento y fuentes oficiales

El [mapa web municipal](https://www.garrucha.es/Servicios/cmsdipro/index.nsf/componente.xsp?p=Garrucha&ref=mapa-web)
enlaza Normas, Tablón de Anuncios y Tablón Histórico Público. El
[tablón actual](https://www.garrucha.es/Servicios/cmsdipro/index.nsf/tablon_view_categoria123.xsp?p=Garrucha)
expone las categorías Normas y Normas en Trámite de Aprobación. El adaptador usa
sus inventarios por categoría, sin fijar anuncios individuales como semillas:

- [Normas](https://www.garrucha.es/Servicios/cmsdipro/index.nsf/tablon_view_categoria1.xsp?cat=Normas&p=Garrucha): Planeamiento Urbanístico → Registro de Instrumentos de Planeamiento.
- [Normas en Trámite de Aprobación](https://www.garrucha.es/Servicios/cmsdipro/index.nsf/tablon_view_categoria1.xsp?cat=Normas+en+Tr%C3%A1mite+de+Aprobaci%C3%B3n&p=Garrucha): Planeamiento Urbanístico → 2018.

El portal es del Ayuntamiento de Garrucha, CIF P-0404900-C; usa infraestructura
Domino/XPages de Diputación de Almería. Las peticiones POST del adaptador sólo
abren categorías de la vista mediante los eventos de expansión y el estado del
formulario público. No presentan solicitudes ni modifican expedientes.

## Registros y significado

La extracción devuelve dos instrumentos reales y cinco documentos agrupados:

- [Estudio de detalle residencial Aldea Marina](https://www.garrucha.es/Servicios/cmsdipro/index.nsf/tablon.xsp?p=Garrucha&documentId=CEF33FBCE5CA6CD3C125811700263E3B): publicación municipal 2017-05-05; un PDF. El texto del anuncio indica aprobación definitiva y referencia el BOP nº 84. La fecha de publicación **no** se convierte en fecha del acuerdo ni de aprobación.
- [Avance del Plan General de Ordenación Urbana de Garrucha](https://www.garrucha.es/Servicios/cmsdipro/index.nsf/tablon.xsp?p=Garrucha&documentId=37BDBD0F0391199EC12582390047A823): publicación municipal 2018-02-19; cuatro tomos (información urbanística, memoria descriptiva, documento inicial estratégico y planos). Es un avance en la rama de normas en trámite, sin afirmar aprobación definitiva.

Se conservan título, descripción original del anuncio, URL del inventario,
URL canónica del detalle, fecha explícita de publicación, fase sólo cuando
la fuente la expresa y todos los adjuntos con su URL de procedencia. Los
enlaces duplicados «descargar» no producen documentos ni proyectos adicionales.
El identificador estable es el ID Domino del anuncio; los tomos pertenecen al
mismo instrumento. No se analiza el contenido de los PDFs para deducir acuerdos.

## Cobertura y límites

Instantánea de las dos ramas actuales de planeamiento, no un censo exhaustivo
del planeamiento vigente, de todas las obras, ni del histórico municipal.
Las fechas antiguas son las fechas publicadas: que los documentos sigan accesibles
hoy no prueba su vigencia jurídica actual. No se incluyen contratación de obras,
noticias genéricas, ordenanzas o formularios como si fueran proyectos o licencias.
No se ha identificado un registro utilizable de licencias concedidas;
`licencias.enabled: false` y sus métodos generan cero registros.

Se abren todas las subcategorías de Planeamiento Urbanístico, independientemente
del año, conservando la sesión XPages. No hay paginación activa en las vistas
observadas. Los controles de paginación detectados provocan error explícito:
no se acepta sólo la primera página. También se falla ante rama vacía/ausente,
expansiones sin progreso, límite de seguridad, cambios de estructura o falta
de adjuntos. Actualizar repite la instantánea completa; no afirma incrementalidad.

No se ha verificado geometría asociada a los IDs de los instrumentos. Los planos
PDF no se convierten automáticamente en coordenadas: `geometry_status: unavailable`,
`publication_ready: false`, `geocode.jitter_missing: false`.
`schedule.enabled: false`.

## Validación reproducible

Runtime preinstalado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_garrucha -v`: seis pruebas sin red para
identidad, agrupación de adjuntos, semántica temporal y del avance, exclusión de
formularios, rechazo de otros municipios/dominios, paginación, estructura rota,
recorrido de subcategorías y licencias deshabilitadas.

La extracción real carga el manifest con `load_manifest('garrucha')`, resuelve
el adaptador con `load_portal_adapter` y ejecuta `backfill_proyectos` hacia
`evidence/proyectos.jsonl`. `portal.config.capture_dir` se configura sólo en
memoria para conservar las respuestas HTML bajo `evidence/`.
`evidence/validation.json` registra recuentos, URLs y limitaciones; las capturas,
JSONL y validación son evidencia local, no archivos fuente para commit.

Los cinco enlaces adjuntos se descargaron con HTTP 200 y firma `%PDF-`
verificada. Sus capturas locales son `evidence/attachment-1.pdf` a
`evidence/attachment-5.pdf`; la validación conserva URL, tamaño y ruta de cada uno.
