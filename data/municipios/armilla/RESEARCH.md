# Armilla — investigación portal ayuntamiento

**Municipio:** Armilla (Granada, Andalucía)  
**Slug:** `armilla`  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)  
**INE:** 18009

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://armilla.es | **Operativa** — WordPress + WPBakery + Download Manager |
| Web (www) | https://www.armilla.es | **503** — WAF Volt ADC; usar dominio sin www |
| Concejalía urbanismo | https://armilla.es/el-ayuntamiento/concejalias/concejalia-de-urbanismo-gobernacion-y-personal/ | Información + enlaces trámites |
| Registro IOU | https://armilla.es/administracion-electronica/tramites/ordenanzas/ordenanzas-planeamiento-urbanistico/ | Tabs: instrumentos, convenios, catalogados |
| Instrumentos planeamiento | .../seccion-de-instrumentos-de-planeamiento-urbanistico/ | **20 PDFs** vía wpdm (estudios de detalle, reparcelación UE-9, etc.) |
| Convenios urbanísticos | .../seccion-de-convenios-urbanisticos/ | 2 PDFs convenio UE-9 |
| Licencias (trámites) | .../licencias-de-obra-y-gestiones-urbanisticas/ | Impresos mod_urb1–6 (formularios) |
| Impresos urbanismo | .../directorio-de-impresos-y-solicitudes/urbanisticos/ | Solicitudes licencias / vía pública |
| Sede electrónica | https://sede.armilla.es | **503** desde CI (WAF); legacy eAdmin |
| Edictos y anuncios | https://sede.armilla.es/portal/noEstatica.do?opc_id=268&ent_id=1&idioma=1 | Tablón legacy eAdmin (inaccesible en CI) |
| Sede espublico | https://armilla.sedelectronica.es | Página "sede indeterminada" — no configurada |
| PGOU (SITUA) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Enlace oficial desde instrumentos IOU |
| Plan vivienda | https://drive.google.com/open?id=10R6GjGSnBxAAN3kTUFx2Hn0_Vrl3LP5d | Google Drive (concejalía urbanismo) |

## Cómo se listan expedientes

- **Planeamiento:** WordPress Download Manager (`data-downloadurl` + slugs `/download/...`). Títulos en `package-title`. Sin API REST pública (wp-json timeout en CI).
- **Convenios:** Misma estructura wpdm en sección dedicada.
- **PGOU:** Enlace a SITUADIFUSION (visor regional Junta de Andalucía); no hay expedientes locales indexados en HTML.
- **Licencias:** Solo formularios descargables (mod_urb); no dataset de concesiones.
- **Edictos:** Portal eAdmin legacy (`noEstatica.do`); estructura distinta a espublico gestiona.

## Licencias de obra

- No hay listado público de licencias concedidas con coordenadas.
- Trámites documentados en web: impresos mod_urb1–6, directorio urbanístico.
- Edictos históricos en sede.armilla.es (cuando accesible).
- Adapter incluye páginas informativas de trámites + intento de scrape edictos legacy.

## Proyectos / planeamiento

| Origen | Contenido |
|--------|-----------|
| IOU instrumentos | ~20 estudios de detalle, reparcelación UE-9, concesión demanial Ramón y Cajal |
| IOU convenios | Convenio gestión UE-9, propuesta Hermanos Quesada |
| SITUADIFUSION | PGOU Armilla (planeamiento general digitalizado) |
| Google Drive | Plan Municipal de Vivienda y Suelo |
| Bienes catalogados | Sección sin descargas wpdm visibles en crawl |

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - SITUADIFUSION / VITUA (Junta de Andalucía): PGOU y planeamiento regional; sin API REST enlazable por expediente municipal.
  - Estudios de detalle: PDFs sin georreferencia en portal.
  - No hay visor urbanístico municipal ArcGIS ni WFS con campo expediente.
- **Estrategia:** no es posible enriquecer `geom_geojson` por expediente. El orquestador aplicará centroide municipio (37.1431, -3.6183) + jitter.
- **Limitaciones:** sede.armilla.es bloqueada (503) desde entornos cloud; www.armilla.es también 503.

## Limitaciones generales

- Sede eAdmin legacy inaccesible en CI (503 WAF).
- `armilla.sedelectronica.es` no es la sede activa (página indeterminada).
- WP REST API lenta/timeout; scrape HTML determinista de páginas semilla.
- Sin listado histórico de licencias concedidas.

## Adapter implementado

- `municipio.adapters.armilla:ArmillaAyuntamientoAdapter`
- Fuentes: crawl wpdm IOU + SITUA PGOU + plan vivienda + trámites informativos + edictos legacy (si accesible).
