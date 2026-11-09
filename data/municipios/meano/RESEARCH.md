# Meaño — INE 36027, Pontevedra, Galicia

Verificación: 2026-11-09. Adaptador limitado al inventario oficial de planeamiento
municipal de SIOTUGA (Xunta de Galicia). No es un inventario completo de obras ni
un registro de licencias concedidas. Programación, licencias y jitter desactivados.

## Descubrimiento y fuentes

- https://meano.gal/servizos/urbanismo/ — página municipal actual localizada mediante
  búsqueda web. Describe servicios de urbanismo, sin instrumentos individualizados.
  El cliente Python recibió 403; el lector web mostró la descripción. No se convierte
  esa descripción ni los trámites/formularios en registros.
- https://www.concellodemeano.com — dominio antiguo citado por FEGAMP; la petición
  HTTPS falló por certificado con hostname incorrecto. No se desactivó TLS.
- https://concellodemeano.sedelectronica.gal/info.0 — sede oficial localizada por
  búsqueda; no se ha verificado un inventario exhaustivo extraíble de licencias.
- https://siotuga.xunta.gal/siotuga/inventario?inv=1&idconcello=36027 — inventario
  oficial autonómico, HTTP 200; el selector identifica inequívocamente
  `36027 = Meaño`. La consulta inicial con `municipio=36027` sólo abría el formulario;
  el parámetro real `idconcello` se descubrió en el JavaScript público.
- https://siotuga.xunta.gal/siotuga/assets/inventario/controls.min.js?2.5.0 — explica
  las consultas y cómo construir enlaces a los componentes documentales.
- https://siotuga.xunta.gal/siotuga/assets/inventario/query_document.php — POST
  público con `id=36027`, `idclase` y nonce del formulario anónimo. Clases 14
  (general), 13 (desarrollo), 18 (delimitaciones rurales). El nonce no es una
  credencial de usuario. No se utiliza autenticación.
- https://siotuga.xunta.gal/siotuga/assets/inventario/getIOTPU.php — POST con
  `iddoc`, `idp=0`, `lang=gl_ES` y el mismo nonce; contiene municipio, fechas,
  incidencias y todos los grupos/componentes de cada instrumento.

## Resultado observado

| ID SIOTUGA | Instrumento | Aprobación definitiva | DOG | BOP | Documentos |
|---|---|---|---|---|---|
| 22862 | PLAN XERAL DE ORDENACIÓN MUNICIPAL | 1999-12-28 | 2000-02-07 | 2000-01-17 | 73 |
| 28481 | MP PXOM NÚMERO 2 | 2021-12-29 | 2022-01-13 | 2022-03-25 | 46 |
| 22863 | PXOM NO SOLO URBANO DE DENA | 2006-10-05 | 2006-12-22 | 2007-01-11 | 28 |
| 28621 | PEID TANATORIO DE MEAÑO | 2023-03-31 | 2023-05-19 | 2023-12-07 | 44 |

Clase 18 devuelve `null` (sin registros). Se inspeccionó también la clase histórica
16: cuatro instrumentos, excluidos explícitamente de este adaptador. La consulta
territorial `assets/iot/queryIotInv.php` devuelve instrumentos supramunicipales,
como las Directrices de ordenación do territorio; también se excluyen. Las capturas
de descubrimiento permiten revisar esas exclusiones. No se afirma vigencia jurídica
independiente: se preserva la clasificación del inventario y la incidencia de Dena,
«APROBACION DEFINITIVA POR SILENCIO ADMINISTRATIVO.»

Cada instrumento produce un registro estable por ID de SIOTUGA, no uno por PDF.
Se conservan los 191 enlaces, sus títulos y grupos. Los enlaces se reconstruyen
exactamente como hace la interfaz: `filesroot + folder + /documents/ + pathesperado`,
resueltos respecto a SIOTUGA. Los IDs son del registro autonómico, no números de
expediente municipal. La procedencia conserva endpoint y parámetros públicos.
`source=xunta_siotuga`; `proyectos.source=ayuntamiento` es el selector compatible
con el esquema compartido del pipeline, no una atribución municipal del contenido.

Se usa `fecha_aprob` para la aprobación definitiva; DOG, BOP y publicación de
normativa tienen campos separados. `fecha` y `fecha_publicacion` genéricas quedan
null: no se inventa una fecha única ni se confunde con la fecha de extracción.
No se extrae ni se infiere geometría de planos raster/PDF; latitud, longitud y
geometría quedan null y `publication_ready=false`.

## Exhaustividad, actualización y validación

El JavaScript recibe arrays completos y aplica DataTables en el navegador; las
consultas revisadas no tienen paginación del servidor ni límite de registros.
Se recorren todos los elementos de las tres clases seleccionadas y todos los
componentes de cada detalle. Se rechaza una respuesta envolvente en vez de ignorar
un posible `next`. Un cambio de protocolo requerirá revisión. Update hace un
snapshot completo; no utiliza una fecha como cursor ni altera el state_path.
Errores HTTP, respuestas inesperadas, discrepancias de identidad/fechas, cambio
de municipio o detalles sin documentos impiden reemplazar la salida anterior.

Ejecutado con el runtime preinstalado:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_meano -v
```

Seis pruebas correctas: agrupación documental y fechas, ausencia de fechas e
incidencias, arrays completos y rechazo de envolventes/conflictos, rechazo de
identidades/documentación inválidas, conservación de salida ante fallo de red,
y carga del manifest con licencias desactivadas.

Extracción real mediante `load_portal_adapter(load_manifest('meano'))` y
`backfill_proyectos`: 4 registros, 191 documentos. Capturas JSON reales del
inventario y detalles en `evidence/live-*.json`; salida en
`evidence/proyectos.jsonl`; resumen con `live_records`, `source_urls`, limitaciones
y comprobaciones en `evidence/validation.json`. Un PDF por instrumento descargado
con HTTP 200 y firma `%PDF`: `0819no001.pdf`, `28481no001.pdf`, `22863no001.pdf`,
`28621nu001.pdf`. El resto de enlaces se conserva sin afirmar disponibilidad ni
lectura integral de sus contenidos. Evidencia local, fuera de los cuatro archivos
fuente solicitados, no destinada a commit.

La anotación compartida de entidades devuelve cuatro categorías desconocidas:
son instrumentos urbanísticos, no se afirma una tipología de edificio residencial.
Cobertura municipal parcial, sin licencias concedidas, obras generales, historial
completo, geometría verificada ni publicación habilitada.
