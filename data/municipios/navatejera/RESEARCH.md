# Navatejera — investigación portal ayuntamiento

**Entidad:** Navatejera (pedanía, municipio de Villaquilambre)  
**Provincia:** León · Castilla y León  
**Fecha:** 2026-09-26  
**BOCYL (cola):** 1 aviso

## Resumen

Navatejera **no dispone de ayuntamiento propio** ni de código en el archivo PlanPublica de la Junta de CYL como municipio independiente (Wikipedia / verpueblos: pedanía de Villaquilambre, ~8 km al norte de León capital). La gestión urbanística y las licencias corresponden al **Ayuntamiento de Villaquilambre**.

El slug `navatejera` en la cola refleja menciones en BOCYL; el adapter reutiliza el portal municipal de Villaquilambre y filtra contenido vinculado a Navatejera o al ámbito **SUR-01** (estudio de detalle en suelo urbano consolidado del PGOU).

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web municipal (Villaquilambre) | `https://www.villaquilambre.es` | WordPress | Urbanismo, noticias, PDFs SUR-01 |
| Estudio detalle SUR-01 | `https://www.villaquilambre.es/atencion-al-ciudadano/urbanismo/estudio-detalle-sur-01/` | HTML + PDF | Planos y documentación del ámbito (Navatejera / SUC) |
| Planeamiento | `https://www.villaquilambre.es/atencion-al-ciudadano/urbanismo/planeamiento-urbanistico/` | HTML | Enlaces PGOU y actuaciones |
| Licencias | `https://www.villaquilambre.es/atencion-al-ciudadano/urbanismo/licencias/` | HTML | Formularios y trámites |
| Sede electrónica | `https://villaquilambre.sedelectronica.es` | espublico gestiona | Tablón `/board`, trámites `/dossier` |
| PlanPublica CYL (Villaquilambre) | `provincia=24&municipio=241` | HTML tabla | Instrumentos del municipio matriz |
| IDECyL WFS | `https://idecyl.jcyl.es/geoserver/urbanismo/wfs` | GeoJSON | Sectores/instrumentos `n_mun=Villaquilambre` |
| Junta vecinal (referencia) | `http://www.jvnavatejera.es` | — | Dominio inactivo / sin respuesta en CI |

## Expedientes y licencias

- **Tablón:** `villaquilambre.sedelectronica.es/board` — anuncios con expediente y PDF (`preview-document`). En CI la tabla a veces no devuelve filas urbanísticas en la ventana visible.
- **Licencias:** no hay registro histórico georreferenciado; solo páginas de trámite en web y sede.
- **Proyectos:** documentación del **Estudio de detalle SUR-01** (convenio urbanístico, aprobaciones BOCyL 2024, certificados de pleno 2025) y capas WFS del municipio de Villaquilambre asociadas al sector SUR-01.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL `urbanismo:plau_cyl_instrumentos_ambito`, `plau_cyl_planes_parciales`, `plau_cyl_sectores` con `n_mun='Villaquilambre'`
  - Polígonos del sector SUR-01 / instrumentos vinculados en el geoportal regional (sin visor ArcGIS propio de Navatejera)
- **Estrategia:** Heredar consultas WFS del adapter Villaquilambre; filtrar filas SUR-01 y enriquecer con `geom_geojson` cuando el sector coincide.
- **Limitaciones:** Geometría municipal es del término de **Villaquilambre** (incluye otras pedanías); no hay delimitación expediente-a-expediente en tablón. PDFs de planos sin georreferencia embebida. `navatejera.sedelectronica.es` responde “sede indeterminada” (alias no configurado).

## Limitaciones

- Sin web ni sede propia de la pedanía.
- No aparece en el selector PlanPublica como municipio (solo Villaquilambre, código 241).
- Contenido filtrado por “Navatejera” / “SUR-01”; otras actuaciones del término municipal quedan fuera.

## Estrategia adapter

1. Subclase de `VillaquilambreAyuntamientoAdapter` (mismas fuentes).
2. Filtro de proyectos: título/URL con `navatejera` o patrón `SUR-01`.
3. Licencias: trámites informativos del ayuntamiento matriz + anuncios del tablón que citen Navatejera.
4. IDs: `navatejera-{lic|proy}-{sha256[:14]}`; campo `pedania_de: Villaquilambre`.
