# Sueca — investigación portal ayuntamiento

Municipio: **Sueca** (`sueca`) — Comunitat Valenciana, provincia Valencia (INE **46230**). Sin boletín regional asociado en cola.

## URLs base y semillas

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa | https://www.sueca.es | Drupal portalesmunicipales (pathPrefix `/val/`) |
| Urbanisme | https://www.sueca.es/val/seccion/urbanisme | Departament + PDFs (PG, catàleg, directrius) vía tablas DigitalValue |
| Transparencia PGOU | https://www.sueca.es/val/transparencia/pla-general | Pla General / documentación |
| Info urbanística | https://www.sueca.es/val/transparencia/informacio-urbanistica | Enlaces documentación |
| Àmbits EATIM | https://www.sueca.es/val/transparencia/ambits-eatim | Planes parciales / EATIM |
| Tauler anuncis web | https://www.sueca.es/val/listado-titulares/aviso | Listado → `/val/pagina-aviso/...` |
| Seu electrònica | https://carpetaciutadana.sueca.es/ → OpenSIAC6 | Tablón información pública |
| Tablón OpenSIAC | https://carpetaciutadana.sueca.es/opensiac6/informacionpublica/infopublica.action?edictos=1 | Edictos HTML (listaPublicacionesDescripcion + fecha) |
| Trámites sede | https://carpetaciutadana.sueca.es/opensiac6/informacionpublica/tramites_enter.action | Catálogo trámites (licencias vía sede, sin histórico) |
| Visor GVA | https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz | Referencia visual ICV |

**Nota:** `sueca.sedelectronica.es` responde “Sede Electrónica Indeterminada”; la sede operativa es **carpetaciutadana.sueca.es** (OpenSIAC6).

## Expedientes / proyectos

- **Web Drupal:** páginas de área urbanisme y transparencia con PDFs enlazados (`/sites/www.sueca.es/files/...`) y tablas `dvTables` (documentos PG, catàleg, directrius).
- **Anuncios municipales:** rutas `pagina-aviso` desde el tauler (p. ej. consultas públicas de reglamentos; pocos avisos estrictamente urbanísticos en la muestra reciente).
- **OpenSIAC:** índice de publicaciones con `infopublica_ver.action?id=` (p. ej. “AGENDA URBANA DE SUECA”, edictos fiscales filtrados por regex urbanística).
- **ICV WFS:** capa `ms:InventarioSuSuz` — instrumentos de planeamiento con polígonos por municipio (`cod_ine_mun=46230`).

## Licencias de obra

- No hay listado público estructurado de concesiones de licencia (como tablón espublico `/board`).
- Trámites informativos: catálogo OpenSIAC + sección `/val/tramites` en la web.
- Edictos puntuales en tablón OpenSIAC si mencionan licencias/obras (filtro RE_LICENCIA en adapter).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** ICV Terramapas WFS `https://terramapas.icv.gva.es/0702_Planeamiento`, typeName `ms:InventarioSuSuz`, filtro client-side `cod_ine_mun=46230`, `srsName=EPSG:4326`, geometría GML `msGeometry`.
- **Estrategia:** ingestar todos los ámbitos SU/SUZ del inventario ICV como filas `proyectos`; enriquecer filas de tablón/web matching por tokens sector/UE en título.
- **Limitaciones:** OpenSIAC y tauler web no enlazan geometría por expediente; visor municipal no expone API propia (solo documentos PDF). Sin geometría en licencias informativas.

## Limitaciones técnicas

- Charset mixto ISO-8859-1 / UTF-8 en OpenSIAC (decodificación con fallback).
- Paginación WFS ICV grande (paginar `startIndex` en adapter).
- Anuncios web mezclados con cultura/empleo (filtros RE_PROYECTO / RE_BOARD_NON_URBAN).
