# Investigar un proyecto importante

> **Cursor Automations:** copia **todo** este fichero en el campo Instructions de la UI.
> El repo es la fuente de verdad; la UI no lee este path automáticamente.

Eres un agente de Cursor. En cada ejecución investigas **exactamente un** proyecto urbanístico y guardas la foto en Supabase (`homes.proyecto_investigacion`, `homes.proyecto_dato_extra`, `homes.proyecto_hallazgo`).

No abras pull request. No toques scrapers ni otros municipios. Si falta `SUPABASE_DB_URL` y `DATABASE_URL`, para y dilo. No inventes cifras.

## 1. Elegir el proyecto

Conéctate con `SUPABASE_DB_URL` o `DATABASE_URL` y lista candidatos sin investigación previa:

```sql
SELECT p.id,
       p.denominacion,
       p.municipio,
       p.expediente_grupo,
       COALESCE(p.num_viviendas_max, p.metric_num_viviendas_max, p.bocm_num_viviendas_max) AS viviendas,
       COALESCE(p.sup_total_m2, p.metric_sup_total_m2, p.bocm_sup_total_m2) AS superficie,
       p.tipo_figura,
       p.fase,
       p.bocm_promotor
FROM homes.proyecto p
WHERE NOT EXISTS (
  SELECT 1 FROM homes.proyecto_investigacion i WHERE i.proyecto_id = p.id
)
ORDER BY
  COALESCE(p.num_viviendas_max, p.metric_num_viviendas_max, p.bocm_num_viviendas_max, 0) DESC,
  COALESCE(p.sup_total_m2, p.metric_sup_total_m2, p.bocm_sup_total_m2, 0) DESC,
  p.updated_at DESC NULLS LAST
LIMIT 20;
```

Quédate con el primero que sea una actuación real (plan parcial, reforma interior, ámbito, sector, promoción). Salta ordenanzas, catálogos y fichas vacías si hay otro candidato mejor en la lista. Si la lista sale vacía, termina: no hay proyectos pendientes.

Lee después la fila completa de `homes.proyecto` y, si existen, trámites, documentos y publicaciones BOCM de ese `proyecto_id`. Eso es el punto de partida, no la foto final. Si el expediente está casi vacío, investiga el proyecto y el terreno a los que apunta el nombre.

## 2. Investigar

Busca en fuentes oficiales y luego en prensa. Queremos saber qué está pasando, qué se va a construir, quién lo impulsa, cuántas viviendas hay y qué ha ocurrido en ese terreno.

Prioridad:

1. Visor o sede del ayuntamiento, boletín oficial, PDF de planeamiento ya enlazado.
2. Memoria o web del promotor.
3. Prensa y notas del ayuntamiento.
4. Foros o comentarios solo si aportan algo concreto. Esos van al cajón, no a una cifra.

Separa siempre la fuente. Si un medio contradice a un documento oficial, guarda la cifra oficial como dato y el recorte en un hallazgo, explicando el conflicto.

El constructor de la obra solo entra como dato si hay licencia, licitación o adjudicación. El promotor, la junta de compensación y el propietario del suelo sí pueden entrar antes.

No conviertas una previsión del promotor en fecha oficial. La confianza de esas fechas es `baja` o `media`, y `fuente_tipo` es `prensa` o `web`.

## 3. Resumen

`resumen` es un relato largo, en español, pensado para leerse en la ficha. No es un párrafo de tres líneas. Tiene que contar:

- qué había en ese terreno y cómo se llegó al proyecto
- la cronología con fechas (aprobaciones, publicaciones, juntas, obras)
- qué se va a construir
- en qué punto está ahora
- qué falta (reparcelación, licencias, otros ámbitos, constructor)
- fechas previstas, marcadas como previsión y con quién las dice

`huecos` lista, en prosa corta, lo que buscaste y no apareció.

Si un dato no es publicable, no lo metas en el resumen.

## 4. Datos

Cada hecho que la web pueda enseñar es una fila. Varias noticias son varias filas de `prensa`. No crees columnas nuevas.

Bloques cerrados: `situacion`, `programa`, `cifras`, `actores`, `prensa`, `cronologia`.

- `clave`: estable y opcional (`nombre_publico`, `num_viviendas`, `sup_total_m2`, `promotor`, `constructor`). Si no hay clave clara, déjala vacía.
- Siempre incluye un dato `bloque: situacion`, `clave: nombre_publico`, `destacado: true`: el nombre con el que la gente reconoce el proyecto (por ejemplo «Ribera del Calderón» o «Madrid Nuevo Norte»), no el código de expediente. El mapa lo pinta encima del resto.
- `etiqueta`: rótulo en español.
- `valor`: texto que se lee en la ficha.
- `valor_numero` y `unidad` si es una cifra (`viviendas`, `m2`, `eur`).
- `confianza`: `alta`, `media` o `baja`.
- `fuente_tipo`: `oficial` (administración o documento primario del promotor), `prensa`, `web`.
- `fuente_nombre`, `fuente_url`, `fuente_fecha` (`YYYY-MM-DD`), `extracto` (cita corta).
- `destacado`: true solo en los pocos KPIs de cabecera (viviendas, superficie, promotor, fase).
- `publicable`: false si no debe salir en la web.
- `orden`: orden dentro del bloque.

## 5. Hallazgos

Todo lo relevante que no quepa en una fila: conflictos entre fuentes, contexto del terreno, rumores, hilos sin cifra ni actor. `titulo`, `cuerpo` (el texto tal cual, no un resumen de una línea), fuente y `nota` interna de por qué no es un dato.

## 6. Guardar

Escribe un JSON y cárgalo en una transacción. Si en el checkout existe `db/save_proyecto_info_extra.py`, úsalo (`python3 db/save_proyecto_info_extra.py --file …`). Si no existe, inserta tú con psycopg en este orden: `proyecto_investigacion` (RETURNING id), luego `proyecto_dato_extra`, luego `proyecto_hallazgo`, y haz commit. No dejes filas a medias.

Forma del JSON:

```json
{
  "proyecto_id": "id de homes.proyecto",
  "estado": "completa",
  "resumen": "relato largo",
  "huecos": "lo que no apareció",
  "datos": [
    {
      "bloque": "cifras",
      "clave": "num_viviendas",
      "etiqueta": "Viviendas",
      "valor": "Hasta 741",
      "valor_numero": 741,
      "unidad": "viviendas",
      "confianza": "alta",
      "fuente_tipo": "oficial",
      "fuente_nombre": "Ayuntamiento",
      "fuente_url": "https://…",
      "fuente_fecha": "2026-01-29",
      "extracto": "cita corta",
      "destacado": true,
      "orden": 0
    }
  ],
  "hallazgos": [
    {
      "titulo": "Cifra distinta en prensa",
      "cuerpo": "texto del recorte",
      "fuente_nombre": "Medio",
      "fuente_url": "https://…",
      "fuente_fecha": "2026-05-06",
      "nota": "Contradice la nota oficial; no sustituye la cifra."
    }
  ]
}
```

`estado` es `completa` si hay relato, cifras principales y actores identificables, aunque falte el constructor. `parcial` si el terreno o el programa siguen opacos.

Al terminar, escribe el id de la investigación y el nombre del proyecto. No lances otra.
