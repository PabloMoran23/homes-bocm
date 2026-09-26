# Chiclana de la Frontera — investigación portal ayuntamiento

## URLs base y páginas semilla

| Recurso | URL | Acceso CI |
|---------|-----|-----------|
| Web municipal | https://www.chiclana.es | Cloudflare 403 |
| Portal transparencia (WordPress) | https://transparencia.chiclana.es | OK |
| Urbanismo (hub transparencia) | https://transparencia.chiclana.es/obras-publicas-y-urbanismo/ | OK |
| Tablón edictos (ventanilla virtual) | https://ventanillavirtual.chiclana.es/web/tablonEdictos.do?entidad=CHICLANA&idioma=1&opcion=0 | Cloudflare 403 |
| Sede espublico | https://chiclana.sedelectronica.es | Responde «Sede Electrónica Indeterminada» (sin tenant) |
| Tablón anuncios urbanismo (web) | https://www.chiclana.es/delegaciones-y-servicios/urbanismo/tablon-de-anuncios/ | Cloudflare 403 |
| Consulta previa nuevo PGOU | https://www.chiclana.es/delegaciones-y-servicios/urbanismo/consulta-publica-previa-del-nuevo-plan-general-de-chiclana-de-la-frontera/ | Cloudflare 403 |
| SITUA (Junta Andalucía) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | OK |
| BOJA revisión PGOU 2016 | https://www.juntadeandalucia.es/boja/2016/233/19 | OK |

## Cómo se listan expedientes

- **Tablón principal:** ventanilla virtual Java (`tablonEdictos.do`) con filtros por procedencia (Licencias, Planeamiento y Gestión, etc.). Bloqueado por Cloudflare en entorno CI.
- **Transparencia:** WordPress (Ogov Tech) con sección «Obras públicas y urbanismo»; enlaces a documentación PGOU en web municipal (bloqueada) e indicadores PDF en transparencia.
- **Planeamiento:** NNSS vigentes tras sentencias BOJA 2021; revisión PGOU 2016 aprobada parcialmente (BOJA 233/2016); nuevo PGOU en consulta pública previa (web municipal).
- **Licencias:** sin listado tabular público accesible desde CI; trámites vía ventanilla virtual / delegación urbanismo.

## Licencias de obra

- Filtro «Licencias» en tablón edictos ventanilla virtual (no accesible en CI).
- Página trámites urbanismo en web municipal (Cloudflare).
- El adapter incluye páginas informativas de tablón/trámites (patrón Conil/Pozuelo).

## Geometría / visor

- **geometry_status:** partial
- **Fuentes:** SITUA/VITUA (Junta de Andalucía) — planeamiento municipal digitalizado (PGOU/NNSS) por municipio INE 11015; sin enlace expediente↔polígono en tablón municipal.
- **Estrategia:** filas SITUA como metadatos; geocode aplicará centroide municipal + jitter. No hay WFS/ArcGIS municipal con código de expediente del tablón.
- **Limitaciones:** web principal y ventanilla virtual protegidas Cloudflare; sede espublico sin tenant configurado en subdominios probados; transparencia no publica geometrías por expediente.

## Limitaciones

- Cloudflare en `www.chiclana.es` y `ventanillavirtual.chiclana.es`.
- Sede `*.sedelectronica.es` devuelve página indeterminada (no tablón espublico gestiona operativo).
- SITUA compartir planeamiento para 11015 no devuelve filas de instrumentos en scrape estático (visor JSF).
- Convenios urbanísticos en transparencia: texto «No existen convenios…» tras Ley 19/2013.
