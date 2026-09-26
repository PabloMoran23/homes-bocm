# Peñaranda de Bracamonte — investigación portal ayuntamiento

**Municipio:** Peñaranda de Bracamonte (Salamanca, Castilla y León)  
**Código INE:** 37224  
**Fecha:** 2026-08-22  
**BOCYL (referencia):** 3 avisos

## Resumen

Peñaranda de Bracamonte publica urbanismo y licencias en la **sede electrónica espublico gestiona**
(`penarandadebracamonte.sedelectronica.es`). El planeamiento aprobado está indexado en el archivo
**PlanPublica** de la Junta de Castilla y León (provincia 37, municipio 224). La geometría de
sectores, planes parciales e instrumentos está disponible en el **WFS de IDECyL**.

La web corporativa `www.bracamonte.es` (WordPress) no responde desde entornos automatizados
(timeout >60 s); la ingesta usa sede + fuentes autonómicas.

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Tablón de anuncios | `https://penarandadebracamonte.sedelectronica.es/board` | HTML tabla Wicket | Edictos, licencias, empleo público |
| Inicio (extracto tablón) | `https://penarandadebracamonte.sedelectronica.es/info.0` | HTML Wicket | Últimos anuncios (requiere sesión) |
| Catálogo trámites | `https://penarandadebracamonte.sedelectronica.es/dossier.0` | HTML Wicket | ~49 trámites (6 urbanismo/licencias) |
| Transparencia ordenanzas | `https://penarandadebracamonte.sedelectronica.es/transparency/521ee54e-3e69-4570-ba6b-bc90c6c7a883/` | HTML | Ordenanzas y reglamentos |
| PLAI info pública | `https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=224` | HTML | Sin documentos activos (ago 2026) |
| PLAI archivo | `https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=224` | HTML | 3 documentos DSU/modificaciones |
| IDECyL WFS | `https://idecyl.jcyl.es/geoserver/urbanismo/wfs` | GeoJSON WFS | Sectores, planes parciales, instrumentos |
| SiuCyL visor (SiUR) | `https://idecyl.jcyl.es/siur/index.html?id=37224` | Visor web | Mapa interactivo regional |
| Web municipal | `https://www.bracamonte.es` | WordPress | **Inaccesible** (timeout en CI) |

## Tablón de anuncios (`/board`)

Tabla HTML con columnas: Documento, Expediente, Procedimiento, Categoría, Descripción,
Fecha de Publicación (`DD/MM/YYYY`). Enlaces `preview-document/{uuid}` (PDF).

Ejemplo vigente (ago 2026):

- Expte. 1100/2026 — ANUNCIO BOCYL — Procedimiento: Licencias Urbanísticas

## Trámites urbanismo (catálogo sede)

Trámites scrapeables como páginas informativas:

- Declaración Responsable o Comunicación en Materia Urbanística
- Solicitud de Certificado o Informe Urbanístico
- Solicitud de Licencia de Ocupación
- Solicitud de Licencia o Autorización Urbanística

## PlanPublica (archivo aprobado)

Documentos identificados (ago 2026):

| cDocId | Fecha | Título |
|--------|-------|--------|
| 277934 | 02/12/1998 | DSU (delimitación suelo urbano) |
| 294677 | 08/02/2018 | Modificación delimitación suelo Camino de la Ermita, ampliación casco urbano |
| 295331 | 30/11/2018 | Modificación Nº 2 DSU — eliminación trazado calle inexistente |

## Licencias

No hay visor georreferenciado ni dataset abierto de concesiones con coordenadas.

- Anuncios de licencia en tablón cuando se publican edictos (p. ej. ANUNCIO BOCYL).
- Páginas de trámite del catálogo sede como referencia informativa.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — 24 sectores (I1_SUNC, R2_SUR, R1, …)
  - IDECyL WFS `urbanismo:plau_cyl_planes_parciales` — 3 planes parciales
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 instrumento (NUM)
  - Filtro: `CQL_FILTER=n_mun = 'Peñaranda de Bracamonte'`, `srsName=EPSG:4326`
  - SiUR: `https://idecyl.jcyl.es/siur/index.html?id=37224`
- **Estrategia:** ingestar polígonos WFS como proyectos; enriquecer tablón por código de sector en título
- **Limitaciones:** licencias del tablón sin geometría enlazable; no hay visor ArcGIS municipal propio;
  sede requiere `insecure_ssl` (certificado Firmaprofesional); `/info.0` y `/dossier.0` requieren cookie de sesión previa en `/board`

## Limitaciones

- `www.bracamonte.es`: inaccesible (timeout >60 s) — no se usa como fuente activa.
- Certificado SSL sede: emisor no en CA del sistema; adapter usa `insecure_ssl: true`.
- Wicket: URLs con sufijo `.0`; páginas internas redirigen en bucle sin sesión previa en `/board`.
- Tablón muestra ~10 anuncios recientes; histórico requiere búsqueda POST Wicket (no implementado).

## Estrategia adapter

1. Bootstrap sesión en `/board` (cookie `JSESSIONID`).
2. Scrape tabla tablón `/board` + extracto `/info.0`.
3. Catálogo trámites `/dossier.0` filtrado por keywords urbanismo/licencia.
4. WFS IDECyL: sectores + planes parciales + instrumentos con `geom_geojson`.
5. Semillas PLAI Junta CYL (provincia 37, municipio 224) y páginas urbanismo web (fallback).
6. IDs estables: `penaranda-de-bracamonte-{lic|proy}-{sha256[:14]}`.

## Referencia adapters

- Sede espublico + SSL: `pelabravo.py`, `alba_de_tormes.py`
- IDECyL WFS partial: `villaquilambre.py`, `cuellar.py`
