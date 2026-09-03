# Torre Val de San Pedro — investigación portal ayuntamiento

Municipio: **Torre Val de San Pedro** (`torre-val-de-san-pedro`) — Castilla y León / BOYL (`bocyl`)

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal Liferay (DipSegovia) | https://www.dipsegovia.es/web/ayuntamiento-de-torre-val-de-san-pedro |
| Dominio propio (alias) | https://www.torrevaldesanpedro.es |
| Urbanismo (biblioteca documental) | https://www.dipsegovia.es/web/ayuntamiento-de-torre-val-de-san-pedro/urbanismo |
| Sede electrónica (espublico gestiona) | https://torrevaldesanpedro.sedelectronica.es |
| Tablón de anuncios | https://torrevaldesanpedro.sedelectronica.es/board |
| Transparencia urbanismo | https://torrevaldesanpedro.sedelectronica.es/transparency/3e5646c8-74e2-4464-a4b5-f182833529b5/ |
| Catálogo de trámites | https://torrevaldesanpedro.sedelectronica.es/dossier |
| PLAI JCYL (aprobado) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=40&municipio=206 |
| PLAI JCYL (info pública) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=40&municipio=206 |

## Cómo se listan expedientes / proyectos

### Web DipSegovia (Liferay)

- Página **Urbanismo** con galería de documentos (`IGDisplayPortlet`): carpetas por actuación (modificaciones puntuales, estudios de detalle, expedientes de uso excepcional en suelo rústico, etc.) y PDFs/DOCs enlazados vía `/documents/1702665/...`.
- Enlace embebido al archivo PLAI JCYL (`municipio=206`, `provincia=40`).
- Enlace a transparencia de urbanismo en la sede electrónica.

### PLAI JCYL

- Tabla HTML con instrumentos aprobados: NUM, ED, PORN, etc.
- Documentos descargables vía `openDocumento.do?cDocId=...`.
- Ejemplos: Normas Urbanísticas Municipales, Estudio de detalle 1-2019, Modificación NUM condiciones estéticas.

### Sede espublico

- Tablón de anuncios con tabla HTML (`preview-document/...`); actualmente sin filas urbanísticas visibles en el listado principal.
- Catálogo de trámites en `/dossier` (páginas informativas de licencias).

## Licencias

- No hay dataset público de concesiones con coordenadas.
- El tablón no publica licencias urbanísticas en el momento de la investigación.
- El adapter devuelve páginas informativas de trámites (sede `/dossier`, transparencia urbanismo) como filas de referencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 polígono (Normas Urbanísticas Municipales)
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — 2 polígonos (sectores sin nombre asignado)
  - `urbanismo:plau_cyl_planes_parciales` — 0 features para este municipio
  - Filtro: `n_mun = 'Torre Val de San Pedro'`, `srsName=EPSG:4326`
- **Estrategia:** descarga WFS GeoJSON + enriquecimiento por coincidencia de título/sector en filas PLAI y DipSegovia urbanismo.
- **Limitaciones:** sin visor ArcGIS municipal; tablón/PDF sin enlace GIS por expediente; sectores WFS sin nombre explícito dificultan el match automático.

## Limitaciones generales

- Tablón de anuncios vacío de entradas urbanísticas en el scrape.
- Licencias solo informativas (sin listado de concesiones).
- Geometría parcial vía WFS regional (no parcela/expediente del tablón).

## Referencia técnica

- Adapter: `municipio/adapters/torre_val_de_san_pedro.py` — patrón DipSegovia + espublico + PLAI JCYL + IDECyL WFS (como Ituero y Lama / Bernuy de Porreros).
