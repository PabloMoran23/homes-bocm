# Humanes de Madrid — investigación portal ayuntamiento

**Municipio:** Humanes de Madrid (Comunidad de Madrid)  
**Fecha:** 2026-06-25  
**BOCM regional (referencia):** 22 avisos

## Resumen

Humanes de Madrid publica anuncios de urbanismo y licencias en la **sede electrónica espublico gestiona**
(`humanes.sedelectronica.es`). Dispone además de una **carpeta tributaria** CiudadaNET (Infaplic) centrada en
tributos. La web corporativa WordPress (`ayto-humanesdemadrid.es`) aplica captcha anti-bot y no es scrapeable
desde entornos automatizados.

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Tablón de anuncios | `https://humanes.sedelectronica.es/board/` | HTML tabla Wicket | Edictos, licencias urbanísticas, información pública |
| Consulta expedientes | `https://humanes.sedelectronica.es/expedientes` | Cl@ve / SAML | Requiere autenticación; sin listado público |
| Carpeta tributaria | `https://tributoshumanesmadrid.eadministracion.es/` | CiudadaNET JSP | Pagos, domiciliación, informes tributarios |
| Web municipal | `https://ayto-humanesdemadrid.es/` | WordPress | **Bloqueada** (redirect captcha SiteGround) |
| Inicio sede `/info`, `/dossier` | `https://humanes.sedelectronica.es/info` | Wicket | **Redirect loop** (no usable en CI) |

## Tablón de anuncios (`/board/`)

Tabla HTML con columnas:

- Documento → enlace `preview-document/{uuid}` (PDF)
- Expediente, Procedimiento, Categoría, Descripción, Fecha de Publicación (`DD/MM/YYYY`)

Ejemplos vigentes (jun 2026):

- **INFORMACIÓN PÚBLICA. TALLER DE REPARACIÓN DE AUTOMÓVILES** (exp. 188/2026, procedimiento *Licencias Urbanísticas*)
- Aprobaciones definitivas modificación de presupuesto (categoría Anuncios)
- Convocatorias de pleno, selección de personal

Búsqueda en tablón: formulario Wicket POST con campo `description` (tokens de sesión expiran; no implementado).

## Licencias

- Anuncios de licencia / exposición pública en tablón cuando el procedimiento es *Licencias Urbanísticas*.
- No hay dataset abierto ni listado histórico de concesiones con coordenadas.
- Carpeta tributaria CiudadaNET **no** incluye trámites de urbanismo (solo Pagos Online y Solicitudes fiscales).
- Consulta de expedientes en sede requiere Cl@ve.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** No se localizó visor urbanístico ArcGIS, WFS, GeoJSON ni geoportal municipal público.
- **Estrategia:** El orquestador aplicará centroide del municipio + jitter en geocode.
- **Limitaciones:** Solo PDFs en tablón sin georreferenciación; web municipal inaccesible; expedientes tras login.

## Limitaciones

- `ayto-humanesdemadrid.es`: captcha SiteGuard (no scrapeable desde CI).
- Certificado SSL sede: posible emisor no estándar; adapter usa `insecure_ssl: true`.
- Tablón muestra ~10 anuncios recientes; histórico requiere búsqueda Wicket POST.
- `/info` y `/dossier` devuelven redirect infinito (a diferencia de otros municipios espublico).
- Carpeta tributaria eadministracion.es sin urbanismo.

## Estrategia adapter

1. Scrape tabla tablón `/board/`.
2. Páginas informativas de referencia (tablón + consulta expedientes con nota de autenticación).
3. IDs estables: `humanes-{lic|proy}-{sha256[:14]}`.
4. `source: ayuntamiento` en todos los registros.

## Referencia adapters

- Tablón espublico gestiona: `pelabravo.py`, `brunete.py`
- Páginas informativas licencias: `brunete.py`
