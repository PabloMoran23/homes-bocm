# Benidorm — investigación portal ayuntamiento

Municipio: **Benidorm** (`benidorm`) — Alicante, Comunitat Valenciana. INE `03031`. Boletín: DOGV.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal (Drupal 11) | https://www.benidorm.org/es |
| Concejalía Urbanismo | https://www.benidorm.org/es/ayuntamiento/concejalias/urbanismo |
| Información pública | https://www.benidorm.org/es/ayuntamiento/concejalias/urbanismo/planeamiento-y-gestion/informacion-publica |
| Instrumentos de ordenación | https://www.benidorm.org/es/ayuntamiento/concejalias/urbanismo/planeamiento-y-gestion/instrumentos-de-ordenacion |
| PGMO / plan general | https://www.benidorm.org/es/ayuntamiento/concejalias/urbanismo/arquitectura/plan-general |
| Obras — información pública | https://www.benidorm.org/es/ayuntamiento/concejalias/obras/ingenieria/informacion-publica-ingenieria |
| Ordenanzas urbanísticas | https://www.benidorm.org/es/pagina/ordenanzas-urbanisticas |
| Archivo urbanismo (2014–2019) | https://www.benidorm.org/es/pagina/urbanismo → pro.benidorm.org |
| Sede electrónica | https://sede.benidorm.org/inicio |
| Tablón de anuncios | https://sede.benidorm.org/eAdmin/Tablon.do?action=verAnuncios&tipoTablon=1 |
| Transparencia | https://www.benidorm.org/es/transparencia |
| Descargas PDF | https://contenidos.benidorm.org/sites/default/files/descargas/ |
| ICV GVA visor | https://visor.gva.es/visor/?idioma=es |

## Expedientes / planeamiento

- **Drupal 11 benidorm.org:** árbol extenso bajo `/es/ayuntamiento/concejalias/urbanismo/` con ~100+ páginas de información pública (PRI hoteleros, estudios de detalle, modificaciones PGMO, convenios expropiatorios, PAI sector PP-11, etc.). Cada página tiene `<h1>` + enlaces PDF a `contenidos.benidorm.org`.
- **Obras/Ingeniería:** proyectos de urbanización, encauzamientos, IP ingeniería civil.
- **pro.benidorm.org:** subdominio legacy con archivos 2014–2019; **timeout desde CI** (30s+).
- **contenidos.benidorm.org:** PDFs accesibles por URL directa (HTTP 200); raíz del dominio devuelve 403.
- Sin JSON:API pública ni listado RSS de expedientes.

## Licencias

- **Sede tablón** (`sede.benidorm.org/eAdmin/Tablon.do`): referenciado en transparencia; **timeout desde CI** (sin respuesta en 15–30s).
- **Trámites informativos:** `/es/ayuntamiento/concejalias/urbanismo/administracion-urbanistica/solicitud-permiso-obras` — formularios URBM (obra mayor/menor, demolición, actividad, etc.) en PDF.
- No hay dataset público de licencias concedidas con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV GVA WFS: `https://terramapas.icv.gva.es/0702_Planeamiento` — capa `InventarioSuSuz`, `cod_ine_mun=03031` (37 polígonos SUZ/planes parciales Benidorm). Salida GML3 `srsName=EPSG:4326`.
  - Visor GVA (web): sin query REST por código de expediente enlazable.
  - No visor urbanístico municipal público con API (pro.benidorm.org caído/timeout).
- **Estrategia:** ingestión WFS como filas `icv_wfs`; enriquecimiento por keywords en título (PP, sector, PRI) contra polígonos WFS.
- **Limitaciones:** polígonos de planeamiento agregado (SUZ/PP), no delimitación por expediente/PRI individual; sede tablón inaccesible desde CI; licencias sin georef.

## Limitaciones generales

- `sede.benidorm.org` y `pro.benidorm.org` no accesibles desde el entorno del agente (timeout).
- `contenidos.benidorm.org` solo vía URLs directas a `/sites/default/files/descargas/`.
- Sin re-parse DOGV en este adapter.
