# Orcera — investigación portal ayuntamiento

**Municipio:** Orcera (Jaén, Andalucía)  
**Slug:** `orcera`  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)  
**INE:** 23085

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://orcera.es | Operativa — WordPress (UpSolution/WooCommerce) |
| Gobierno y transparencia | https://orcera.es/gobierno-y-transparencia/ | Operativa — ordenanzas urbanísticas (026–048), tasas licencias |
| Formularios | https://orcera.es/formularios/ | Operativa — licencia de obras, primera ocupación, etc. |
| Sede electrónica | https://orcera.sedelectronica.es | Operativa — espublico gestiona |
| Tablón de anuncios | https://orcera.sedelectronica.es/board/ | Operativa — tabla HTML, preview-document |
| Portal transparencia | https://orcera.sedelectronica.es/transparency/ | Operativa — carpeta «URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» (19 docs) |
| Planeamiento Urbanístico | https://orcera.sedelectronica.es/citizen-service/7492b460-b570-4f30-8682-65421df87993 | Operativa — NNSS 1987, Adaptación Parcial, Plan Ordenación, UA, Sector SAU |
| PBOM de Orcera | https://orcera.sedelectronica.es/citizen-service/e8532594-6733-451a-bdf7-038653f71f3f | Operativa — carpeta documental PBOM |
| Declaraciones Responsables | https://orcera.sedelectronica.es/citizen-service/db64886c-26af-41c9-a644-b41c9a1da9b9 | Operativa — trámites DR |
| Consulta expedientes | https://orcera.sedelectronica.es/expedientes | Requiere autenticación |
| Formulario licencia obras (PDF) | https://admin.dipujaen.es/export/.../Orcera/pdf/solicitud_obras.pdf | Operativa — enlace desde formularios web |

## Cómo se listan expedientes / proyectos

1. **Tablón sede (`/board/`):** tabla HTML espublico (`class_name`, `class_folderName`, `class_description`, `class_dateFrom`). Anuncios de contratación de redacción de proyectos técnicos (infraestructura) y bandos BOP; pocas filas estrictamente de planeamiento urbanístico.
2. **Transparencia — Planeamiento:** menú lateral Wicket con carpetas (NNSS 1987, Adaptación Parcial NN.SS, Plan de Ordenación, Unidad de Actuación, Sector SAU). Los PDFs se cargan vía AJAX al expandir; no hay listado plano en HTML inicial.
3. **PBOM:** servicio ciudadano dedicado en menú de transparencia.
4. **Web:** sección «Urbanismo, Vivienda y Obras» en gobierno/transparencia con ordenanzas fiscales y de habitabilidad (PDF/enlaces).

## Cómo se publican licencias

- No hay dataset público de licencias concedidas con coordenadas.
- Trámites: formularios web + sede (`/dossier`) y página DR en transparencia.
- Licencias publicadas como edictos irían al tablón; en la muestra actual predominan personal, contratación y BOP.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - SITUADIFUSION (`https://ws132.juntadeandalucia.es/situadifusion/`) — consulta por municipio; cartografía de planeamiento sin enlace a expediente municipal.
  - IDE Diputación de Jaén — sin capa consultable por código de expediente para Orcera.
  - Web/sede — sin visor ArcGIS/WFS; documentos PDF en carpetas Wicket.
- **Estrategia:** metadatos de planeamiento (NNSS/PBOM) como seeds; geocodificación vía centroide municipal + jitter en orquestador.
- **Limitaciones:** geometría de ámbito solo en PDF/planos no descargables sin sesión Wicket; tablón sin georreferencia.

## Limitaciones generales

- Documentos de planeamiento en sede requieren navegación Wicket (no API REST).
- `/dossier` puede ser lento en CI.
- Consulta de expedientes autenticada.
- Histórico de licencias no estructurado.

## Adapter implementado

- `municipio.adapters.orcera:OrceraAyuntamientoAdapter`
- Fuentes: tablón + seeds planeamiento (PBOM, NNSS, SITUA) + ítems menú Planeamiento + trámites DR/formularios.
- IDs: `orcera-lic-*` / `orcera-proy-*` (sha256[:14]).
