# Investigar una entrada territorial y relacionar su asunto

> Copia TODO este archivo en Instructions de Cursor. La UI no lee este path automáticamente.
> Requiere `20261017140000_regional_research.sql`. No sustituirlo por INSERT antiguos.

Investiga exactamente una entrada de Homes, aunque sea planeamiento, normativa, documento,
subasta o anuncio. Queremos explicar qué ocurre en la región y qué le afecta. Guarda siempre
clasificación, evidencia y resultado, también cuando no logres identificar el asunto.
No abras PR, no toques scrapers ni modifiques políticas de actividad/mapas. No inventes hechos.
Si falta SUPABASE_DB_URL/DATABASE_URL o una herramienta, detente y reporta el error.

## 1. Reservar y cargar contexto

La reserva se escribe en Supabase, en `homes.entrada_investigacion_lease`, mediante el helper.
Ejecuta los comandos desde la raíz del checkout que contiene `db/research_asunto.py`, con
`SUPABASE_DB_URL` o `DATABASE_URL` configurada. Pegar este texto en una UI cuyo checkout todavía
no contiene el helper no instala el código: ese checkout debe estar actualizado también.

```bash
# OWNER: cursor:<UUID nuevo por ejecución>
python3 db/research_asunto.py claim --owner "$OWNER" --ttl 600
# Lee proyecto_id y token del JSON devuelto como ID y TOKEN. Si es null, termina.
python3 db/research_asunto.py context --project "$ID"
# Conserva source_hash del contexto como SOURCE_HASH.
python3 db/research_asunto.py renew --project "$ID" --owner "$OWNER" --token "$TOKEN" --ttl 600
# Solo si abandonas sin guardar:
python3 db/research_asunto.py release --project "$ID" --owner "$OWNER" --token "$TOKEN"
```

Genera un owner único `cursor:<UUID>`. Ejecuta `python3 db/research_asunto.py claim --owner "$OWNER"`.
Si devuelve null termina. Conserva proyecto_id, owner y token. Obtén el contexto con
`python3 db/research_asunto.py context --project "$ID"`. Conserva su `source_hash` como SOURCE_HASH. Si la fuente cambia durante la investigación, el guardado se detiene para evitar marcar como procesada una versión que no investigaste.
La selección prioriza fichas visitadas por sesiones humanas del filtro `interesting` existente,
y después viviendas/superficie/actualización. No inventa una ventana de visitas.
Una investigación antigua de proyecto no excluye esta primera clasificación territorial.
Una clasificación territorial procesada no se repite automáticamente hasta cambio de fuente
o revisión solicitada, aunque sea parcial/pendiente. No se descarta ningún tipo por ser norma.
Renueva cada 120s con `research_asunto.py renew --project "$ID" --owner "$OWNER" --token "$TOKEN"`.
Si falla detente; ante abandono usa `release`. No recuperes reservas ajenas ni uses skip.

## 2. Identificar qué es y a qué pertenece

Clasifica tipo_entrada: actuacion, planeamiento, modificacion_normativa, documento, subasta,
tramite, anuncio o pendiente. La clasificación es de esta entrada, no del título inferido.
Identifica el asunto concreto y compara `asuntos_existentes` antes de crear otro.
Tipos de asunto: actuacion, planeamiento, norma, subasta, expediente, documento u otro.

Cada asunto tiene `clave_identidad` estable y verificable: organismo + número oficial de
plan/expediente/subasta; si no hay número, URL oficial canónica del documento/asunto. No uses
un título genérico, un centroide ni una semejanza de nombres para fusionar. Reutiliza EXACTAMENTE
la clave existente cuando haya evidencia de que es el mismo asunto. Los IDs se asignan al guardar.

Usa `padre_ref` solo para pertenencia CONFIRMADA a otro asunto del JSON. Ejemplos:
plan general → modificación → expediente → documento; procedimiento de subasta → anuncio.
Los asuntos raíz tienen padre null; si no conoces el padre no lo inventes: registra el vínculo
pendiente y por qué falta. Un capítulo/plano se vincula a su plan/norma, no se crea como obra.
Si no hay ningún asunto identificable usa asunto_ref null, estado pendiente_identificar y
razon_pendiente; conserva las búsquedas y fuentes. Un tipo conocido no implica identidad conocida.

