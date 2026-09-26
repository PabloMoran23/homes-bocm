# Navaluenga — investigación portal ayuntamiento

## Municipio
- **Nombre:** Navaluenga
- **Provincia:** Ávila (Castilla y León)
- **INE:** 05163
- **Boletín:** BOCYL (`boletin_source_id: bocyl`)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa | https://aytonavaluenga.es | WordPress (tema Astra) |
| Ordenanzas / normativa | https://aytonavaluenga.es/bandos-y-pregones/ | Normas urbanísticas (PDF Dropbox), modificaciones NUM, enlaces BOPA |
| Sede electrónica | https://navaluenga.sedelectronica.es | espublico gestiona |
| Tablón de anuncios | https://navaluenga.sedelectronica.es/board/ | HTML tabla Wicket; `preview-document` UUID |
| PlanPublica JCyL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?provincia=05&municipio=163 | Modificaciones NUM (6 docs) |
| IDECyL WFS | https://idecyl.jcyl.es/geoserver/urbanismo/ows | Capas PLAU CyL filtro `n_mun='Navaluenga'` |

## Cómo se listan expedientes / proyectos

1. **PlanPublica (Junta CYL):** tabla HTML con columnas Libro / Instrumento / Fecha publicación / Fecha acuerdo / Título. Enlaces `doOpen(docId)` → `openDocumento.do?cDocId=…`. Principal fuente de modificaciones de las NUM.
2. **IDECyL WFS:** GeoJSON vía `GetFeature` en capas `plau_cyl_instrumentos_ambito`, `plau_cyl_planes_parciales`, `plau_cyl_sectores`. 26 polígonos (1+1+24).
3. **Web WP:** página `bandos-y-pregones` con PDFs de normas urbanísticas (Dropbox), planos y modificaciones enlazadas al BOPA Diputación Ávila.
4. **Tablón sede:** solo 2 anuncios activos (IAE, limpieza solares); sin expedientes urbanísticos recientes.

## Licencias de obra

No hay listado público de concesiones de licencia. La sede publica trámites genéricos; el tablón no muestra licencias concedidas. El adapter devuelve páginas informativas de trámites (urbanismo, sede, PlanPublica).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — 24 sectores con polígono WGS84
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 polígono ámbito NUM
  - IDECyL WFS `urbanismo:plau_cyl_planes_parciales` — 1 plan parcial
  - Campo enlace: `c_id_sect`, `n_sector`, `n_num_sect`
- **Estrategia:** descarga masiva WFS por municipio; enriquecimiento por coincidencia de título/sector en filas PlanPublica y tablón.
- **Limitaciones:** sin visor municipal propio; PDFs de Dropbox/BOPA sin georreferencia; tablón sin geometría; licencias sin coords.

## Limitaciones generales

- Sede requiere `insecure_ssl` (certificado intermedio).
- Tablón con muy pocos anuncios urbanísticos.
- Normas urbanísticas en Dropbox externo (no scrapeable de forma estable sin API).
- Sin API REST de expedientes en la sede (solo HTML Wicket).
