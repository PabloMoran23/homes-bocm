# San Pedro de Rozados — investigación portal ayuntamiento

**Municipio:** San Pedro de Rozados (provincia Salamanca, Castilla y León)  
**Fecha:** 2026-10-16  
**BOCYL (referencia):** 1 aviso  
**INE:** 37291 | **CIF:** P3729300H

## Resumen

El ayuntamiento publica trámites y documentación en **sede electrónica espublico gestiona**
(`sanpedroderozados.sedelectronica.es`). El planeamiento vigente y sectores están en
**PlanPublica / SiuCyL** y **IDECyL WFS**. La web `sanpedroderozados.es` responde con
timeouts frecuentes desde entornos externos. No hay listado público de licencias de obra
concedidas con coordenadas; el tablón publica avisos generales (ordenanzas, electorales, IAE).

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web corporativa | http://sanpedroderozados.es | Timeouts frecuentes; sede es la fuente principal |
| Sede electrónica | https://sanpedroderozados.sedelectronica.es/info | Redirige desde raíz |
| Tablón de anuncios | https://sanpedroderozados.sedelectronica.es/board/ | Tabla HTML + `preview-document/{uuid}` |
| Transparencia | https://sanpedroderozados.sedelectronica.es/transparency | Sección 7 Urbanismo (4 docs) |
| Catálogo de trámites | https://sanpedroderozados.sedelectronica.es/dossier/.0 | ~100 trámites; warm-up con cookie JSESSIONID |
| PlanPublica — archivo aprobado (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=291 | Varios documentos (PU/NUM) |
| PlanPublica — información pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=291 | Consultar IP activa |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=37291 | Mapa interactivo regional |
| Diputación Salamanca (ficha) | https://www.lasalina.es/…&codMunicipio=291 | Enlace «Información Urbanística Municipal» |

**Contacto:** Plaza Mayor, 1 · 37183 San Pedro de Rozados · Tel. 923 344 001 · ayunsanpedro@hotmail.com

## 2. Urbanismo — expedientes / planeamiento

### PlanPublica (PLAU)

Tabla HTML con `doGoBoletin` / `doOpen` y `openDocumento.do?cDocId=…`. Códigos internos:
**provincia=37** (Salamanca), **municipio=291** (San Pedro de Rozados).

Documentos identificados (muestra):

| cDocId | Código | Notas |
|--------|--------|-------|
| 286007 | 37291-PU-20101105-286007 | Publicación BOCYL |
| 294100 | 37291-PU-20170614-294100 | Publicación BOCYL |

### Transparencia — urbanismo

Expediente visible: **autorización de uso provisional en suelo urbanizable** (sector 2B, nave agrícola;
coherente con aviso VisualUrb sep 2024, ref. catastral `37293A501051570000AI`).

### Tablón de anuncios

Contenido actual (oct 2026): ordenanzas (venta ambulante, caminos rurales), avisos electorales,
ITV móvil — sin licencias de obra publicadas.

### Catálogo de trámites

Trámites urbanísticos estándar espublico (licencia urbanística, DR/comunicación, planeamiento,
actuación urbanística, etc.). Páginas informativas; no listan concesiones.

## 3. Licencias de obra

No hay dataset ni tablón con licencias concedidas georreferenciadas. El adapter devuelve:

1. Entradas del tablón si aparecen licencias (actualmente ninguna).
2. Páginas informativas de trámites de licencia del catálogo sede.

## Geometría / visor

- **geometry_status:** available
- **Fuentes:**
  - WFS IDECyL `urbanismo:plau_cyl_sectores` (y capas `plau_cyl_planes_parciales`, `plau_cyl_instrumentos_ambito`)
  - Filtro `n_mun = 'San Pedro de Rozados'`, GeoJSON EPSG:4326
  - SiUR: https://idecyl.jcyl.es/siur/index.html?id=37291
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enlazar sectores citados en títulos (p. ej. «sector 2B») vía query puntual a `plau_cyl_sectores`.
- **Limitaciones:** licencias sin GIS; web corporativa sin visor propio; expedientes en PDF en transparencia sin geometría embebida.
- **Límite municipal (geocode):** IGN OGC API no devuelve ficha para el nombre exacto; el manifest usa contorno OSM (Nominatim) en `geometry.validation.municipal_boundary`.

## 4. Limitaciones técnicas

- Sede requiere cookie `JSESSIONID` (warm-up `/board/` o `/info`).
- Certificado sede: wildcard `*.sedelectronica.es`; adapter usa `insecure_ssl: true` si falla verificación CA.
- `sanpedroderozados.es` HTTP sin respuesta fiable en scraping remoto.
