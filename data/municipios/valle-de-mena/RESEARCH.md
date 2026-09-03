# Valle de Mena — investigación portal ayuntamiento

**Municipio:** Valle de Mena (provincia Burgos, Castilla y León)  
**Fecha:** 2026-09-03  
**BOCYL (referencia):** 2 avisos  
**INE:** 09410

## Resumen

Valle de Mena dispone de **dos webs Drupal** (portal Diputación `valledemena.burgos.es` con tema Toools, y
`www.valledemena.es` con tema medina_theme) más **sede electrónica espublico gestiona**
(`valledemena.sedelectronica.es`). El planeamiento urbanístico vigente (NS históricas + sectores SUNC) está
centralizado en **PlanPublica / SiuCyL** (Junta de Castilla y León). No hay visor urbanístico municipal ni
listado público de concesiones de licencias georreferenciadas.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web Diputación (Toools) | https://valledemena.burgos.es/ | Drupal 10, enlace a sede y PLAU |
| Web ayuntamiento | https://www.valledemena.es/ | Drupal 9 medina_theme |
| Sede electrónica | https://valledemena.sedelectronica.es/info.0 | espublico gestiona (Wicket) |
| Tablón de anuncios | https://valledemena.sedelectronica.es/board/ | Sin licencias urbanísticas recientes |
| Transparencia | https://valledemena.sedelectronica.es/transparency | Sección 7 «URBANISMO» (~209 docs) |
| PlanPublica — archivo aprobado (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=09&municipio=410 | 6 documentos NS |
| PlanPublica — información pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=09&municipio=410 | Sin documentos activos |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=09410 | Mapa interactivo regional |

**Contacto:** Eladio Bustamante 1, 09580 Villasana de Mena · Tel. 947 126 211 · menaonline@valledemena.es

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **NS** (Normas Subsidiarias de Planeamiento Municipal — normativa anterior), varios documentos históricos
  en PlanPublica (1991–1997).
- Sectores **SUNC** (suelo urbano no consolidado) catalogados en WFS IDECyL: 118 polígonos (ej. `SUNC-0.3`).

### Listado PlanPublica (PLAU)

Página HTML con tabla ordenable. Códigos internos: **provincia=09** (Burgos), **municipio=410** (Valle de Mena).

Endpoints:

```
GET https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=09&municipio=410
GET https://servicios.jcyl.es/PlanPublica/openDocumento.do?cDocId={id}
```

Documentos identificados (sep 2026): 6 NS históricas (`cDocId` 277695–277703).

## 3. Building licenses — tablón, sede, etc.

### Tablón de anuncios (`/board/`)

Tabla espublico. Anuncios recientes (2026): cobranza IAE, bolsa de empleo. **Sin licencias de obra** visibles.

### Catálogo de trámites

Varios trámites estándar espublico están **deshabilitados** en esta sede. Activos (sep 2026):

| Trámite | URL |
|---------|-----|
| Solicitud de Licencia de Ocupación | `/catalog/t/b834b3fa-3690-4626-9c92-d82669d6f26f` |
| Solicitud de Certificado o Informe Urbanístico | `/catalog/t/e247f7c3-b1ff-42ef-8b7d-5195c14e9bbf` |

`/dossier/.0` devuelve bucle de redirección; no usable para scrape.

**No existe** dataset ni visor de licencias concedidas con coordenadas.

## 4. CMS / tecnología

| Componente | Stack |
|------------|-------|
| Web Diputación | **Drupal 10** tema Toools (`valledemena.burgos.es`) |
| Web ayuntamiento | **Drupal 9** tema medina_theme (`www.valledemena.es`) |
| Sede electrónica | **espublico gestiona** (Apache Wicket) |
| Planeamiento regional | **PlanPublica** JCyL (Java/JSP) |
| GIS regional | **GeoServer** IDECyL + visor **SiUR** |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS `https://idecyl.jcyl.es/geoserver/urbanismo/wfs` capas `plau_cyl_sectores` (118 polígonos
  SUNC), `plau_cyl_instrumentos_ambito`, `plau_cyl_planes_parciales`; filtro `n_mun='Valle de Mena'`.
- **Estrategia:** ingestar sectores WFS con `geom_geojson`; cruzar códigos `SUNC-x.x` del título con WFS;
  NUM/NS sin sector → polígono ámbito municipal vía `plau_cyl_instrumentos_ambito`.
- **Limitaciones:** licencias y tablón sin GIS; transparencia urbanismo vía AJAX Wicket (no scrapeado);
  SiUR no expone API directa al adapter.

## Limitaciones

- Tablón: ventana corta, sin licencias urbanísticas.
- Catálogo dossier inaccesible (redirect loop).
- Varios trámites de licencia deshabilitados en sede.
- Planeamiento local reducido a NS históricas; geometría principalmente vía sectores SUNC regionales.

## Estrategia adapter

1. **WFS IDECyL** → proyectos con polígono (118 sectores + instrumentos ámbito).
2. **PlanPublica PLAU** → parsear tabla HTML (`doGoBoletin`, `openDocumento.do`).
3. **Tablón sede** → filtrar keywords urbanismo (backup).
4. **Catálogo trámites activos** → licencias informativas (2 páginas `/catalog/t/{uuid}`).
5. **IDs:** `valle-de-mena-{lic|proy}-{sha256[:14]}`.
