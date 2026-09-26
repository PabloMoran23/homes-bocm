# Almonaster la Real — investigación portal ayuntamiento

## Datos municipales

| Campo | Valor |
|-------|-------|
| Slug | `almonaster-la-real` |
| INE | 21004 |
| Provincia | Huelva |
| CCAA | Andalucía |
| Boletín | BOJA (`boja`) |
| Entradas BOCM/BOJA | 1 |

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.almonasterlareal.es |
| Urbanismo | https://www.almonasterlareal.es/es/areas-tematicas/urbanismo/ |
| PGOU | https://www.almonasterlareal.es/es/areas-tematicas/urbanismo/pgou/ |
| Sede electrónica | https://almonasterlareal.sedelectronica.es/info.2 |
| Gobierno abierto | https://www.almonasterlareal.es/es/gobierno-abierto/ |
| Publicaciones oficiales | https://www.almonasterlareal.es/es/ayuntamiento/publicaciones-oficiales/ |

## CMS / tecnología

- **OpenCms / SAGA Suite** con tema Diputación de Huelva (`com.saga.sagasuite.theme.diputacion.huelva.base`, skin-8).
- Documentos en galerías OpenCms: `/export/sites/almonaster/es/.galleries/areas-tematicas/Urbanismo/`.
- **Certificado SSL inválido** en `www.almonasterlareal.es` → requiere `insecure_ssl: true`.

## Proyectos / planeamiento

El municipio publica muy poca documentación urbanística online:

1. **PGOU** — página con dos archivos ZIP descargables:
   - `LOUA.zip` — Memoria completa, planos PDF adaptación suelo urbano, planos PDF usos globales.
   - `ORDENACION-ESTRUCTURAL-SNU.zip` — Ordenación estructural SNU.
2. No hay subsecciones de planes parciales, modificaciones PGOU ni estudios de detalle (a diferencia de municipios vecinos como Aljaraque).
3. **SITUA** (Junta de Andalucía): consulta genérica de planeamiento — sin geometría scrapeable por expediente.
4. **Tablón Diputación Huelva** (`sede.diphuelva.es`): sin listado público filtrable por INE 21004.
5. **Sede propia** (`almonasterlareal.sedelectronica.es`): responde con redirect pero timeout frecuente desde datacenter; sin histórico de expedientes scrapeable.

Estrategia del adapter: crawl HTML de semillas urbanismo/PGOU → extraer enlaces `.pdf` y `.zip` en galerías SAGA + enlace SITUA + página PGOU como metadato.

## Licencias de obra

- No hay listado público de licencias concedidas.
- La sección urbanismo muestra contacto del **Servicio de Vías y Obras** (tel. 959 14 30 03).
- Trámites vía sede electrónica propia (espublico/GSede); sin scraping de concesiones.
- Adapter devuelve páginas informativas (urbanismo, sede, PGOU) como filas `licencias.jsonl` con `min_rows: 0`.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** No hay visor urbanístico municipal, ArcGIS, WFS ni GeoJSON en datos abiertos.
- **SITUA:** enlace genérico a planeamiento de Andalucía; no expone polígonos por expediente vía API pública scrapeable.
- **Limitaciones:** Solo documentos ZIP/PDF sin georreferenciación; sede sin histórico público; SSL inválido en web principal.

El orquestador aplicará centroide municipal + jitter (`centroid: [37.8725, -6.7856]`).

## Limitaciones generales

- Portal con contenido urbanístico mínimo (2 ZIP en PGOU).
- Certificado SSL caducado/inválido.
- Sede electrónica con conectividad intermitente desde el agente.
- Sin tablón de edictos urbanísticos scrapeable por municipio.
