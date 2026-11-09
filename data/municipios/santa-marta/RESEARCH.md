# Santa Marta — Badajoz — INE 06121

Verificación en vivo: 2026-11-09. Adaptador único:
`municipio.adapters.santa_marta:SantaMartaAyuntamientoAdapter`.

## Descubrimiento y fuentes oficiales

- Web del Ayuntamiento: https://santamarta.es/ (captura `evidence/municipal.html`).
  El directorio provincial identifica esta web para Santa Marta, Badajoz:
  https://www.dip-badajoz.es/municipios/municipio_dinamico/inicio/index_inicio.php?codigo=136
  Ese 136 es un identificador provincial interno, no el INE.
- Administración municipal: https://santamarta.es/administracion.php (HTTP 200).
  Contiene modelos «Obra con proyecto» y «Obra sin proyecto», no concesiones.
  No genera registros. Las noticias generales y el perfil de contratación no se
  usan como sustitutos de expedientes urbanísticos o proyectos reales.
- Sede: https://santamartadelosbarros.sedelectronica.es/info.0 (HTTP 200).
  Catálogo de trámites y acceso al tablón/transparencia; esta revisión no ha
  verificado un registro público de licencias concedidas. No se accede a carpetas
  personales ni a zonas autenticadas.
- Inventario autonómico oficial de seguimiento del planeamiento de la Junta:
  https://sitex.juntaex.es/SITEX/planeamiento
  Descubierto por la búsqueda de planeamiento de Santa Marta y su ficha
  https://sitex.juntaex.es/SITEX/planeamiento?ptofigura=40168 .
  El selector identifica **Santa Marta = 166**; Santa Marta de Magasca es otra
  opción (449), excluida. El 166 tampoco es el INE.

El JavaScript público usa `Ajax.Updater` sobre
`https://sitex.juntaex.es/SITEX/ptofiguras/listadoresultadossigcat` con
**POST de consulta** `municipioseleccionado=166`, cabeceras
`X-Requested-With: XMLHttpRequest` y `X-Update: planeamientosindex`.
Un GET no selecciona municipio y puede devolver «No hay ningún planeamiento»;
no se acepta como resultado vacío. El parser exige la opción 166 seleccionada.
El inventario devuelve el árbol municipal completo sin paginación. Se recorren
**todos** los enlaces `viewsigcat/<id>` con estado V o TR, deduplicando por ID;
NV (histórico no vigente) y el refundido raster agregado quedan fuera del alcance.
No hay límite ni corte de resultados. Si aparece paginación HTML se falla
explícitamente; requeriría ampliar el recorrido. No se interpreta JavaScript remoto.

## Resultado y semántica

Extracción real mediante el adaptador resuelto por el manifest: **7 instrumentos**,
**102 enlaces documentales**. Una fila por instrumento, no por PDF ni por anuncio.

| ID SITEX / ficha | Referencia | Estado fuente | Fecha AD | Publicación AD | Documentos |
| --- | --- | --- | --- | --- | --- |
| [37254](https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/37254) | PGM | Vigente | 2016-06-30 | 2016-12-29 | 93 |
| [40168](https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/40168) | PGM.M-001 | Vigente | 2022-02-24 | 2022-08-23 | 4 |
| [40406](https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/40406) | PGM.M-002 | En trámite | 2022-04-07 | sin dato | 1 |
| [39582](https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/39582) | PGM.ED-001 | En trámite | sin dato | sin dato | 1 |
| [39745](https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/39745) | PGM.ED-002 | En trámite | sin dato | sin dato | 1 |
| [40163](https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/40163) | PGM.ED-003 | En trámite | sin dato | sin dato | 1 |
| [40234](https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/40234) | PGM.ED-004 | En trámite | sin dato | sin dato | 1 |

`fecha_aprob` procede únicamente de «Fecha AD»; `fecha_publicacion` de «Fecha de
publicación AD». Los anuncios de información pública inicial conservan su fecha
y concepto en `tramites`; no se convierten en publicación de aprobación definitiva.
`fecha` y `fecha_acuerdo` quedan nulas. No se infiere una fase a partir del tipo.
En 40406 se conserva la discordancia de SITEX: estado «En trámite» y AD municipal
registrada el 07/04/2022, sin publicación definitiva. No se declara vigente por
inferirlo de esa aprobación. Tampoco se verifica aquí la vigencia jurídica de cada
instrumento contra posibles actos posteriores fuera de SITEX.

Los documentos técnicos y las publicaciones DOE se agrupan por ID SITEX, con
`título`, URL original, organismo y URL de ficha de procedencia. Se retienen todos
los enlaces observados y los nombres `download`, incluso los planos del PGM.
Algunos expedientes sólo ofrecen el anuncio DOE y no el proyecto técnico completo.
No se fusionan 1-A y 1-B: son instrumentos distintos registrados separadamente.
Se preservan las URLs HTTP originales de DOE; dos documentos se comprobaron
adicionalmente por HTTPS (200 y firma PDF), con capturas locales:
https://sitex.juntaex.es/SITEX/ptofiguras/downloaddocumento/11393 y
https://doe.juntaex.es/pdfs/doe/2022/1620o/22AC0067.pdf .
No se han descargado/verificado los 102 destinos individualmente.

## Cobertura y geometría

Cobertura parcial: planeamiento marcado V/TR en SITEX, sin histórico NV, sin
inventario completo de obras públicas y sin licencias. Las fechas antiguas son
las de los expedientes, no la fecha de extracción del inventario actual. La
procedencia efectiva es la Junta (`source=junta_extremadura_sitex`); el valor
`proyectos.source=ayuntamiento` del manifest selecciona el flujo del adaptador del
portal según el esquema existente, no atribuye la publicación al Ayuntamiento.

`geometry_status: unavailable`. El portal SITEX ofrece mapa municipal y enlaces
al centro de descargas; las fichas examinadas no exponen geometrías vectoriales
vinculadas al ID de cada instrumento. Los planos PDF no se vectorizan, ni se
utiliza el centroide del municipio como ubicación del expediente. Latitud,
longitud y geometría nulas; `publication_ready=false`.

## Validación y reproducción

Runtime empleado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_santa_marta -v
```

7 pruebas offline: selección municipal, exclusión NV y deduplicación, paginación,
fechas diferenciadas y discordancia de estado, documentos agrupados, rechazo de
fichas ajenas/ausentes, carga de manifest, licencias sin red y conservación de la
instantánea anterior si falla la extracción. Fixtures sintéticos embebidos en el
test, sin dependencia de las evidencias locales.

Reproducir la extracción, sin orquestador:

```python
from pathlib import Path
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter
manifest = load_manifest('santa-marta')
manifest.portal.config['capture_dir'] = 'evidence'
report = load_portal_adapter(manifest).backfill_proyectos(Path('evidence/proyectos.jsonl'))
```

`update_proyectos` refresca la instantánea completa; no depende de cursores ni
trunca páginas. Cualquier fallo de detalle o red impide sustituir el JSONL.
Evidencias locales: `proyectos.jsonl`, `validation.json` con `live_records=7`,
URLs, parámetros de consulta, limitaciones y comprobaciones HTTP; árbol de
inventario y siete fichas HTML, web municipal, administración, sede y dos PDF de
muestra. No se incorporan como fuentes versionadas.

Manifest: INE 06121, Santa Marta, Badajoz, Extremadura;
`schedule.enabled=false`, `licencias.enabled=false`,
`geocode.jitter_missing=false`. Sin cambios compartidos ni dependencias nuevas.
