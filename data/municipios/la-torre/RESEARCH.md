# La Torre — investigación portal ayuntamiento

**Municipio:** La Torre (Castilla y León, Ávila)  
**Fecha:** 2026-09-20

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (plantilla Diputación de Ávila) | https://www.latorre.es | CMS estático DipuÁvila 2020 |
| Normas urbanísticas | https://www.latorre.es/ayuntamiento/normas-urbanisticas/ | Índice vacío (sin fichas locales) |
| PLAU JCyL (web) | https://www.latorre.es/ayuntamiento/normas-urbanisticas/plau-junta-de-castilla-y-leon.html | Enlace al archivo PLAU CyL |
| PlanPublica JCyL (aprobado) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=05&municipio=247 | 1 documento: «SIN PLANEAMIENTO GENERAL» (cód. 05247-PU-00000000-277029) |
| SIUR / mapa planeamiento | https://idecyl.jcyl.es/siur/index.html?id=05247 | Visor cartográfico JCyL (INE 05247) |
| Sede electrónica (espublico gestiona) | https://latorre.sedelectronica.es | Trámites y tablón |
| Tablón sede | https://latorre.sedelectronica.es/board | Vacío (`<tbody>` sin filas) |
| Sede trámites | https://latorre.sedelectronica.es/dossier | Catálogo espublico (lento; sin filas urbanismo visibles) |
| BOPA Diputación Ávila | https://www.diputacionavila.es/bops/ | Anuncio licencia ambiental/urbanística (ej. nave almacén Blacha, 2024) |

## Cómo se listan expedientes

- **Web DipuÁvila:** sección normas urbanísticas sin fichas locales; solo enlace a PLAU CyL.
- **PlanPublica JCyL:** tabla HTML con `doOpen(docId, codigo)` — 1 documento vigente (SPG «SIN PLANEAMIENTO GENERAL»).
- **Tablón sede:** HTML espublico estándar; actualmente sin anuncios publicados.
- **Sin visor municipal** de expedientes individuales ni API JSON del ayuntamiento.

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra en web ni sede.
- Información pública de licencias aparece en BOPA/BOP provincial (p. ej. licencia nave almacén Blacha, enero 2024) pero no en tablón scrapeable.
- Estrategia adapter: páginas informativas de sede (tablón + dossier) + tablón si aparecen anuncios.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito` (1 SPG), `urbanismo:plau_cyl_sectores` (0), `urbanismo:plau_cyl_planes_parciales` (0)
  - Filtro: `n_mun = 'La Torre'`
  - Visor SIUR: `https://idecyl.jcyl.es/siur/index.html?id=05247`
- **Estrategia:** ingestar feature WFS del instrumento SPG con `geom_geojson` (MultiPolygon municipio); enriquecer documento PlanPublica por coincidencia de título.
- **Limitaciones:**
  - Municipio sin PGOU aprobado; solo ámbito «sin planeamiento general».
  - Sin sectores ni planes parciales en WFS.
  - Licencias de obra sin georreferencia en portal.
  - Tablón sede vacío.

## Limitaciones generales

- Plantilla DipuÁvila sin REST API; scrape HTML determinista.
- Sede `/dossier` responde muy lento (>50 s); `/board` accesible pero vacío.
- Certificado sede válido; no requiere `insecure_ssl`.
- Boletín regional: BOCYL (`boletin_source_id: bocyl`, 1 entrada en CSV).
