# Vilallonga / Villalonga — INE 46255, Valencia

Comprobado el 2026-11-09 con solicitudes HTTPS reales. Adaptador exclusivamente
para este municipio valenciano; no Vilallonga del Camp ni Vilallonga de Ter.

## Descubrimiento y fuentes oficiales

La web https://villalonga.es/ devuelve HTTP 403 en este entorno; la variante con
`www` presenta un error de certificado. No se desactiva la verificación TLS.
La sede oficial responde HTTP 200:
https://ayuntamientodevillalonga.sedelectronica.es/transparency
Su sección «6. URBANISME, OBRES PÚBLIQUES I MEDI AMBIENT» muestra 61 documentos:
https://ayuntamientodevillalonga.sedelectronica.es/transparency/4603b71d-617a-4fae-82af-8e96c1a0e66a/

El inventario «6.1. PLANEJAMENT URBANÍSTIC», fuente del adaptador, muestra 46:
https://ayuntamientodevillalonga.sedelectronica.es/transparency/4ae93831-fe0b-4cee-b3ad-c6942bc90c38/
Incluye cuatro enlaces externos, «Publicació Pla» y una carpeta nominativa de
41 documentos: **Modificació Pla Ampliació Sector C Industrial**.
https://ayuntamientodevillalonga.sedelectronica.es/transparency/08ed6766-7d7b-4f4b-9ecf-a2bb3e12bfa5/

El mismo inventario municipal enlaza el registro autonómico para el INE exacto:
https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/4%20VALENCIA/46255%20VILLALONGA/
Comprobado HTTP 200, con directorios «1 PLANEAMIENTO GENERAL» y
«2 PLANEAMIENTO DE DESARROLLO». Se conserva captura como evidencia del
inventario alternativo; este adaptador no recorre ni afirma cubrir ese registro.

## Extracción y unidad de registro

Un registro por carpeta nominativa de instrumento urbanístico. ID basado en el
UUID público de la carpeta oficial, título conservado del inventario. Los
anexos, planos, estudios ambientales, edicto y acuerdo no generan registros
adicionales. Se retienen los 41 enlaces públicos estables `preview-document`,
con título, URL del inventario que los contiene y ruta de carpetas.
No se persisten callbacks Wicket de sesión como enlaces documentales.

Se descubren las carpetas desde el inventario, se resuelven sus callbacks con
una sesión HTTP y se recorren recursivamente. Se agota «Mostrar más» mediante
respuestas XML de Wicket. La carpeta ambiental tiene **27 documentos, repartidos
en 10 + 10 + 7**. Se admite la reutilización del mismo callback cuando entrega
nuevos documentos. Se rechazan paginación sin progreso, estructura inesperada,
ciclos, destinos ajenos a la sede y discrepancias con los recuentos publicados.
Los límites de seguridad producen error, nunca salida parcial. Solo se sustituye
el JSONL al completar la extracción. La actualización repite el inventario actual;
no pretende mantener un histórico de documentos retirados.

Resultado real: **1 instrumento, 41 documentos únicos**. Distribución: cuatro
archivos en la raíz, dos en Títol 0, ocho en Títol I y 27 en Títol II.

## Fechas, fase y procedencia

Se verificó el documento «Aprovació Ple»:
https://ayuntamientodevillalonga.sedelectronica.es/preview-document/597a4c54-0aa5-4e76-82ae-8955826e5a32
Su PDF certifica sesión del pleno del **26-09-2022**, expediente **286/2020**,
sobre evaluación ambiental y territorial estratégica ordinaria del plan parcial
de mejora del sector C industrial, homologación modificativa, participación
pública y versión preliminar. El acuerdo aprueba el **trámite de participación
pública y consultas**, no la aprobación definitiva del plan. La firma es del
28-09-2022; la pantalla del documento indica creación 30-mar-2023. Son fechas
con significados diferentes, ninguna prueba la fecha de publicación del plan.

El adaptador extrae el inventario y no interpreta el texto de los PDF. Por ello
no emite `fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob`, fase ni
número de expediente inferidos o fijados como constantes. El acuerdo y la
versión preliminar quedan disponibles mediante sus documentos. El PDF y su
texto están capturados en evidencia para la revisión humana.

## Alcance parcial y geometría

Solo carpetas nominativas de instrumentos en 6.1; actualmente el sector C.
No es un inventario exhaustivo de todo el planeamiento municipal ni un censo
de obras. Se excluyen los visores genéricos, el enlace al registro GVA y el
documento aislado «Publicació Pla». Tampoco se extraen normativa general de
6.2, planes ambientales de 6.3, el documento de obra «Pla obert d'inversions
24-27» de la portada, noticias, contratos ni formularios. No se han verificado
licencias concedidas; ambas operaciones de licencias escriben cero registros.

`geometry_status: unavailable`. El inventario enlaza https://visor.gva.es/visor/
y https://icv.gva.es/va/, sin identificador de capa o geometría vinculada al
instrumento extraído. No se han georreferenciado sus planos PDF ni se han
inventado coordenadas. `publication_ready: false`. La clasificación compartida
lo deja pendiente por falta de referencia de expediente extraída automáticamente;
la existencia del instrumento se acredita con su carpeta y sus documentos.

## Validación reproducible

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- Parser/crawler: `python -m unittest municipio.test_vilallonga -v` — seis pruebas OK.
  Cubren paginación con callback reutilizado, ausencia de progreso, estructura
  perdida, recuentos, agrupación recursiva, conservación de salida ante error,
  fechas ausentes, licencias vacías y restricciones del manifest.
- Extracción real mediante `load_manifest('vilallonga')`,
  `load_portal_adapter(manifest).backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
  Para guardar capturas, `manifest.portal.config['capture_dir']='evidence/live-captures'`.
- Evidencia local: `evidence/proyectos.jsonl`, `evidence/validation.json`,
  HTML/XML del inventario completo, descubrimiento de la sede y PDF de acuerdo.

`schedule.enabled=false`, `geocode.jitter_missing=false` y
`licencias.enabled=false`. Sin cambios compartidos ni dependencias nuevas.
