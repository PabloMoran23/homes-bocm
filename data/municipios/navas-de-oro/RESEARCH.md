# Navas de Oro — investigación portal ayuntamiento

**Municipio:** Navas de Oro (Segovia, Castilla y León)  
**Slug:** `navas-de-oro`  
**BOCYL:** `bocyl` (1 aviso histórico en cola)

## URLs base y semillas

| Fuente | URL | Notas |
|--------|-----|-------|
| Web municipal (Liferay DipSegovia) | https://www.navasdeoro.es | Tema Segovia11 |
| Urbanismo — galería documental | https://www.navasdeoro.es/urbanismo | NUM, modificaciones puntuales, planos PO* |
| Tablón de anuncios (web) | https://www.navasdeoro.es/tablon-de-anuncios | Enlace a contenidos Liferay |
| Sede electrónica (espublico gestiona) | https://navasdeoro.sedelectronica.es | Tablón `/board`, info pública `/info`, trámites `/dossier` |
| PLAI JCYL (prov. 40, mun. 145) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=40&municipio=145 | ~14 documentos aprobados (NUM, PAU, modificaciones) |
| PLAI información pública | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=40&municipio=145 | Consulta sin documentos activos (sep 2026) |

## Cómo se listan expedientes / planeamiento

- **Planeamiento aprobado:** tabla HTML en PlanPublica JCYL (`searchVPubDocMuniPlau.do`) con enlaces `openDocumento.do?cDocId=…`.
- **Documentación local:** Liferay Document Library en `/urbanismo` — PDFs con `title` + `/documents/2585857/…` (NUM vigentes, MP 1-2015, 2-2015, 3-2015, MP 1-2017 en IP, planos ordenación).
- **Tablón / sede:** tablas HTML en `navasdeoro.sedelectronica.es/board` e `/info` con `preview-document` (misma plataforma que otros municipios CYL espublico).
- **Licencias:** no hay listado público de concesiones; el catálogo de trámites en `/dossier` incluye procedimientos de licencia (páginas informativas).

## Licencias de obra

- Sin dataset ni tablón dedicado a licencias concedidas.
- Trámites urbanísticos vía sede electrónica (catálogo).
- El adapter devuelve páginas informativas de semillas + cualquier fila del tablón que coincida con patrones de licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL GeoServer WFS `urbanismo:plau_cyl_instrumentos_ambito` — polígono ámbito NUM (`n_mun='Navas de Oro'`, 1 feature).
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — 20 sectores con geometría EPSG:4326 (`n_sector`, `n_num_sect`, `url_doc_info`).
  - No hay visor ArcGIS municipal ni enlace expediente→polígono en la sede.
- **Estrategia:** descarga WFS por municipio; enriquecer filas PLAI/urbanismo por coincidencia de título/sector; centroide del polígono.
- **Limitaciones:** instrumentos sin sector WFS no tienen polígono propio; tablón/PDF sin georef; sede a veces lenta o con certificado débil (`insecure_ssl`).

## Limitaciones generales

- Sede `navasdeoro.sedelectronica.es` puede responder lentamente desde entornos cloud (timeout 45–90 s).
- Sin API JSON pública de expedientes; scrape HTML determinista.
- Paginación PLAI estándar JCYL (15 filas/página).
