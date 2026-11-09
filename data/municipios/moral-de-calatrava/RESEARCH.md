# Moral de Calatrava — INE 13058, Ciudad Real

Verificado en vivo el 9 de noviembre de 2026. Adaptador de un único municipio,
con cobertura parcial del inventario actual de planeamiento municipal. Tres
instrumentos reales, doce enlaces documentales agrupados. No es un histórico
completo de proyectos ni un registro de licencias concedidas. Revisión independiente
pendiente; `publication_ready=false` por ausencia de geometría verificada.

## Descubrimiento y fuentes oficiales

La [web municipal](https://www.moraldecalatrava.org/web1/) enlaza al
[portal de transparencia](https://moraldecalatrava.sedelectronica.es/transparency).
Ambos respondieron HTTP 200. El portal contiene «7. URBANISMO, OBRAS PÚBLICAS Y
MEDIO AMBIENTE», con 43 documentos, y su subcarpeta «7.1. PLANEAMIENTO
URBANÍSTICO», con 14. La navegación pública Wicket redirige a carpetas con UUID
estable; el adaptador utiliza esas URL públicas, sin autenticación ni ejecución
de JavaScript remoto.

Fuentes extraídas (todas HTTP 200):

- [Inventario de planeamiento](https://moraldecalatrava.sedelectronica.es/transparency/e13025be-2d42-4311-89ce-ca0df4791a34/):
  cuatro documentos directos y dos carpetas con uno y nueve documentos.
- [Normas Subsidiarias](https://moraldecalatrava.sedelectronica.es/transparency/ef8dd259-fbaa-4e55-af23-0ee3da99ad73/):
  un documento «NORMATIVA». Una entidad de planeamiento; no se deduce fecha,
  aprobación ni vigencia de la presencia del documento en el inventario.
- Modificación puntual 1/2021: se agrupan «MP_1_2021_Moral_2021_08_01_completo» y
  «MODIFICACION_PUNTUAL_1_2021_DEFINITIVA» del inventario. Se conservan ambos
  enlaces originales. La versión definitiva descargada es un PDF escaneado;
  no se atribuyen fecha ni fase jurídica a partir de su nombre.
- [Plan parcial de mejora del Sector 8 Industrial](https://moraldecalatrava.sedelectronica.es/transparency/ec8b8c7a-6e3b-4f06-8348-94942c3fa563/):
  nueve documentos, todos conservados en una única entidad: dos anuncios,
  certificado plenario, memorias informativa y justificativa, normas, planos de
  información y ordenación y documento ambiental.
- [Certificado de acuerdo plenario](https://moraldecalatrava.sedelectronica.es/preview-document/414ceaff-7521-4555-9fd3-2d4e9f8cd12f):
  expediente 2932/2023; sesión de 10 de septiembre de 2026. El PDF certifica la
  votación y el acuerdo de aprobar definitivamente el plan. Se extraen referencia,
  fase y fecha de acuerdo/aprobación desde el texto del certificado, exigiendo
  el apartado ACUERDA posterior a la votación, además de la identificación del
  municipio, la sesión y el objeto. La firma del 11 de septiembre y el anuncio
  firmado el 15 de septiembre **no** se convierten en fechas de publicación.

## Exclusiones, alcance y limitaciones

«SECTOR RA» es un PDF escaneado cuyo rótulo no identifica suficientemente el
instrumento: se conserva captura para investigación pero no se genera entidad.
«Trámite de consulta pública» tampoco se convierte en proyecto. Quedan fuera
licencias de actividad, calificaciones urbanísticas, PLATEMUN, noticias,
contratación y actas de gobierno. El epígrafe municipal de obras públicas indica
cero documentos; no se presenta esto como ausencia de obras en el municipio.

Las fechas de publicación quedan nulas. No se usan creación de PDF, firma,
nombre de archivo ni fecha de consulta como acuerdo o publicación. No se extraen
coordenadas, centroides ni geometría desde los planos PDF. No se aplica jitter.
El manifiesto desactiva licencias y ejecución programada.

Se extraen las tres páginas completas. Actualmente no tienen paginación. El
adaptador rechaza controles «Mostrar más», siguiente página o paginadores;
verifica que los documentos hijos coinciden con los recuentos publicados y
rechaza nuevas carpetas/documentos que requieran revisar la agrupación. Así un
cambio de estructura provoca error y no una extracción aparentemente completa
con páginas omitidas. Las actualizaciones vuelven a leer la instantánea entera.

La clasificación compartida reconoce el expediente del Sector 8; los otros dos
instrumentos quedan `pendiente` por no tener referencia de expediente extraída.
No se inventa una referencia para satisfacer esa clasificación. La cobertura de
planeamiento no implica actividad edificatoria ni licencias concedidas.

## Validación reproducible y evidencia local

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Dependencias existentes requests y BeautifulSoup; conversión del certificado con
`/usr/bin/pdftotext` ya instalado. Sin cambios de dependencias.

- `python -m unittest municipio.test_moral_de_calatrava -v`: siete pruebas de
  agrupación, exclusiones, fechas, propuestas sin acuerdo, documentos faltantes,
  cambios de inventario, paginación, procedencia y licencias desactivadas.
- Extracción real mediante `load_manifest`, `load_portal_adapter` y
  `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con
  `portal.config.capture_dir='evidence'` sólo en memoria.
- Resultado: 3 registros; inventario de 14 documentos, 12 incluidos y 2 excluidos.
- `evidence/validation.json`: recuento, URL de fuentes, limitaciones y resultado
  del guard compartido. `evidence/planeamiento.html`, `normas.html`, `sector8.html`,
  certificado HTML/PDF/texto y capturas adicionales de investigación permiten
  contrastar la extracción. Evidencia local fuera de los cuatro archivos fuente.
