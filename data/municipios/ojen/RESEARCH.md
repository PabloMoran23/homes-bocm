# Ojén — investigación portal ayuntamiento

**Municipio:** Ojén (Málaga, Andalucía)  
**Slug:** `ojen`  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)  
**INE:** 29076

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.ojen.es | **WAF AWS** — respuesta vacía / challenge (`x-amzn-waf-action: challenge`) en CI |
| Urbanismo (carta servicios S08) | https://www.ojen.es/11039/com1_md1_cd-18257/s08-urbanismo | Misma plataforma Diputación; WAF en CI |
| Impresos / formularios | https://www.ojen.es/6031/impresos-formularios | Formularios PDF urbanismo (aportación documentación, solicitud informes) |
| Sede Diputación Málaga | https://sede.malaga.es/ojen | **Timeout SSL** en CI (>25s handshake) |
| Tablón de anuncios | https://sede.malaga.es/ojen/tablon-de-anuncios/ | HTML tablón Diputación; incluye edictos urbanísticos (p. ej. rectificación descriptiva parcela) |
| Sede espublico (legacy) | https://ojen.sedelectronica.es | **Inactiva** — «Sede Electrónica temporalmente inactiva» |
| Ficha planeamiento Diputación | https://www.malaga.es/delegacionfomento/planeamiento/ficha.asp?mun=29076 | CloudFront/WAF en CI |
| SITUA (Junta) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | **Operativa** — planeamiento por municipio INE 29076 |
| BOJA NNSS 2023 | https://www.juntadeandalucia.es/boja/2023/230/38 | Revisión NNSS + normativa y fichas |
| BOJA fichas S-6…S-9 (2026) | https://www.juntadeandalucia.es/boja/2026/5/19 | Fichas urbanísticas pendientes publicadas |

## Web municipal (Diputación Málaga CMS)

- **CMS:** Plataforma corporativa Diputación de Málaga (`static.malaga.es/municipios/`).
- **Urbanismo (S08):** tramitación de expedientes urbanísticos, planeamiento, parcelaciones, disciplina urbanística; licencias de obra remitidas al servicio de licencias.
- **Formularios:** página de impresos con PDFs rellenables (aportación documentación urbanismo, solicitud documentos urbanísticos).

## Sede electrónica

- **Activa:** `sede.malaga.es/ojen` (Diputación Provincial de Málaga, integración «Málaga Provincia Digital»).
- **Tablón:** listado HTML con fecha, título, expediente, procedimiento y enlace a documento.
- **Carpeta ciudadana:** consulta de expedientes con Cl@ve / certificado; sin listado público histórico.
- **Legacy:** `ojen.sedelectronica.es` (espublico) desactivada.

## Licencias de obra

- No hay dataset público de concesiones con coordenadas.
- Edictos y notificaciones en tablón sede Diputación.
- Formularios e información en web municipal (impresos).

## Proyectos / planeamiento

- **Instrumento vigente documentado:** Revisión de **Normas Subsidiarias** (NNSS), no PGOU definitivo en fuentes consultadas.
- **BOJA 2023:** publicación de revisión NNSS, normativa y fichas urbanísticas.
- **BOJA 2026:** fichas sectores S-6 a S-9 (suelo apto para urbanizar / plan parcial).
- **PGOU:** tramitación histórica (DAE modificada 2018 en BOJA); sin aprobación definitiva referenciada en adapter.
- **SITUA:** consulta de planeamiento general digitalizado para INE 29076.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - PRP Málaga / Diputación: `https://gis.prpmalaga.es/` — cartografía provincial; sin REST por expediente.
  - SITUA/VITUA Junta de Andalucía: zonificación y planeamiento; sin enlace a expediente del tablón.
  - Tablón y BOJA: documentos PDF sin geometría embebida enlazable.
- **Estrategia:** no hay WFS/ArcGIS con campo expediente; el orquestador usará centroide municipio + jitter.
- **Limitaciones:** WAF en web municipal; timeout SSL en sede.malaga.es en CI; sin visor urbanístico municipal con API.

## Limitaciones generales

- Web `ojen.es` bloqueada por AWS WAF en entornos automatizados.
- Sede `sede.malaga.es/ojen` con timeout SSL frecuente en CI.
- Dos sedes: espublico inactiva, Diputación activa pero difícil de scrapear en CI.
- Sin geometría por expediente.

## Adapter implementado

- `municipio.adapters.ojen:OjenAyuntamientoAdapter`
- Fuentes: páginas semilla web + formularios + SITUA + entradas BOJA estáticas + intento tablón sede.
- IDs: `ojen-lic-*` / `ojen-proy-*` (sha256[:14]).
