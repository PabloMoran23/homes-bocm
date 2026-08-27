# El Puig de Santa Maria — investigación portal ayuntamiento

**Municipio:** El Puig de Santa Maria (Valencia, Comunitat Valenciana)  
**Slug:** `el-puig-de-santa-maria`  
**INE:** 46104  
**Boletín:** DOGV (`dogv`, 2 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web oficial | https://www.elpuig.es | **Inaccesible** en CI (timeout / SSL) |
| Sede electrónica | https://elpuig.sede.dival.es | **Operativa** — plataforma Dival/Sedipualba (ASP.NET) |
| Tablón de anuncios | https://elpuig.sede.dival.es/tablondeanuncios/ | **Operativa** |
| Tablón RSS | https://elpuig.sede.dival.es/tablondeanuncios/tablon_rss.aspx | Feed RSS determinista (~10 ítems) |
| Catálogo trámites | https://elpuig.sede.dival.es/catalogoservicios.aspx | **Operativa** |
| Urbanismo (catálogo) | https://elpuig.sede.dival.es/catalogoservicios.aspx?area=1835&ambito=1 | 21 trámites URB* |
| URB02 licencia tipo 1 | https://elpuig.sede.dival.es/carpetaciudadana/tramite.aspx?idtramite=18309 | Trámite telemático (certificado) |
| Autoliquidaciones | https://autoliquidaciones.elpuig.es/autoliquidacionesweb/ | Pagos tasas urbanísticas |

## Tablón de anuncios (Sedipualba / Dival)

- **CMS:** ASP.NET Sedipualba (`elpuig.sede.dival.es`), mismo stack que Canals u otros municipios valencianos.
- **Listado:** RSS `tablon_rss.aspx` con título, enlace `anuncio.aspx?id=` y fecha.
- **Documentos:** PDF en `tablondeanuncios/documento.aspx?id=…`.
- **Paginación:** ~10 anuncios en RSS (ago 2026); sin API de histórico completo.

### Ejemplos urbanismo (ago 2026)

| Título | Tipo |
|--------|------|
| Edicto aprobación definitiva modificación puntual 2023_01 ámbito PRI Odenanza 5 Plansmar | Modificación puntual / ordenanza |
| RESOLUCION ALEGACIONES Y REQUERIMIENTO PRESENTACION DOCUMENTACION TAG URBANISMO | Expediente urbanismo |

## Licencias de obra

- No hay dataset público de concesiones de licencia con dirección o coordenadas.
- Catálogo sede con trámites URB01–URB21 (licencias, certificados, declaraciones responsables).
- Presentación telemática obligatoria con certificado digital (Decreto 220/2014).
- Licencias publicadas aparecen como edictos en tablón cuando el ayuntamiento las anuncia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV GVA WFS `terramapas.icv.gva.es/0702_Planeamiento` capa `Planeamiento.Zonificacion`, filtro cliente `cod_ine_mun=46104`.
  - 1–2 polígonos municipales: «NORMAS SUBSIDIARIAS, REVISIÓN» (exp. 19950520).
  - Capa `ms:InventarioSuSuz`: 0 features con geometría para 46104.
  - PGOU homologado 1991 (referencia en trámites URB02); sin visor municipal público enlazado.
- **Estrategia:** muestreo WFS por `startIndex` (offsets 0–14000), merge polígonos por keyword en título (plansmar, PRI, ordenanza, PGOU).
- **Limitaciones:**
  - WFS sin filtro CQL efectivo → paginación costosa (~30 s).
  - Geometría solo a nivel de instrumento de planeamiento (normas subsidiarias), no por expediente del tablón.
  - Web municipal inaccesible; sin visor ArcGIS local detectado.

## Limitaciones generales

- `www.elpuig.es` no responde en entorno CI (timeout).
- Tablón con pocos anuncios recientes; mayoría son personal/empleo público.
- Sin listado público de licencias concedidas con ubicación.
- Trámites urbanísticos solo informativos en sede (sin datos de expedientes abiertos).

## Adapter implementado

- `municipio.adapters.el_puig_de_santa_maria:ElPuigDeSantaMariaAyuntamientoAdapter`
- Fuentes: tablón RSS Dival + seeds ICV GVA WFS + páginas informativas trámites URB*.
- IDs: `el-puig-de-santa-maria-lic-*` / `el-puig-de-santa-maria-proy-*` (sha256[:14]).
