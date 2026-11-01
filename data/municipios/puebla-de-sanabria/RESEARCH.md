# Puebla de Sanabria — investigación portal ayuntamiento

## URLs base y semillas

| Fuente | URL |
|--------|-----|
| Web municipal | https://www.pueblasanabria.com/ |
| Trámites (PDF licencias) | https://www.pueblasanabria.com/ayuntamiento/tramites.html |
| Sede electrónica | https://puebladesanabria.sedelectronica.es/ |
| Tablón de anuncios | https://puebladesanabria.sedelectronica.es/board |
| Información pública sede | https://puebladesanabria.sedelectronica.es/info.0 |
| Catálogo trámites | https://puebladesanabria.sedelectronica.es/dossier.0 |
| PlanPublica CYL (aprobado) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=49&municipio=200 |
| PlanPublica CYL (info pública) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=S&provincia=49&municipio=200 |

## Cómo se listan expedientes / proyectos

- **CMS:** Joomla 4 + plantilla YOOtheme. No hay sección dedicada de urbanismo en la web; la normativa y trámites están en `/ayuntamiento/tramites.html` como PDFs estáticos en `/images/ayuntamiento/`.
- **Tablón (espublico / Wicket):** HTML con tabla y enlaces `preview-document/{uuid}`. Categorías relevantes: «Licencias Urbanísticas», «Urbanismo, obras públicas y medio ambiente». Títulos en atributo `title` del enlace.
- **Planeamiento regional:** PlanPublica lista instrumentos PDF por municipio (código interno `municipio=200`, provincia Zamora `49`).
- **No hay** listado JSON ni API municipal de expedientes de planeamiento.

## Licencias de obra

- Formularios descargables en trámites (licencia de obra, declaración responsable, documentación técnica).
- Concesiones / edictos publicados en tablón bajo procedimiento «Licencias Urbanísticas» (p. ej. rectificación catastral, edictos).
- No hay dataset abierto de licencias georreferenciadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `https://idecyl.jcyl.es/geoserver/urbanismo/wfs` capas `urbanismo:plau_cyl_sectores`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_instrumentos_ambito` filtro `n_mun = 'Puebla de Sanabria'`.
  - PlanPublica enlaza documentación PDF sin geometría embebida.
- **Estrategia:** ingestar polígonos WFS por municipio; enriquecer filas de tablón/PDF por coincidencia de título con sector o instrumento WFS.
- **Limitaciones:** sin visor urbanístico municipal ni WFS por expediente de licencia; edictos del tablón suelen ser PDF sin enlace GIS. Centroide municipal + jitter para licencias sin polígono.

## Limitaciones generales

- Sede espublico requiere sesión cookie (bootstrap en primer GET a `/board`).
- Paginación del tablón limitada a página visible en scrape estático (suficiente para filas actuales de urbanismo).
- SSL estándar en ambos dominios.
