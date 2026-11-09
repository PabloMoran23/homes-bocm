# Castejón (Navarra), INE 31070

Verificado el 9 de noviembre de 2026 con extracción HTTP real. Adaptador parcial
del tablón municipal vigente, no un inventario exhaustivo de proyectos históricos.

## Descubrimiento oficial e inventarios

La portada municipal https://www.castejon.com/ enlaza «Tablón de anuncios» a
https://sedeelectronica.castejon.com/tablondeanuncios/ . Su inventario canónico es
https://sedeelectronica.castejon.com/tablondeanuncios/default.aspx . La sede identifica
CASTEJÓN, Navarra, Plaza de los Fueros, y la versión accesible identifica la entidad
31070. El NIF municipal P3106900H no es el código INE.

La extracción del inventario sin filtrar («Todas las áreas») recuperó **12 anuncios**,
sin paginación activa. Recorre todas las filas, descubre los detalles por sus enlaces
y selecciona información pública sobre bienes y derechos afectados por proyectos.
No usa una noticia ni un ID individual como semilla. No fija un límite de registros.
Si aparece paginación mediante enlaces, controles de página o postbacks WebForms,
falla explícitamente antes de escribir una instantánea parcial. También falla ante
cambios de estructura, fuente vacía sin proyectos de este alcance, discrepancias de
identidad/fecha o pérdida de documentos. El siguiente refresco vuelve a leer todo
el inventario vigente, sin pretender reconstruir anuncios retirados.

El enlace municipal https://www.castejon.com/transparencia/ redirige a
https://transparencia.animsa.es/P3106900H y devuelve una aplicación Blazor sin
inventario renderizado en el HTML recibido. No se presenta como una fuente cubierta.
https://sedeelectronica.castejon.com/catalogoservicios.aspx ofrece trámites:
una solicitud de licencia no acredita una licencia concedida y no se extrae.
No se ha verificado un registro público de concesiones. Licencias deshabilitadas.

## Proyecto real y procedencia

Resultado vivo: **1 registro**, anuncio municipal **27840**:

- https://sedeelectronica.castejon.com/tablondeanuncios/anuncio.aspx?id=27840
- Título literal: «PERIODO DE INFORMACION PUBLICA DE LA RELACION DE BIENES Y
  DERECHOS AFECTADOS PROYECTO ALTA VELOCIDAD».
- Publicación/inicio de exposición municipal: **2026-10-26**. Fin de exposición
  indicado en el inventario: **2026-11-17**. No se deriva la fecha final del plazo
  contado en el documento. No se atribuye ninguna fecha de acuerdo ni aprobación.
- Un documento oficial, ID **66181**, retenido dentro del registro del proyecto:
  https://sedeelectronica.castejon.com/tablondeanuncios/documento.aspx?id=66181&modo=guardar
  (PDF, 14 páginas, 9.928.558 bytes en esta comprobación).

La primera página del PDF fue renderizada e inspeccionada visualmente: el anuncio
de Adif-Alta Velocidad identifica el **Proyecto Básico de la Conexión Ferroviaria
de la Línea de Alta Velocidad Castejón-Pamplona en el entorno de Castejón de Ebro**.
Se somete a información pública la declaración de necesidad de ocupación de bienes
y derechos afectados. Menciona los ayuntamientos de Castejón y Tudela: el proyecto
no se afirma exclusivo de Castejón ni se extraen datos de propietarios.
Es evidencia documental de una infraestructura física, no un anuncio de compra ni
una autorización de obra concedida. No se afirma que esté ejecutada o aprobada.

El cuerpo del PDF es una imagen escaneada; `pdftotext` recupera principalmente los
sellos municipales. Por eso el adaptador conserva el título del anuncio municipal,
sin codificar manualmente el título ampliado ni convertir los sellos o las fechas
de registro de entrada en fechas de aprobación. Retiene todos los adjuntos de cada
anuncio en `documentos`, deduplica los enlaces por ID y verifica firma PDF y SHA-256;
los adjuntos nunca generan proyectos adicionales. El ID estable del registro es el
del anuncio, no un número de expediente inventado. Esta fuente no proporciona un
identificador estructurado para enlazar futuras publicaciones de un mismo proyecto:
una eventual repetición del instrumento en otro anuncio requiere revisión.

## Geometría y límites

`geometry_status: unavailable`. No hay geometría vectorial asociada al anuncio ni
coordenadas verificadas. No se geocodifican direcciones municipales, ni se emplea el
centroide del municipio o se vectorizan planos. `lat`, `lon`, `geometry`,
`fecha_acuerdo` y `fecha_aprob` son nulos; `publication_ready` es falso.

Cobertura limitada a los anuncios vigentes de exposición de bienes y derechos
proyectados. Se excluyen presupuestos, empleo, padrones, formularios y licitaciones.
No cubre todos los instrumentos urbanísticos, obras ni el histórico municipal.
El clasificador compartido anota el registro como `pendiente`,
`insufficient_identity_evidence`: el código de anuncio y el título general no se
convierten artificialmente en un expediente urbanístico ni se elude esa anotación.
La evidencia visual acredita el proyecto; queda pendiente la clasificación común.

## Implementación y validación reproducible

Runtime usado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_castejon -v` — **6 pruebas correctas**.
Cubren fechas de publicación frente a exposición, exclusión de formularios,
licitaciones y presupuestos, duplicados, documentos agrupados, identidad del
detalle, URL de adjuntos, paginación, cambios de estructura, respuesta no PDF,
preservación del resultado anterior ante fallo, manifest/registro y licencias vacías.

La extracción real usa `load_portal_adapter(load_manifest('castejon'))`, configura
`capture_dir='evidence/live'` y ejecuta
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`. Peticiones HTTP públicas,
timeouts y límite de tamaño que provoca error explícito, no recorte silencioso.
La escritura de proyectos solo ocurre tras completar las verificaciones.

Evidencia local no destinada a commit:
`evidence/proyectos.jsonl`, `evidence/validation.json`,
`evidence/live/inventory.html`, `evidence/live/notice-27840.html`,
`evidence/live/document-66181.pdf`; capturas adicionales del descubrimiento y
`evidence/documento-66181-page1.png` para inspección visual.

`schedule.enabled=false`, `geocode.jitter_missing=false`, `licencias.enabled=false`.
No se ejecutaron publicación, base de datos, despliegue ni sincronización.
