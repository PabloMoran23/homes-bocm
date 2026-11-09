# Abanilla — INE 30001, provincia de Murcia

Investigación y extracción real: 9 de noviembre de 2026. Un solo adaptador municipal,
implementado contra el contrato `municipio/adapters/portal.py`; manifest compatible
con `municipio/manifest.py` y carga mediante `municipio/adapters/registry.py`.
Se revisaron los ejemplos de Chipiona y Manlleu antes de implementar.

## Fuentes oficiales e inventarios explorados

- https://abanilla.es/ y https://abanilla.es/gestion-municipal/: web del Ayuntamiento.
  Gestión Municipal presenta un explorador documental JavaScript Share-one-Drive,
  no un listado HTML de expedientes. No se accedió a cuentas, credenciales ni carpetas
  privadas. No se considera ese contenedor vacío un proyecto.
- La web enlaza la sede correcta https://sede.abanilla.regiondemurcia.es/ .
  Su redirección HTML lleva a
  https://sede.abanilla.regiondemurcia.es/web/inicioWebc.do?opcion=noreg&entidad=30001 .
  La página identifica la sede de Abanilla y ofrece catálogo de trámites, licencias
  y permisos. Un trámite para solicitar licencia no acredita su concesión.
  No se verificó inventario de licencias concedidas; quedan desactivadas.
  El dominio tentativo abanilla.sedelectronica.es devolvió sede indeterminada y
  fue descartado; no es fuente del adaptador.
- Inventario utilizado: API pública del archivo municipal de noticias
  https://abanilla.es/wp-json/wp/v2/posts?search=obras&per_page=100&page=1 .
  Respuesta viva HTTP 200, `X-WP-Total=61`, `X-WP-TotalPages=1`.
  Las búsquedas exploratorias de planeamiento y planes no ofrecieron un inventario
  municipal estructurado de instrumentos. Sus resultados no se convierten en planes.
- Se localizaron también documentos oficiales BORM del PGMO, fuera del alcance
  implementado: https://www.borm.es/services/anuncio/336292/pdf y
  https://www.borm.es/services/anuncio/ano/2025/numero/3627/pdf?id=837688 .
  Son pistas para una futura cobertura de planeamiento; no se extraen ni se mezclan
  sus fechas con las de las obras viarias.

## Selección y resultado real

Cobertura deliberadamente parcial: publicaciones municipales con asunto principal
viario, una carretera RM identificada y evidencia textual de obras realizadas o en
marcha. No se extrae cada coincidencia de la palabra «obras». Se excluyen inspecciones
ITV, teatro, formularios, anuncios de licitación y previsiones de adjudicación.
Tampoco se generan actuaciones a partir de menciones secundarias a otras inversiones.
Otras obras públicas, caminos sin identificador RM y planes quedan fuera del filtro.

La ejecución generó **4 registros**, respaldados por **5 publicaciones**:

- RM-414, refuerzo por reciclado del firme con emulsión bituminosa, carretera
  Abanilla–Santomera. Publicaciones de inicio y evolución agrupadas: comparten
  carretera, tratamiento descrito y actuación observada. No se afirma que todo el
  tramo esté en Abanilla: es una conexión entre municipios.
- RM-422, rehabilitación de firme entre PK 3 y 9,3, en el término de Abanilla.
- RM-A21, mejora de seguridad vial y pavimento hacia Baños de Fortuna.
- RM-423, estado de obras visitadas en 2018. La fuente es breve: no permite precisar
  tramo, importe ni situación actual; se conserva literalmente su descripción.

Enlaces de los cinco artículos y capturas se enumeran en `evidence/validation.json`.
Cada registro conserva los artículos en `documentos`, sus fechas individuales,
contenido descriptivo y enlaces presentes. No se descargan solo títulos ni se
introducen registros precargados. La identidad del refuerzo por reciclado se basa
en carretera y técnica; en el resto, en la publicación. No se agrupan indiscriminadamente
todas las intervenciones históricas de una carretera. La agrupación heurística del
reciclado requerirá revisión si futuras actuaciones distintas usan la misma técnica
en esa carretera; no es una clave oficial de expediente.

## Fechas, geometría y límites

`fecha_publicacion` procede del campo `date` del CMS municipal, sin convertir la
fecha de modificación ni la fecha de una visita en un acuerdo. En registros agrupados
se muestra la publicación más reciente y se retienen las anteriores por documento.
`fecha_acuerdo` y `fecha_aprob` son nulas. No se infieren fechas de terminación,
concesiones, fases administrativas ni estado actual de ejecución. Las descripciones
son las publicadas por el Ayuntamiento en cada momento, no una verificación actual
sobre el terreno. La clasificación de obra viaria procede del adaptador; no equivale
a una categoría oficial de expediente.

Sin coordenadas, centroides o geometría comprobada: `lat`, `lon`, `geometry` nulos,
`geometry_status=unavailable`, `publication_ready=false`.
`schedule.enabled=false`, `geocode.jitter_missing=false`, `licencias.enabled=false`.
No es un histórico completo de proyectos, planeamiento o licencias de Abanilla.

## Paginación y ejecución

El adaptador sigue todas las páginas declaradas por WordPress, comprueba el total
de publicaciones y rechaza páginas vacías inesperadas, identificadores repetidos,
cambios de total durante el recorrido y redirecciones de dominio. No hay límite
silencioso de páginas ni salida de éxito sin actuaciones utilizables. Actualizar
reconstruye la instantánea completa del alcance; `state_path` no supone una fecha
límite que oculte documentos anteriores.

Runtime utilizado, sin instalar dependencias:

```
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_abanilla -v
```

Resultado: cinco pruebas correctas (selección y exclusiones, separación de actuaciones,
agrupación y semántica de fechas, manifest/registry y paginación completa o error).
Una primera ejecución del test de paginación descubrió una configuración incompleta
del mock de sesión; se corrigió y la suite completa pasó.

La extracción viva se ejecutó con `load_manifest('abanilla')`,
`load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`,
configurando únicamente `capture_dir='evidence'` en memoria. El envoltorio compartido
aplicó la política de entidades (4 categorías desconocidas; estado `ok`); se conserva
su informe sin inventar categorías. No se ejecutaron publicación, base de datos,
sincronización ni pasos de despliegue.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, `evidence/obras-page-1.json`, cinco capturas
`evidence/article-*.html` (HTTP 200 y SHA-256 en validación), páginas de descubrimiento
y respuestas exploratorias. Las únicas adiciones de código/documentación son los
cuatro ficheros solicitados.
