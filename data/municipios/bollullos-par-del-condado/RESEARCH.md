# Bollullos Par del Condado — investigación portal ayuntamiento

## Datos municipio

| Campo | Valor |
|-------|-------|
| Slug | `bollullos-par-del-condado` |
| INE | 21019 |
| Provincia | Huelva |
| CCAA | Andalucía |
| Boletín | BOJA |

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal (October CMS) | https://www.bollullospardelcondado.es |
| Urbanismo | https://www.bollullospardelcondado.es/servicios/urbanismo |
| Ordenanzas urbanísticas | https://www.bollullospardelcondado.es/ayuntamiento/ordenanzas/ordenanzas-urbanisticas-y-uso-del-suelo |
| Sede electrónica (SWAL) | https://sede.bollullospardelcondado.es |
| Sitemap | https://www.bollullospardelcondado.es/sitemap.xml |
| SITUA (PGOU regional) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf |

## Cómo se listan expedientes / proyectos

- **CMS October**: la página de urbanismo enlaza decenas de PDFs en `/storage/app/media/PORTAL DE TRANSPARENCIA/URBANISMO/` y `/storage/app/media/URBANISMO/`.
- Documentos: PGOU 2021-2023 (avance, aprobación provisional/definitiva, EAE), plan parcial sector SURS R-5, convenio UE SURO Camino de San Sebastián, reparcelación UE R1 Andalucía-Carboneras, ordenanzas.
- **Noticias**: sitemap con entradas filtradas por palabras clave (`pgou`, `urban`, `planeam`, `licencia`).
- **SITUA**: visor regional de planeamiento de la Junta de Andalucía; no hay API WFS pública enlazada al portal municipal.

## Cómo se publican licencias

- **Sin listado histórico** de licencias concedidas en formato tabular.
- La sede SWAL (ASP.NET) tiene menú «Tablón de Anuncios» (código 1007) pero requiere autenticación/postback; no es scrapeable sin sesión.
- El dominio `bollullosparcondado.sedelectronica.es` (espublico) devuelve «Sede Electrónica Indeterminada».
- Trámites de licencia/obra se gestionan vía sede; solo páginas informativas en el adapter.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - SITUADIFusión (ws132.juntadeandalucia.es): visor de consulta PGOU regional; sin WFS/REST público por expediente municipal.
  - IDEAndalucía GeoServer SITUA: endpoints WFS no accesibles desde el entorno del agente.
  - Portal municipal: solo PDFs de planeamiento sin coordenadas ni visor ArcGIS.
- **Estrategia:** el orquestador aplicará centroide municipal + jitter.
- **Limitaciones:** documentación exclusivamente en PDF; sede sin tablón público; sin enlace visor→expediente.

## Limitaciones generales

- Sede SWAL con tablón protegido (no espublico gestiona).
- Sin API REST del blog October CMS expuesta.
- Paginación de noticias vía sitemap (solo URLs con keywords urbanísticas).
