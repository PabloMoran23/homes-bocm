# Águilas — investigación portal ayuntamiento

## URLs base y semillas

| Fuente | URL |
|--------|-----|
| Web municipal | https://www.ayuntamientodeaguilas.org |
| Procedimientos (filtro OBRAS) | https://www.ayuntamientodeaguilas.org/procedimientos |
| Sede electrónica (espublico gestiona) | https://aguilas.sedelectronica.es |
| Tablón de anuncios | https://aguilas.sedelectronica.es/board |
| Catálogo trámites sede | https://aguilas.sedelectronica.es/dossier |
| Transparencia — Obras y urbanismo | https://transparencia.ayuntamientodeaguilas.org/obras-publicas-y-urbanismo/ |
| Transparencia — PGOU | https://transparencia.ayuntamientodeaguilas.org/obras-publicas-y-urbanismo/plan-general-de-ordenacion-urbana/ |
| Transparencia — Convenios urbanísticos | https://transparencia.ayuntamientodeaguilas.org/obras-publicas-y-urbanismo/convenios-urbanisticos/ |

## Listado de expedientes / proyectos

- **Tablón sede:** HTML tabular espublico (`class_name`, `class_folderCode`, `class_folderName`, `class_description`, `class_dateFrom`). Enlaces `preview-document/{uuid}`. Mezcla contratación con filas de urbanismo (p. ej. aprobación inicial urbanización sector plan parcial «Niágara-Isla del Fraile», exp. `554/2014`).
- **Transparencia:** WordPress con secciones estáticas PGOU / convenios; algunos PDFs bajo `/wp-content/uploads/`.
- No hay portal tipo `urbanismo.*.es` con listados IP/PGMO como Cartagena o Lorca.

## Licencias de obra

- No hay dataset histórico de concesiones publicado.
- **Tablón:** edictos puntuales cuando se publican (licencias/actividad mezcladas con otras materias).
- **Web procedimientos:** formularios informativos categoría OBRAS (comunicación previa obra menor, declaración responsable obras, 1ª/2ª ocupación, etc.).
- **Sede:** catálogo de trámites en `/dossier` (sin listado de licencias concedidas).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes probadas:**
  - WFS CARM `SIT_USU_PLA_URB_CARM:plu_ze_37_mun_uso_suelo` con `CQL_FILTER=Municipio='Águilas'` (y variantes) → 0 features.
  - Transparencia / web municipal: sin visor ArcGIS ni WFS municipal enlazado al expediente.
- **Estrategia:** el orquestador usará centroide municipal + jitter (`manifest.centroid`).
- **Limitaciones:** edictos en PDF sin georreferencia; no hay join parcela/expediente en datos abiertos.

## Limitaciones generales

- Tablón muestra ventana corta (~10 anuncios recientes); histórico completo no indexado en HTML público.
- Consulta de expedientes en curso requiere identificación en sede.
- SSL sede: certificado válido; `insecure_ssl: true` por consistencia con otros adapters espublico.
