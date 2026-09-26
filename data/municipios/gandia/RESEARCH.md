# Gandia — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `gandia` |
| INE | 46131 |
| Provincia | Gandia (València) |
| CCAA | comunitat-valenciana |
| Boletín | DOGV (`dogv`) |

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa (lanzador) | https://www.gandia.es | Operativa — requiere UA navegador |
| Portal ATG (CMS Woden) | https://www.gandia.es/atg/Web_php/ | Operativa |
| Urbanismo | https://www.gandia.es/atg/Web_php/index.php?contenido=subapartados_woden&id_boto=141&lang=1 | Operativa — formularios PDF + enlaces sede |
| Información pública | https://www.gandia.es/atg/Web_php/index.php?contenido=subapartados_woden&id_boto=479&lang=1 | Operativa — tabla HTML expedientes |
| GeoGandia (visor municipal) | http://geo.gandia.org/geognd/ | Operativo — JS ofuscado, sin API REST pública |
| Sede electrónica | https://gandia.sedelectronica.es | Operativa — espublico gestiona |
| Tablón de anuncios | https://gandia.sedelectronica.es/board | Operativa — tabla HTML preview-document |
| Catálogo trámites | https://gandia.sedelectronica.es/dossier | Operativo con cookies de sesión (lento en CI) |
| Consulta expedientes | https://gandia.sedelectronica.es/expedientes | Requiere autenticación |
| Visor GVA (ICV) | https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion | Operativo (referencia) |

## Cómo se listan expedientes

| Tipo | Mecanismo |
|------|-----------|
| Información pública | ATG Woden — tabla HTML con enlaces `formInt&idForm=25&id=...` |
| Planeamiento vigente | ICV WFS `Planeamiento.Zonificacion` filtrado `cod_ine_mun=46131` |
| Edictos / anuncios | Tablón sede — filas HTML con expediente, procedimiento, PDF preview |
| Trámites | Catálogo sede / dossier (sin histórico público de concesiones) |

### Información pública (agosto 2026)

7 expedientes activos, entre ellos:

- Exp. 39900/2022 — Pla de reforma interior Camí La Via
- Exp. 58041/2025 — Programa d'actuació aïllada Els Arcs
- Pla parcial Baix de Santa Anna
- 95a. Modificació puntual Pla General — PRI Marenys de Rafalcaid

## Cómo se publican licencias

- Edictos en tablón sede (BOP/BOPV, subvenciones, autorizaciones)
- Sin dataset histórico de licencias concedidas con coordenadas
- Formularios de licencia/DR en sección urbanismo ATG (G00180, G00136, G00139, etc.)
- Trámites vía sede (requiere identificación para consulta expedientes)

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS: `https://terramapas.icv.gva.es/0702_Planeamiento`
  - TypeName: `Planeamiento.Zonificacion`
  - Filtro municipio: `cod_ine_mun=46131` (7 instrumentos únicos con polígonos)
  - GeoGandia: `http://geo.gandia.org/geognd/` — visor municipal con capas PGOU/parcelas; JS ofuscado sin endpoints ArcGIS identificables
- **Estrategia:** escaneo paginado WFS GeoJSON (~13k features, ~3 min); matching textual título↔`denominaci` (p. ej. «Baix de Santa Anna» → plan parcial ICV)
- **Limitaciones:**
  - Geometría ICV es zonificación PGOU/planes parciales, no parcela catastral ni licencia individual
  - GeoGandia no expone API REST/WFS scrapeable (código JS ofuscado)
  - CQL_FILTER del WFS no funciona en servidor; requiere paginar y filtrar por INE
  - Licencias del tablón no tienen geometría explícita

## Limitaciones generales

- Web gandia.es raíz es lanzador estático; contenido real en `/atg/Web_php/`
- Sede dossier requiere cookie de sesión (JSESSIONID) para evitar timeout
- Tablón mezcla urbanismo con personal, presupuesto, etc. (filtro por regex)
- Sin registro público de licencias concedidas; solo trámites informativos
