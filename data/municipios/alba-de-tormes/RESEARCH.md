# Alba de Tormes — investigación portal ayuntamiento

**Municipio:** Alba de Tormes (Salamanca, Castilla y León)  
**Código INE:** 37008  
**Fecha:** 2026-08-09  
**BOCYL (referencia):** 5 avisos

## Resumen

Alba de Tormes publica urbanismo y licencias en la **sede electrónica espublico gestiona**
(`albadetormes.sedelectronica.es`). El planeamiento aprobado y en trámite está indexado en el
archivo PLAI de la Junta de Castilla y León. La geometría de sectores y planes parciales está
disponible en el WFS de IDECyL.

La web corporativa `www.albadetormes.es` no responde desde entornos automatizados (timeout);
la ingesta usa sede + fuentes autonómicas.

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Tablón de anuncios | `https://albadetormes.sedelectronica.es/board` | HTML tabla Wicket | Edictos, licencias, contratación |
| Inicio (extracto tablón) | `https://albadetormes.sedelectronica.es/info.0` | HTML Wicket | Últimos anuncios (requiere sesión) |
| Catálogo trámites | `https://albadetormes.sedelectronica.es/dossier.0` | HTML Wicket | ~27 trámites urbanismo/licencias |
| PLAI info pública | `https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=008` | HTML | Documentación en exposición pública |
| PLAI archivo | `https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=008` | HTML | Planeamiento aprobado |
| IDECyL WFS | `https://idecyl.jcyl.es/geoserver/urbanismo/wfs` | GeoJSON WFS | Sectores, planes parciales, instrumentos |
| Web municipal | `https://www.albadetormes.es` | — | **Inaccesible** (timeout en CI) |

## Tablón de anuncios (`/board`)

Tabla HTML con columnas: Documento, Expediente, Procedimiento, Categoría, Descripción,
Fecha de Publicación (`DD/MM/YYYY`). Enlaces `preview-document/{uuid}` (PDF).

Ejemplo vigente (jul 2026):

- Expte. 1189/2026 — Autorización de uso excepcional en suelo rústico (tenada ganado bovino)

## Trámites urbanismo (catálogo sede)

Trámites scrapeables como páginas informativas:

- Solicitud de Licencia o Autorización Urbanística
- Declaración Responsable o Comunicación en Materia Urbanística
- Licencia de Ocupación de Vía Pública
- Modificación del Planeamiento de Desarrollo / Planeamiento General
- Solicitud de Actuación Urbanística, Certificado o Informe Urbanístico
- Solicitud de Declaración de Ruina

## Licencias

No hay visor georreferenciado ni dataset abierto de concesiones con coordenadas.

- Anuncios de licencia en tablón cuando se publican edictos.
- Páginas de trámite del catálogo sede como referencia informativa.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — 20 sectores (UBZ-R6, UNC-3, UBZ-I2, …)
  - IDECyL WFS `urbanismo:plau_cyl_planes_parciales` — 4 planes parciales
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 instrumento (NUM)
  - Filtro: `CQL_FILTER=n_mun = 'Alba de Tormes'`, `srsName=EPSG:4326`
- **Estrategia:** ingestar polígonos WFS como proyectos; enriquecer tablón por código de sector en título
- **Limitaciones:** licencias del tablón sin geometría enlazable; no hay visor ArcGIS municipal propio;
  sede requiere `insecure_ssl` (certificado Firmaprofesional); `/info.0` y `/dossier.0` requieren cookie de sesión

## Limitaciones

- `www.albadetormes.es`: inaccesible (timeout) — no se usa como fuente.
- Certificado SSL sede: emisor no en CA del sistema; adapter usa `insecure_ssl: true`.
- Wicket: URLs con sufijo `.0`; páginas internas redirigen en bucle sin sesión previa en `/board`.
- Tablón muestra ~10 anuncios recientes; histórico requiere búsqueda POST Wicket (no implementado).

## Estrategia adapter

1. Bootstrap sesión en `/board` (cookie `JSESSIONID`).
2. Scrape tabla tablón `/board` + extracto `/info.0`.
3. Catálogo trámites `/dossier.0` filtrado por keywords urbanismo/licencia.
4. WFS IDECyL: sectores + planes parciales + instrumentos con `geom_geojson`.
5. Semillas PLAI Junta CYL (provincia 37, municipio 008).
6. IDs estables: `alba-de-tormes-{lic|proy}-{sha256[:14]}`.

## Referencia adapters

- Sede espublico + SSL: `pelabravo.py`, `candeleda.py`
- IDECyL WFS partial: `villadangos_del_paramo.py`, `candeleda.py`
