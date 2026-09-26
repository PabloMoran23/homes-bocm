# Benaguasil — investigación portal ayuntamiento

**Municipio:** Benaguasil (Valencia, Comunitat Valenciana)  
**Slug:** `benaguasil`  
**INE:** 46051  
**Boletín:** DOGV (`dogv`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.benaguasil.es | **Intermitente** — Drupal (x-drupal-cache); timeout frecuente desde CI |
| Planeamiento municipal | https://www.benaguasil.es/es/pagina/planeamiento-municipal | PDFs PGOU/planos (mar 2025); timeout CI |
| Sede Dival (Sedipualba) | https://benaguasil.sede.dival.es | **Operativa** — ASP.NET Dival |
| Tablón de anuncios | https://benaguasil.sede.dival.es/tablondeanuncios/ | **Operativa** |
| Tablón RSS | https://benaguasil.sede.dival.es/tablondeanuncios/tablon_rss.aspx | Feed RSS determinista |
| Catálogo trámites | https://benaguasil.sede.dival.es/catalogoservicios.aspx | Trámites URB_001–URB_027 (urbanismo) |
| Sede espublico | https://benaguasil.sedelectronica.es | **No operativa** — «Sede Electrónica Indeterminada» |

## Planeamiento municipal (web Drupal)

- Página `/es/pagina/planeamiento-municipal` (04/03/2025): memorias y planos del texto consolidado PGOU (nov 2022).
- Documentos: PDFs en `/sites/www.benaguasil.es/files/wp-content/uploads/2023/01/` (índice planos, zonificación E 1:5000, alineaciones E 1:1000).
- **Listado:** HTML estático con enlaces PDF; sin JSON/API pública.
- **Limitación:** web corporativa con latencia alta / timeout desde runners CI; adapter usa semillas configuradas + reintentos.

## Tablón de anuncios (Sedipualba / Dival)

- **CMS:** ASP.NET Sedipualba (`benaguasil.sede.dival.es`).
- **Listado:** RSS `tablon_rss.aspx` con título, enlace `anuncio.aspx?id=` y fecha.
- **Documentos:** PDF en `tablondeanuncios/documento.aspx?id=…&modo=guardar`.
- **Contenido actual (sep 2026):** edictos organización municipal, oposiciones policía local — **sin filas urbanísticas recientes**.

## Licencias de obra

- No hay dataset público de concesiones de licencia.
- Catálogo sede incluye trámites URB_012 (declaración responsable obras), URB_020/021 (licencias mayor/menor), URB_010 (primera ocupación), etc. — solo páginas informativas, sin histórico.
- Informe urbanístico URB_013 indica consulta gratuita en web del ayuntamiento.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV GVA WFS `terramapas.icv.gva.es/0702_Planeamiento` capa `Planeamiento.Zonificacion`, filtro cliente `cod_ine_mun=46051`.
  - ~2 instrumentos: «HOMOLOGACIÓN MODIFICACIÓN Y PLAN PARCIAL SECTOR "MOLI NOU"» (exp. 20060744), «HOMOLOGACIÓN MODIFICACIÓN SECTORIAL… PLAN PARCIAL SUR-R10» (exp. 20050632).
  - Planeamiento web: PDFs cartográficos sin visor interactivo ni enlace a expediente.
  - `ms:InventarioSuSuz`: sin features para INE 46051.
- **Estrategia:** muestreo WFS por `startIndex` (offsets 0–20000), seeds GVA + matching keyword en título tablón.
- **Limitaciones:**
  - WFS sin CQL efectivo → paginación costosa (~35 s).
  - Geometría del tablón no disponible; solo polígonos de planeamiento homologado.
  - Web Drupal inaccesible en CI impide scrape dinámico de avisos.

## Limitaciones generales

- `benaguasil.sedelectronica.es` no resuelve al ayuntamiento (indeterminada).
- Tablón sin anuncios urbanísticos recientes en RSS.
- Web corporativa con timeouts desde CI.
- Consulta expedientes requiere autenticación en sede.

## Adapter implementado

- `municipio.adapters.benaguasil:BenaguasilAyuntamientoAdapter`
- Fuentes: tablón RSS Dival + seeds ICV GVA WFS + semillas planeamiento web + trámites informativos.
- IDs: `benaguasil-lic-*` / `benaguasil-proy-*` (sha256[:14]).
