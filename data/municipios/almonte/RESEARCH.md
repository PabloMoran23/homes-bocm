# Almonte — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `almonte` |
| INE | 21001 |
| Provincia | Huelva |
| CCAA | Andalucía |
| Boletín | BOJA (`boja`) |

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.almonte.es |
| Urbanismo | https://www.almonte.es/es/servicios/urbanismo/ |
| Consulta pública | https://www.almonte.es/es/servicios/participacion-ciudadana/consulta-publica/ |
| PGOU (Google Drive) | https://drive.google.com/open?id=0BylSYtrz3wPKVWpEam93RUFZOGs |
| PGOU (web) | https://www.almonte.es/es/ayuntamiento/PGOU/ |
| Descargas / PGOU | https://www.almonte.es/es/descargas/ |
| Ordenanzas urbanismo | https://www.almonte.es/es/ayuntamiento/ordenanzas/ (#urbanismo-vivienda-y-medio-ambiente) |
| SAC / impresos urbanismo | https://www.almonte.es/es/servicios/servicio-de-atencion-al-ciudadano/ |
| Modelos urbanismo | https://www.almonte.es/es/ayuntamiento/impresos-y-modelos-administracion-electronica/ |
| Sede electrónica | https://almonte.sedelectronica.es/info.0 |
| Tablón Dip. Huelva | https://sede.diphuelva.es/opencms/system/modules/gsede/elements/contenido/TablonAnuncios.jsp |
| SITUA (Junta) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf |
| VITUA (Junta) | https://www.juntadeandalucia.es/institutodeestadisticaycartografia/visores/VITUA/ |

## CMS y formato de datos

- **Web corporativa:** OpenCms / **SAGA Suite** con skin `com.saga.sagasuite.theme.diputacion.huelva.base` (plataforma Diputación de Huelva), igual que Aljaraque/Moguer.
- **Expedientes / planeamiento:**
  - **Consulta pública:** bloques `<h3>` con título del expediente + enlaces PDF en galerías `/export/sites/almonte/es/.galleries/otros/documentos-consulta-publica/` y `/Documentos/`.
  - **PGOU:** carpeta pública en Google Drive enlazada desde web; planos en PDF/PLT sin API.
  - **Ordenanzas URB/01–09:** PDFs en galería `documentos-ordenanzas/ordenanzas-generales-urbanismo-vivienda-y-medio-ambiente/`.
- **Licencias:**
  - Enlaces a portales internos `http://195.55.65.234:8889` (consulta) y `http://80.28.254.234:8889/` (descargas) — **no accesibles** desde internet (timeout).
  - Formularios DR/comunicación previa en impresos SAC (PDF estáticos).
  - Sede `almonte.sedelectronica.es` no responde en el entorno del agente (timeout); trámites requieren autenticación.
- **Tablón provincial:** sede Diputación Huelva (GSede) sin API pública filtrable por municipio.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - PGOU Google Drive: documentación raster (PDF/PLT), sin WFS/ArcGIS REST.
  - Consulta pública: PDFs de expedientes sin coordenadas embebidas.
  - Portales licencias (IPs internas): inaccesibles; probablemente aplicación municipal sin geometría pública.
  - SITUA/VITUA Junta: planeamiento general digitalizado; no enlaza expedientes individuales del ayuntamiento.
  - Diputación Huelva: sin capa WFS de expedientes por INE 21001.
- **Estrategia:** metadatos de PDFs y consultas públicas; orquestador aplica centroide municipal + jitter (`centroid: [37.2626, -6.5167]`).
- **Limitaciones:** sin visor urbanístico municipal público; licencias en red interna del ayuntamiento; sede propia inalcanzable para scrape.

## Licencias

Sin listado histórico público accesible. Fuentes informativas:

- Comunicación previa: `/export/sites/almonte/es/ayuntamiento/impresos-y-modelos-administracion-electronica/Urbanismo/COMUNICACION-PREVIA.pdf`
- DR obra mayor/menor y ocupación: misma carpeta Urbanismo en impresos SAC.
- Urbanismo → pestaña Planeamiento: enlaces a portales internos de licencias (no públicos).
- Sede electrónica: trámites sin histórico scrapeable.

## Limitaciones generales

- Portales de licencias en IPs privadas/internas (195.55.65.234, 80.28.254.234).
- Sede `almonte.sedelectronica.es` timeout desde datacenter CI.
- Certificado SSL de `www.almonte.es` válido (no requiere `insecure_ssl`).
- Consulta pública con entradas históricas (algunas de 2018); sin paginación dinámica.