Otros vínculos son relaciones tipadas: modifica, afecta_a, describe o vinculado_a, con certeza
confirmada o posible y fuente/extracto para cada relación. Las posibles no cambian padres.
No afirmes que un plan afecta a un proyecto concreto sin fuente que lo sitúe en su ámbito.

## 3. Investigar según el tipo

Fuentes oficiales primero: sedes, boletines, PDFs enlazados y documentación primaria; después
promotores y prensa. Abre/lee las fuentes y cita URL específica y extracto breve verificable.

- Actuación: terreno, historia, programa, actores, cifras, tramitación, obras y próximos pasos.
- Planeamiento/norma: cuál es, ámbito, contenido, aprobaciones/publicaciones, modificaciones,
  estado de vigencia acreditado y condiciones que cambian. No confundas aprobación inicial
  con vigencia. Identifica la norma modificada y relaciónala si consta.
- Documento/plano/capítulo: autor/órgano, fecha, expediente y plan de pertenencia; qué aporta
  concretamente y si refleja una propuesta, versión aprobada o modificación. Sigue los enlaces
  al documento matriz para comprender su contexto, no te limites a describir el archivo.
- Subasta: inmueble/bien y localización, procedimiento, órgano, condiciones y fechas; busca
  resultado acreditado, adjudicación, suspensión o cierre. Que pase la fecha no prueba ejecución.
- Trámite/anuncio: qué procedimiento o acontecimiento describe y qué efecto verificable tiene.

Si no encuentras información o todas las fuentes son inaccesibles, guarda el fallback:
estado pendiente_identificar si no resuelves el asunto (o parcial si sí tiene identidad),
razon_pendiente/huecos y busquedas_intentadas con consulta, resultado y URL intentada si existe.
Puedes dejar fuentes vacío en este fallback; no inventes extractos de documentos no leídos.
Este resultado QUEDA PROCESADO y fuera de la cola automática, no se reintenta por estar pendiente.
Solo se reabre por cambio de la fuente original o revisión solicitada explícitamente.
Si faltan fuentes accesibles guarda lo encontrado y el hueco. No conviertas una búsqueda sin
resultado en una afirmación de inexistencia, vigencia, adjudicación o ejecución.

## 4. Relato, datos y hallazgos

Resumen largo en español: identidad y contexto, cronología fechada, contenido, ámbito afectado,
estado actual y qué queda por conocer. No es un resumen de tres líneas; mínimo técnico 400
caracteres, sin rellenar por longitud. Explica cada fecha y su fuente.
Separa cifras vigentes de máximos, rangos, previsiones e históricos anulados. No destaques
anulados como KPIs actuales. No inventes fechas de prensa; fecha null si no consta.
Datos y hallazgos conservan evidencia propia, estado temporal y certeza. No atribuyas un
constructor sin licencia/adjudicación. Marca estimaciones como tales.
`completa` exige identidad y aspectos principales razonablemente documentados; `parcial` si
hay asunto identificado con lagunas relevantes, padre/vínculos pendientes o estado sin resolver;
`pendiente_identificar` si no puede vincularse la entrada con ningún asunto concreto.
No marques completa una subasta cuyo resultado sigue desconocido: parcial con ese hueco.

## 5. JSON de resultado

