# l'Alcúdia de Crespins — INE 46020, Valencia

Verificación: 2026-11-09. Implementación limitada al inventario oficial municipal
«Planes urbanisticos». Se revisaron primero `municipio/manifest.py`, el contrato
`municipio/adapters/portal.py`, el registro de adaptadores y los ejemplos Manlleu
y Hernani. No se requieren dependencias ni modificaciones compartidas.

## Fuentes e inventarios descubiertos

- https://transparencia.acrespins.es/ — portal de transparencia municipal. Su pie
  identifica al Ajuntament de L'Alcúdia de Crespins, CIF P4602000D, y enlaza la web
  municipal https://www.lalcudiadecrespins.es/ y la sede
  https://acrespins.sede.dival.es/. Captura: `evidence/transparencia-home.html`.
- https://transparencia.acrespins.es/urbanismo-obras-publicas-y-medio-ambiente/
  — directorio municipal de urbanismo; enlaza planes, normas y medio ambiente.
- https://transparencia.acrespins.es/planes-urbanisticos/ — inventario utilizado.
  FacetWP declara `page=1`, `per_page=100`, `total_rows=1`,
  `total_rows_unfiltered=1`, `total_pages=1`. Un instrumento: «PGOU ( PLAN GENERAL
  DE ORDENACIÓN URBANÍSTICA)», año fuente 2023.
- https://transparencia.acrespins.es/plan-urbanistico/pgou/ — ficha utilizada.
  Contiene el archivo municipal PGOU2023.rar y siete enlaces adicionales:
  certificado del pleno, dos catálogos, normas, fichas, planos y memorias.
  Se retienen los ocho enlaces y sus rótulos en un único registro. El botón final
  sin href no constituye otro documento. Captura de la ejecución real:
  `evidence/plan-urbanistico-pgou.html`.
- https://transparencia.acrespins.es/normas-urbanisticas/ — dos entradas:
  ordenación estructural y pormenorizada; no se cuentan como dos proyectos nuevos.
  Sus páginas individuales no están incorporadas al extractor. La ficha PGOU ya
  enlaza un archivo NORMAS.zip; no se afirma equivalencia documental completa.
- https://transparencia.acrespins.es/obras-publicas/ — inventario consultado:
  FacetWP declara cero resultados, cero páginas y cero opciones de año. No se
  inventan obras a partir de este directorio vacío.
- https://acrespins.sede.dival.es/carpetaciudadana/tramite.aspx?idtramite=18395
  — solicitud de informe urbanístico, encontrada durante la búsqueda. Es un
  trámite de solicitud, no una licencia concedida; se excluye.

Las capturas de los directorios anteriores están en `evidence/` con nombres
correspondientes a sus rutas. La búsqueda web permitió localizar también una
comunicación de la Generalitat sobre aprobación del plan (22/03/2023, sesión
15/03/2023), pero no es la fuente del registro ni se incorporan esas fechas:
https://www.gva.es/va/web/arees/vivenda-i-urbanisme/-/asset_publisher/glSjBLQyRkC1/content/la-comisi%C3%93n-territorial-de-urbanismo-de-valencia-aprueba-el-plan-general-de-l%C2%B4alcudia-de-crespins/20551182

## Semántica y límites

El año del inventario se conserva como `anio_fuente`, nunca como fecha completa.
El rótulo «CERTIFICADO PLENO 26/05/2023» se conserva como título documental: sin
leer el certificado no se atribuye su fecha a aprobación del PGOU. Las rutas
`uploads/2024/10` tampoco acreditan publicación ni acuerdo. `fecha`,
`fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` y `fase` quedan nulos.

Cobertura parcial municipal: no incluye un histórico completo de instrumentos,
licencias, expedientes, actas, contratación ni noticias. No extrae el interior
ni comprueba la disponibilidad de todos los archivos PDF/ZIP/RAR; conserva su
proveniencia en `documentos[].source_url`. No extrae geometría ni coloca el
centroide del municipio: latitud, longitud y geometría nulas,
`publication_ready=false`. El guardián semántico compartido clasifica el registro
como pendiente por identidad insuficiente; no se modifica esa política.

La extracción exige metadatos FacetWP, verifica conteos de resultados y páginas
contra el HTML y falla si aparece paginación o filtrado. No hay un límite de
registros que recorte resultados silenciosamente. Instrumentos nuevos de tipo
no revisado, estructura cambiada o ficha sin documentos también producen error.
Se escribe el resultado de forma atómica tras validar todas las fichas; una
actualización es una instantánea completa, sin cursor de fechas.

## Validación reproducible

Runtime preinstalado utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas ejecutadas: `python -m unittest municipio.test_l_alcudia_de_crespins -v`:
7 correctas. Cubren agrupación y deduplicación documental, procedencia, ausencia
de fechas inferidas, rechazo de solicitudes y navegación, cambios de estructura,
paginación incompleta, enlaces inesperados, resolución del manifiesto y
conservación del resultado anterior ante una extracción fallida.

Ejecución real mediante `load_manifest`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `capture_dir=evidence`:
1 registro real, 8 enlaces documentales. Resultado y limitaciones en
`evidence/validation.json`; capturas HTML locales conservadas para auditoría.
Licencias, ejecución programada y jitter desactivados en el manifiesto.
La evidencia es local y no forma parte de los cuatro archivos fuente.
