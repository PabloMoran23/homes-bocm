# Albuñol — investigación portal ayuntamiento

**Municipio:** Albuñol (Granada, Andalucía)  
**Slug:** `albunol`  
**Boletín:** BOJA (`boja`, 2 entradas en histórico)  
**INE:** 18010

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.albunol.es | **Operativa** — WordPress + Elementor; sin sección urbanismo ni posts |
| Sede electrónica | https://albunol.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://albunol.sedelectronica.es/board | **Operativa** — tabla HTML con preview-document |
| Catálogo trámites | https://albunol.sedelectronica.es/dossier | Lento/timeout en CI |
| Consulta expedientes | https://albunol.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |
| Transparencia urbanismo | https://albunol.sedelectronica.es/citizen-service/ade72156-e3c1-4d56-81f0-f39624e0fb3f | **Operativa** — página informativa licencias y PGOM |
| ATUM Diputación Granada | https://atum.dipgra.es/atum/formulario_actuaciones/buscador.php?ent=6 | Timeout en CI; buscador trámites urbanísticos |
| SITUA Junta Andalucía | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Visor regional PGOU; sin API REST por expediente |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Cómpeta, Coín, Cártama.
- **Listado:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** enlace `preview-document/{uuid}` (PDF embebido en visor sede).
- **Paginación:** botón «Mostrar más» vía Wicket AJAX; el adapter parsea la primera página (~8 filas).

### Ejemplos urbanísticos encontrados (ago 2026)

| Fecha | Procedimiento | Descripción |
|-------|---------------|-------------|
| 27/07/2026 | Actuaciones Urbanísticas | Aprobación admisión a trámite proyecto de urbanización AA-3 La Rábita (exp. 2282/2024) |
| 23/07/2026 | Procedimiento Genérico | Edicto rectificación de superficie y linderos en pago La Herradura (exp. 1976/2026) |

## Licencias de obra

- No hay dataset público de concesiones de obra con coordenadas.
- Página informativa en sede (transparencia «Obras y Urbanismo»):
  - Declaraciones Responsables
  - Licencias Urbanísticas
  - Comunicación Previa
- Buscador ATUM Diputación Granada (`ent=6`) para trámites urbanísticos; sin listado histórico de concesiones.
- Las licencias concedidas publicadas aparecen en el tablón como edictos (cuando existan).

## Proyectos / planeamiento

- **Tablón:** actuaciones urbanísticas (urbanización AA-3 La Rábita) y edictos de rectificación catastral.
- **Transparencia sede:** información básica sobre PGOM y trámites.
- **SITUA:** consulta regional de planeamiento general aprobado (sin enlace por expediente del ayuntamiento).
- No hay visor de seguimiento de expedientes público fuera del tablón.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - SITUA/VITUA (Junta de Andalucía): planeamiento regional PGOU; visor JSF sin WFS/ArcGIS REST accesible desde CI.
  - ATUM Diputación Granada: buscador de trámites; sin capas GIS.
  - Web municipal: sin visor urbanístico ni datos abiertos georreferenciados.
- **Estrategia:** los visores regionales muestran zonificación PGOU, **sin campo de enlace a expediente** del tablón. Los anuncios son PDF sin georreferencia embebida.
- **Limitaciones:**
  - Sin WFS/GeoJSON por código de expediente.
  - `/dossier` inestable (timeout) en entorno CI.
  - El orquestador aplicará centroide municipio + jitter para coordenadas.

## Limitaciones generales

- Tablón paginado con AJAX Wicket (solo primera página en adapter).
- Sin geometría por expediente.
- Consulta de expedientes requiere login.
- Web corporativa sin contenido urbanístico estructurado (solo administración, playas, cultura).

## Adapter implementado

- `municipio.adapters.albunol:AlbunolAyuntamientoAdapter`
- Fuentes: tablón sede + transparencia urbanismo + SITUA (metadato PGOU).
- IDs: `albunol-lic-*` / `albunol-proy-*` (sha256[:14]).
