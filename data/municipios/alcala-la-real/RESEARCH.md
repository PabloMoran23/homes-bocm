# Alcalá la Real — investigación portal ayuntamiento

Municipio: **Alcalá la Real** (`alcala-la-real`), provincia Jaén, Andalucía. INE **23003**.

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal | https://alcalalareal.es/ |
| Urbanismo y Patrimonio | https://alcalalareal.es/urbanismo-y-patrimonio-municipal/ |
| Sede electrónica (espublico gestiona) | https://alcalalareal.sedelectronica.es/ |
| Tablón de anuncios | https://alcalalareal.sedelectronica.es/board |
| Transparencia — Obras y Urbanismo | https://transparencia.alcalalareal.es/obras-publicas-y-urbanismo/ |
| Consulta expedientes (login) | https://alcalalareal.sedelectronica.es/expedientes |
| SITUA (Junta) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf |

## Cómo se listan proyectos / planeamiento

- **CMS:** WordPress en `alcalalareal.es` (tema propio, plugins MEC/LayerSlider).
- La sección **Urbanismo y Patrimonio Municipal** agrupa por bloques `<h3>`:
  - PGOU vigente (texto refundido, planos T1–T4, zonificación, EIA, etc.) — cientos de PDFs en `wp-content/uploads/`.
  - **Instrumentos de desarrollo** (planes parciales Llano de Mazuelos, modificaciones).
  - **Plan Parcial NS-2.1** — información pública, exp. **9598/2022**, aprobación inicial Junta de Gobierno **08/04/2025**.
  - **Plan Parcial S-8** ampliación parque industrial Llano de Mazuelos — aprobación inicial **21/07/2026**, 45 días información pública vía BOP Jaén.
  - **Avance Plan Especial** reforma interior sector **UE-SA7**.
- No hay API JSON ni listado paginado de expedientes abiertos; publicación = página + PDFs.
- **Tablón sede:** HTML tabla (`class_name`, `class_folderCode`, …). En la muestra (~10 filas) **sin** entradas de urbanismo/licencias recientes.
- **Regional:** documentación PGOU/planeamiento consultable en **SITUA** (sin geometría vectorial por expediente municipal).

## Licencias de obra

- Tramitación vía sede y atención presencial (Casa Batmala, c/ General Lastres 13).
- **No** hay dataset ni tablón dedicado con concesiones de licencia identificables (tablón general sin filas urbanísticas en el scrape).
- Transparencia enlaza al inicio de sede, sin catálogo UUID de “licencia de obra” como en otros municipios espublico.
- El adapter expone **páginas informativas** (tablón, urbanismo, transparencia, consulta expedientes).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - Web municipal: planos PDF sin coordenadas ni servicio WMS/WFS.
  - SITUA: visor documental PGOU/planeamiento (Junta), **no** devuelve polígono por código de expediente del ayto.
  - Sede `/transparency` y consulta expedientes: requieren sesión o timeout SSL frecuente; sin capa GIS pública.
  - No se localizó visor ArcGIS, GeoJSON en datos abiertos ni WFS municipal (Jaén/Diputación) con enlace a exp. 9598/2022.
- **Estrategia:** el orquestador usará centroide municipal + jitter (`centroid` en manifest).
- **Limitaciones:** solo PDFs; tablón sin anuncios urbanísticos recientes; geometría de ámbito no publicada en portal.

## Limitaciones generales

- Tablón sede: pocas filas, sin urbanismo en el momento del scrape.
- SSL de `/transparency` en sede puede tardar o hacer timeout (>120 s).
- Volumen alto de PDFs PGOU (planos por hoja); el adapter filtra instrumentos y documentos clave (BOP, texto refundido, informes).
