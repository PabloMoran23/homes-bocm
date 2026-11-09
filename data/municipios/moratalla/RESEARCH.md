# Moratalla — INE 30028, provincia de Murcia

Investigación y comprobación en vivo: 9 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Se revisaron previamente el contrato `municipio/adapters/portal.py`, el cargador
`municipio/manifest.py`, el registro de adaptadores y los ejemplos Chipiona y Hernani.

## Fuentes descubiertas

- Web municipal actual: https://moratalla.es/ y su mapa https://moratalla.es/mapa-web/.
  https://moratalla.es/transparencia/ muestra «TBD». El enlace municipal a
  https://sede.moratalla.regiondemurcia.es/web/transparencia?entidad=30028&idioma=1
  devuelve la envoltura de la sede, sin inventario documental utilizable en el HTML.
  No se han convertido formularios, eventos, noticias ni anuncios contractuales en obras.
- El dominio antiguo https://www.ayuntamientomoratalla.net/ responde con una
  redirección HTML a su versión HTTP, sin inventario en la respuesta consultada.
- URBmurcia: https://urbmurcia.carm.es/ identifica el registro regional de
  planeamiento. Su consulta https://urbmurcia.carm.es/consulta-general-de-expedientes
  y últimas publicaciones devuelven CAPTCHA a las peticiones del runtime.
  No se ha intentado eludirlo. La página CARM de estado del planeamiento
  https://www.carm.es/web/pagina?IDCONTENIDO=47211&IDTIPO=100&RASTRO=c521$m
  enlaza un PDF, pero su descarga devolvió HTML en esta ejecución. No se usa
  como si se hubiera leído un instrumento.
- Fuente efectiva: inventario oficial de la Confederación Hidrográfica del Segura
  https://www.chsegura.es/es/cuenca/infraestructuras/embalses/listado-de-embalses/.
  Se llega desde https://www.chsegura.es/es/cuenca/infraestructuras/embalses/.
  Contiene obras hidráulicas físicas con ficha técnica, ubicación administrativa y
  documentación gráfica. Es una fuente estatal sobre el municipio, no una fuente
  del Ayuntamiento ni una lista de obras municipales recientes.

## Extracción y alcance

Se leen las **33 filas** presentes en el HTML del inventario y se consultan las
**33 fichas**, sin elegir obras por coincidencias en una noticia, nombre del río o
menú. El filtro utiliza exclusivamente los campos tabulados «Término municipal»
y «Provincia». Resultado observado: **3 obras existentes** y 30 fichas excluidas
por pertenecer a otros términos municipales:

| Obra | Ficha oficial | Ubicación literal |
| --- | --- | --- |
| Embalse de la Risca | https://www.chsegura.es/es/cuenca/infraestructuras/embalses/Embalse-de-la-Risca/ | Moratalla; Murcia |
| Embalse de Moratalla | https://www.chsegura.es/es/cuenca/infraestructuras/embalses/Embalse-de-Moratalla/ | Moratalla; Murcia |
| Embalse del Cenajo | https://www.chsegura.es/es/cuenca/infraestructuras/embalses/Embalse-del-Cenajo/ | Moratalla y Hellín; Murcia y Albacete |

Una ficha es una obra, con identificador estable derivado de su URL y todos sus
PDF de la sección «Planos» agrupados en `documentos`: 5 de La Risca, 5 de
Moratalla y 2 del Cenajo. Cada documento conserva título, URL y ficha de
procedencia. No se incorporan certificados ENS del pie de página. La descripción
procede de la sección «Finalidad»; se mantiene el literal de construcción, uso y
gestor del inventario. No se inventan referencias de expediente.

La tabla actual entrega todas las filas en el DOM, aunque la interfaz pueda
paginarlas en cliente. El parser no limita las filas y rechaza enlaces de
paginación remota o configuración AJAX/serverSide identificada. Fallan también
un inventario vacío, cambios de esquema, una ficha sin jurisdicción estructurada
o una obra seleccionada sin documentos. Una petición fallida aborta el conjunto:
no se publica silenciosamente una instantánea parcial. El archivo se reemplaza
solo al finalizar la extracción completa. `update_proyectos` repite la instantánea
completa, sin cortes temporales ni modificación de estado incremental.

## Semántica y límites

Cobertura parcial de infraestructuras históricas documentadas, no de todas las
obras, nuevos proyectos o instrumentos urbanísticos del municipio. La consulta
actual de la ficha no implica actualidad del contenido técnico. No se afirma
concesión de licencia, aprobación de proyecto, fase actual de tramitación ni
competencia municipal sobre las presas. El Cenajo conserva su carácter compartido;
no se atribuye la totalidad del embalse exclusivamente a Moratalla.

No se extraen fechas: ni las fechas del CMS ni un año de construcción constituyen
fechas de publicación, acuerdo o aprobación. Se omiten esas claves en vez de
asignarles significados supuestos. Tampoco se extraen coordenadas de textos,
planos ni mapas; `geometry_status: unavailable` y `publication_ready: false`.
No se acredita un registro de licencias concedidas: `licencias.enabled: false`.
Programación y jitter desactivados en el manifest.

`proyectos.source: ayuntamiento` selecciona la ruta de adaptador del esquema
existente. El manifest aclara la fuente estatal y cada registro identifica
`source: confederacion_hidrografica_del_segura`. No se altera el contrato común
ni la política de entidades. El guard compartido puede clasificar estas fichas
sin expediente como `pendiente`; no se fabrican referencias para forzar su
publicación. Son evidencia de obras físicas existentes para revisión independiente.

## Validación y evidencia local

Pruebas: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_moratalla -v`.
Ocho pruebas comprueban el esquema/INE, inventario completo de más de 50 filas,
duplicados, cambios de esquema, paginación, enlaces ajenos, exclusión por
jurisdicción, ubicación compartida, aislamiento de documentos, ausencia de fechas
y coordenadas inventadas, fallo sin sobrescribir resultados y licencias desactivadas.

Extracción real mediante `load_portal_adapter(load_manifest('moratalla'))` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con capturas habilitadas
mediante `adapter.config['evidence_dir'] = 'evidence/live-captures'`.
`evidence/validation.json` registra `live_records`, URLs visitadas, cobertura,
limitaciones y resultado del guard de entidades. `evidence/proyectos.jsonl`
contiene registros reales; `evidence/live-captures/` conserva el HTML del listado
y de cada ficha. Los 12 enlaces documentales respondieron HTTP 200,
`application/pdf`, con firma `%PDF-` al comienzo. Se conservan únicamente los
primeros 4096 bytes por documento y el informe `evidence/document-checks.json`;
esta comprobación no supone lectura ni validación completa del PDF.
Las capturas exploratorias y la auditoría completa también
permanecen bajo `evidence/`. La descarga CARM fallida se guarda como HTML,
no como un PDF validado. La evidencia es local y no forma parte de los cuatro
archivos fuente entregados. No se ejecuta publicación, geocodificación, base de
datos ni despliegue.
