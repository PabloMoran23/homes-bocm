# Doñinos — investigación portal ayuntamiento

**Municipio:** Doñinos de Salamanca (Salamanca, Castilla y León)  
**Código INE:** 37117  
**Fecha:** 2026-09-13  
**BOCYL (referencia):** 1 aviso

## Resumen

Doñinos de Salamanca publica trámites y anuncios en la **sede electrónica espublico gestiona**
(`doninosdesalamanca.sedelectronica.es`). El planeamiento aprobado está indexado en el archivo PLAI
de la Junta de Castilla y León (provincia 37, municipio 117). La geometría de sectores, planes
parciales e instrumento NUM está disponible en el WFS de IDECyL.

La web corporativa `ayto-doninos.com` (OpenCMS) no responde desde entornos automatizados (timeout);
la ingesta usa sede + fuentes autonómicas.

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Tablón de anuncios | `https://doninosdesalamanca.sedelectronica.es/board` | HTML tabla Wicket | Edictos, presupuesto, subvenciones |
| Inicio (extracto tablón) | `https://doninosdesalamanca.sedelectronica.es/info.0` | HTML Wicket | Últimos anuncios (requiere sesión) |
| Catálogo trámites | `https://doninosdesalamanca.sedelectronica.es/dossier.0` | HTML Wicket | ~37 trámites (13 urbanismo/licencias) |
| PLAI info pública | `https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=117` | HTML | Documentación en exposición pública |
| PLAI archivo | `https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=117` | HTML | Planeamiento aprobado |
| IDECyL WFS | `https://idecyl.jcyl.es/geoserver/urbanismo/wfs` | GeoJSON WFS | Sectores, planes parciales, instrumentos |
| Web municipal | `https://ayto-doninos.com` | OpenCMS | **Inaccesible** (timeout en CI) |
| Web vecinal | `https://doninos.es` | HTML estático | Portal del pueblo (no oficial ayuntamiento) |

## Tablón de anuncios (`/board`)

Tabla HTML Wicket con enlaces `preview-document/{uuid}` (PDF). Ejemplos vigentes (2026):

- Anuncio modificación Ordenanza nº 26 (aprobar provisional)
- Anuncios presupuesto, IAE, subvenciones escolares

No hay edictos de licencias urbanísticas recientes en el tablón visible.

## Trámites urbanismo (catálogo sede)

Trámites scrapeables como páginas informativas:

- Solicitud de Licencia o Autorización Urbanística
- Declaración Responsable Obra
- Declaración Responsable o Comunicación en Materia Urbanística
- Solicitud de Certificado o Informe Urbanístico
- Solicitud de Declaración de Ruina
- Licencia de Ocupación / Actividades

## Licencias

No hay visor georreferenciado ni dataset abierto de concesiones con coordenadas.

- Anuncios de licencia en tablón cuando se publican edictos.
- Páginas de trámite del catálogo sede como referencia informativa.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — 20 sectores (Ur-R1, Ur-R4, Ur-R6, UR-R11, …)
  - IDECyL WFS `urbanismo:plau_cyl_planes_parciales` — 10 planes parciales
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 instrumento (NUM, polígono municipal)
  - Filtro: `CQL_FILTER=n_mun = 'Doñinos de Salamanca'`, `srsName=EPSG:4326`
- **Estrategia:** ingestar polígonos WFS como proyectos; enriquecer tablón por código de sector en título
- **Limitaciones:** licencias del tablón sin geometría enlazable; no hay visor ArcGIS municipal propio;
  sede requiere `insecure_ssl` (certificado Firmaprofesional); `/info.0` y `/dossier.0` requieren cookie de sesión

## Limitaciones

- `ayto-doninos.com`: inaccesible (timeout) — no se usa como fuente activa.
- Certificado SSL sede: emisor no en CA del sistema; adapter usa `insecure_ssl: true`.
- Wicket: URLs con sufijo `.0`; páginas internas requieren sesión previa en `/board`.
- Tablón muestra ~8 anuncios recientes; histórico requiere búsqueda POST Wicket (no implementado).

## Estrategia adapter

1. Bootstrap sesión en `/board` (cookie `JSESSIONID`).
2. Scrape tabla tablón `/board` + extracto `/info.0`.
3. Catálogo trámites `/dossier.0` filtrado por keywords urbanismo/licencia.
4. WFS IDECyL: sectores + planes parciales + instrumentos con `geom_geojson`.
5. Semillas PLAI Junta CYL (provincia 37, municipio 117).
6. IDs estables: `doninos-{lic|proy}-{sha256[:14]}`.
