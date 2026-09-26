# Gavilanes — investigación portal ayuntamiento

**Municipio:** Gavilanes (provincia Ávila, Castilla y León)  
**Fecha:** 2026-09-17  
**BOCYL (referencia):** 1 aviso  
**INE:** 05082 | **PlanPublica:** provincia=05, municipio=082

## Resumen

Gavilanes dispone de **web WordPress** (`www.gavilanes.es`) orientada a turismo y noticias locales, sin sección de urbanismo. La gestión administrativa pasa por la **sede electrónica espublico gestiona** (`gavilanes.sedelectronica.es`). El planeamiento urbanístico está centralizado en **PlanPublica / IDECyL** (Junta de Castilla y León): el municipio carece de PGOU propio y aplica **NSAP provinciales** de Ávila.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web municipal | https://www.gavilanes.es | WordPress; 9 páginas estáticas, sin urbanismo |
| Sede electrónica | https://gavilanes.sedelectronica.es/info | Redirige desde raíz |
| Tablón de anuncios | https://gavilanes.sedelectronica.es/board | **Vacío** (0 filas, sep 2026) |
| Catálogo de trámites | https://gavilanes.sedelectronica.es/dossier/.0 | ~76 KB HTML; UUIDs embebidos en JS |
| Transparencia | https://gavilanes.sedelectronica.es/transparency/ | Sección 7 «Urbanismo, obras públicas y medio ambiente» (7 docs) |
| PlanPublica — archivo (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=05&municipio=082 | 2 instrumentos |
| PlanPublica — info pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=05&municipio=082 | Sin documentos activos |
| SiuCyL visor | https://idecyl.jcyl.es/siur/index.html?id=05082 | Visor regional |

## 2. Urban planning — expedientes / planeamiento

### Instrumentos vigentes (PlanPublica PLAU)

| Tipo | Subtipo | Fecha | Título | cDocId |
|------|---------|-------|--------|--------|
| PU | SPG | — | SIN PLANEAMIENTO GENERAL | 276911 |
| PU | NSAP | 22/09/1997 | NORMAS SUBSIDIARIAS DE PLANEAMIENTO MUNICIPAL CON ÁMBITO PROVINCIAL | 295481 |

- **SPG:** el municipio no tiene Plan General de Ordenación Urbana propio.
- **NSAP:** normas subsidiarias provinciales de Ávila (Diputación), aplicables en suelo no urbanizable.

### Cómo se listan

- **PlanPublica:** tabla HTML con filas `PU/NSAP`, fechas `DD/MM/YYYY`, enlaces `openDocuIndice.do?cDocId={id}`.
- **IDECyL WFS:** capa `plau_cyl_instrumentos_ambito` con 1 polígono municipal (`c_mun=05082`).
- **Tablón sede:** vacío; sin expedientes urbanísticos publicados.
- **Web WP:** sin contenido de planeamiento.

## 3. Building licenses — tablón, sede, etc.

- **Tablón (`/board`):** sin anuncios de licencias ni urbanismo (sep 2026).
- **Catálogo dossier:** trámites informativos estándar espublico (licencia urbanística, comunicación previa, etc.); UUIDs en HTML embebido, no enlaces `<a>` directos.
- **Transparencia:** sección 7 con documentación de urbanismo (PDFs `preview-document/{uuid}`).
- **No existe** dataset ni visor de licencias concedidas con coordenadas.

## 4. GIS / geometría

| Fuente | URL | Contenido Gavilanes |
|--------|-----|---------------------|
| WFS IDECyL | `https://idecyl.jcyl.es/geoserver/urbanismo/ows` | 1 instrumento SPG (MultiPolygon municipal) |
| WFS sectores | `plau_cyl_sectores` | 0 features |
| WFS planes parciales | `plau_cyl_planes_parciales` | 0 features |
| SiUR | `id=05082` | Visor regional |

**No hay:** visor urbanístico municipal, ArcGIS local, WFS de licencias.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS `plau_cyl_instrumentos_ambito` (polígono municipal SPG, ~29 km²); filtro `c_mun='05082'` o `n_mun='Gavilanes'`.
- **Estrategia:** extraer geometría del instrumento WFS; enriquecer filas PLAU por coincidencia de título; fallback centroide `[40.2614, -4.8723]`.
- **Limitaciones:** sin sectores ni planes parciales; licencias sin GIS; geometría SPG es delimitación municipal completa, no por expediente.

## Limitaciones

- Tablón vacío; sin API ni paginación.
- Web WP sin urbanismo; noticias locales (fiestas, farmacia, etc.).
- Dossier puede redirigir en bucle sin cookie de sesión (`/dossier/.0` más estable).
- PLAI sin documentos activos.
- Sin PGOU municipal; solo NSAP provincial.

## Estrategia adapter

1. **PlanPublica PLAU** → parsear tabla (SPG + NSAP).
2. **IDECyL WFS** → instrumento `plau_cyl_instrumentos_ambito` con geometría.
3. **Tablón sede** → intentar `/board` (vacío esperado).
4. **Páginas informativas** → tablón, transparencia, dossier para licencias.
5. **IDs:** `gavilanes-{lic|proy}-{sha256[:14]}`.
