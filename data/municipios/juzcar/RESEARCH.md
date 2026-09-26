# Júzcar — investigación portal ayuntamiento

**Municipio:** Júzcar (Málaga, Andalucía)  
**Slug:** `juzcar`  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)  
**INE:** 29089

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.juzcar.es | **Bloqueada** — CloudFront WAF challenge (HTTP 202) en CI |
| Registro instrumentos urbanísticos | https://www.juzcar.es/14513/registros-instrumentos-urbanisticos | **Bloqueada** — mismo WAF; referencia oficial del ayuntamiento |
| Sede espublico (legacy) | https://juzcar.sedelectronica.es | **Inactiva** — mensaje «La Sede Electrónica se encuentra temporalmente inactiva» |
| Tablón espublico | https://juzcar.sedelectronica.es/board/ | **Inactiva** — misma respuesta |
| Sede Diputación Málaga | https://sede.malaga.es/juzcar | **Timeout** — no responde en CI (90 s) |
| BOJA — PGOU definitivo | https://www.juntadeandalucia.es/boja/2020/224/57 | **Operativa** — resolución registro/publicación PGOU (nov 2020) |
| SITUA — PGOU Júzcar | https://ws132.juntadeandalucia.es/situadifusion/pages/planeamientoGeneralCompartir.jsf?… | **Operativa** — consulta planeamiento regional (INE 29089) |
| BOPMA | https://www.bopmalaga.es | **Operativa** — búsqueda avanzada con Turnstile; sin resultados recientes scrapeables para Júzcar |

## Sede electrónica

- **Plataforma actual:** sede agregada Diputación Provincial de Málaga (`sede.malaga.es/juzcar`), con autenticación Cl@ve y carpeta ciudadana.
- **Plataforma anterior:** espublico gestiona (`juzcar.sedelectronica.es`), actualmente desactivada.
- **Consulta expedientes:** requiere identificación; no hay listado público de expedientes urbanísticos fuera del tablón (inactivo).
- **Atención presencial:** C/ Real Fábrica de Hojalata, 1, 29462 Júzcar — tel. 952 183 500.

## Tablón de anuncios

- La sede espublico (`/board/`) responde con página de inactividad; no hay filas HTML scrapeables.
- La sede Diputación Málaga no responde en entorno CI (timeout).
- Los anuncios de planeamiento del ayuntamiento se publican históricamente en **BOPMA** y **BOJA** (p. ej. avance PGOU BOPMA 114/2006 citado en resolución BOJA 2020).

## Licencias de obra

- No hay dataset público de concesiones de obra mayor/menor con coordenadas.
- Trámites vía sede Diputación Málaga (cuando operativa) o presencial en el ayuntamiento.
- Sin tablón activo ni listado histórico público scrapeable en CI.

## Proyectos / planeamiento

- **PGOU vigente:** aprobado definitivamente (Texto Único Subsanado) — publicación BOJA 4 nov 2020 ([BOJA 2020/224/57](https://www.juntadeandalucia.es/boja/2020/224/57)).
- **Registro municipal:** sección «Registros Instrumentos Urbanísticos» en web municipal (bloqueada en CI).
- **SITUA:** planeamiento digitalizado depositado en Delegación Provincial Málaga; accesible por código INE 29089.
- **Anexos BOJA:** resolución, acuerdos CTOTU 2018/2019, normas urbanísticas y fichas (PDFs enlazados desde la página BOJA).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - SITUA (`ws132.juntadeandalucia.es/situadifusion`): visor/documentación del PGOU municipal; sin enlace por código de expediente del ayuntamiento.
  - PRP Málaga / Diputación (`gis.prpmalaga.es`): visores cartográficos provinciales; sin REST accesible desde CI.
  - Web municipal: WAF CloudFront impide acceso a visor o datos geográficos.
- **Estrategia:** los documentos disponibles (BOJA, SITUA) son PDF/raster sin georreferencia embebida ni API WFS por expediente.
- **Limitaciones:**
  - Sedes inactiva/timeout impiden tablón y trámites scrapeables.
  - Sin WFS/GeoJSON por código de expediente.
  - El orquestador aplicará centroide municipio + jitter para coordenadas.

## Limitaciones generales

- Web `juzcar.es` y sede `sede.malaga.es/juzcar` no scrapeables en CI.
- Sede espublico desactivada.
- Sin geometría por expediente.
- BOPMA búsqueda protegida con Turnstile.

## Adapter implementado

- `municipio.adapters.juzcar:JuzcarAyuntamientoAdapter`
- Fuentes: BOJA PGOU (anexos PDF) + SITUA + páginas informativas sede/registro municipal.
- IDs: `juzcar-lic-*` / `juzcar-proy-*` (sha256[:14]).