```json
{
  "proyecto_id": "ID asignado (entrada original)",
  "tipo_entrada": "documento",
  "estado": "parcial",
  "resumen": "Relato extenso con fuentes, contexto y cronología...",
  "huecos": "No se localizó la aprobación definitiva de la versión del plano.",
  "razon_pendiente": null,
  "asunto_ref": "plano",
  "asuntos": [
    {"ref":"plan","clave_identidad":"oficial:organismo:plan-numero","tipo":"planeamiento","titulo":"Nombre oficial del plan","municipio":"Municipio","padre_ref":null,"fuente_url":"https://organismo/plan","extracto":"Nombre/identidad que constan en el documento"},
    {"ref":"plano","clave_identidad":"documento:https://organismo/plano.pdf","tipo":"documento","titulo":"Plano 5 del plan","municipio":"Municipio","padre_ref":"plan","fuente_url":"https://organismo/plano.pdf","extracto":"Cabecera que identifica el plan al que pertenece"}
  ],
  "relaciones": [],
  "busquedas_intentadas": [{"consulta":"Plan en sede oficial","resultado":"documento localizado"}],
  "fuentes": [{"nombre":"Organismo","url":"https://organismo/plano.pdf","fecha":null,"extracto":"Cita breve verificable"}],
  "datos": [{"bloque":"situacion","etiqueta":"Estado","valor":"Versión del plano sin aprobación identificada","confianza":"media","fuente_tipo":"oficial","fuente_url":"https://organismo/plano.pdf","fuente_fecha":null}],
  "hallazgos": [{"titulo":"Versiones","cuerpo":"Explicación extensa del contexto y el hueco, con fuente."}],
  "vinculos_pendientes": []
}
```

Las refs son locales al JSON; los IDs persistentes se resuelven/reutilizan en Supabase.
No copies los ejemplos como hechos. Cada URL/extracto debe corresponder al caso investigado.
Para relaciones: origen_ref, destino_ref, tipo, certeza, fuente_url, extracto.
`padre_ref` genera automáticamente la relación confirmada pertenece_a.
No inventes campos nuevos para sustituir identidad, padres o estado.

## 6. Guardar siempre el resultado

**Destino del JSON: modelo territorial nuevo, no la tabla antigua de investigaciones de proyectos.**
El JSON es la entrada del helper, no un objeto para INSERT directo. El helper lo reparte así:

| Parte del JSON | Destino en Supabase |
|---|---|
| `proyecto_id`, tipo, estado, resumen, huecos y motivo | `homes.entrada_investigacion` |
| `fuentes`, `busquedas_intentadas`, `datos`, `hallazgos`, `vinculos_pendientes` | Columnas JSONB de `homes.entrada_investigacion` |
| `asuntos` y sus claves oficiales | Filas de `homes.asunto`, con UUIDs reutilizados |
| `padre_ref` | `homes.asunto.padre_id` y relación `pertenece_a` confirmada |
| `relaciones` | Filas de `homes.asunto_relacion` |
| `asunto_ref` | Se resuelve al UUID de `homes.entrada_investigacion.asunto_id` |
| Resultado actual por entrada | Puntero en `homes.entrada_investigacion_actual` |

El helper genera hash del payload, metadatos y fecha; recibe request_id/source_hash/owner/token
por argumentos. Al guardar libera la reserva dentro de la misma transacción. No escribe este
formato en `homes.proyecto_investigacion`, `homes.proyecto_dato_extra` ni `homes.proyecto_hallazgo`.
Esas tablas históricas y su lector web se conservan; la web necesita adaptación para presentar
el modelo territorial nuevo. El campo `proyecto_id` conserva el ID de la entrada de origen,
aunque la clasificación resultante sea norma, documento o subasta.

Genera request_id UUID por investigación y consérvalo para reintentos. Guarda el JSON con:
```bash
python3 db/research_asunto.py save --file resultado.json --request-id "$REQUEST_ID" --source-hash "$SOURCE_HASH" --owner "$OWNER" --token "$TOKEN"
```
La salida es `{"investigacion_id": numero}` de `homes.entrada_investigacion`.
El helper valida reserva, IDs/padres y ciclos, guarda todo transaccionalmente y devuelve el id.
Mismo request_id y JSON: mismo id. Contenido distinto con el mismo request_id: error.
No uses el escritor antiguo de proyecto para normas/subastas/documentos. No hagas INSERT manual.
Al acabar informa id, tipo, estado, asunto_id y padre_id disponibles. No inicies otra entrada.
La UI de Cursor la actualiza el usuario copiando estas instrucciones.
