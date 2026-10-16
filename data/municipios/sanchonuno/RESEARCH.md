# Sanchonuño — investigación portal urbanístico

**Municipio:** Sanchonuño (Segovia, Castilla y León)  
**Slug:** `sanchonuno`  
**Boletín:** BOCyL (`boletin_source_id: bocyl`)

## URLs base y semillas

| Fuente | URL | Notas |
|--------|-----|--------|
| Web corporativa | https://www.sanchonuno.es | **Inaccesible** desde red del agente (F5 503 / URL rejected). Plesk/nginx detrás de Volt ADC. |
| Sede electrónica | https://sanchonuno.sedelectronica.es | **espublico gestiona** (Wicket). Tablón, trámites, documentos PDF. |
| Tablón de anuncios | https://sanchonuno.sedelectronica.es/board | Tabla HTML con `preview-document` (PDFs). |
| Catálogo trámites | https://sanchonuno.sedelectronica.es/dossier | ~87 trámites; urbanismo/licencias filtrables por título. |
| PLAU aprobado | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=40&municipio=179 | Archivo planeamiento aprobado JCYL |
| PLAI información pública | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=40&municipio=179 | Expedientes en IP |
| DipSegovia | https://www.dipsegovia.es/web/ayuntamiento-de-sanchonuno | Sin portal Liferay activo (vacío / no publicado). |

**Código PlanPublica:** provincia `40` (Segovia), municipio `179` (Sanchonuño).  
**INE:** `40179`.

## Expedientes / planeamiento

- **Listado:** tablón sede (HTML tabla) + documentos en PDF vía `preview-document`.
- **Planeamiento:** tablas HTML en PlanPublica JCYL (`doGoBoletin` / `openDocumento.do?cDocId=`).
- **Trámites:** páginas informativas del catálogo espublico (licencias urbanísticas, modificaciones de planeamiento, etc.) — no hay registro público de concesiones de licencia de obra en tablón salvo anuncios puntuales.

## Licencias de obra

- No hay dataset ni visor de licencias concedidas.
- **Tablón:** anuncios varios (tributos, elecciones, VPO, concentración parcelaria); licencias urbanísticas puntuales si se publican como anuncio.
- **Trámites informativos:** «Solicitud de Licencia o Autorización Urbanística», DR/comunicación urbanística, ocupación, etc. en `/dossier`.

## Geometría / visor

- **geometry_status:** `available` (vía capas regionales IDECyL; sin visor municipal propio)
- **Fuentes:**
  - WFS GeoServer JCYL: `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_sectores`
  - Filtro: `n_mun = 'Sanchonuño'` (~14 features sectores/instrumentos en prueba)
  - Visor SIUR: https://idecyl.jcyl.es/siur/index.html?id=40179
- **Estrategia:** ingestar features WFS en `backfill_proyectos`; enriquecer filas de tablón/PLAI con `_attach_geometry` consultando sectores por código en título.
- **Limitaciones:**
  - Web ayuntamiento bloqueada (no Liferay/DipSegovia).
  - Geometría no enlazada a expedientes del tablón; solo instrumentos PLAU CyL.
  - Licencias sin polígono (centroide municipio + jitter en geocode).

## Implementación

- Adapter: `municipio/adapters/sanchonuno.py` (patrón Mozárbez / espublico + PLAI + WFS).
- `insecure_ssl: true` en sede (certificado gestiona estándar).
