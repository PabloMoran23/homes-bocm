# Algemesí — investigación portal ayuntamiento

## URLs base y páginas semilla

| Fuente | URL |
|--------|-----|
| Web corporativa | https://www.algemesi.es |
| Urbanismo (Drupal) | https://www.algemesi.es/va/urbanisme |
| Sección urbanisme | https://www.algemesi.es/va/seccion/urbanisme |
| Projectes urbans | https://www.algemesi.es/va/pagina/projectes-urbans |
| Ordenances (dvmenu) | https://www.algemesi.es/va/dvmenu/2499 |
| Sede eAdmin (activa) | https://sede.algemesi.es/eAdmin |
| Tablón anuncios | https://sede.algemesi.es/eAdmin/Tablon.do?action=verAnuncios |
| Catálogo trámites | https://sede.algemesi.es/eAdmin/Registrar.do?action=inicioPortalTramites |
| Portal transparencia | https://transparencia.algemesi.es |
| Planejament i gestió | https://transparencia.algemesi.es/?page_id=185 |
| Exposició pública ordenances | https://transparencia.algemesi.es/?page_id=1003 |
| Sede espublico (inactiva) | https://algemesi.sedelectronica.es — devuelve «Sede Electrónica Indeterminada» |

## CMS y listado de expedientes

- **Web:** Drupal con módulos `digital_value` (tema portalesmunicipales). Idioma principal valenciano (`/va/`). Respuestas lentas en CI (~60–90 s/página); el adapter reintenta.
- **Projectes urbans:** página índice sin listado dinámico de expedientes (solo menú lateral urbanisme).
- **Tablón:** sede **eAdmin** (Maggioli/add4u). HTML `Tablon.do?action=verAnuncios` codificado ISO-8859-1. Anuncios urbanísticos mezclados con personal, presupuesto, subvenciones.
- **Transparencia:** WordPress Avada; páginas de índice sin documentos embebidos con código CSV (a diferencia de otros municipios eAdmin).
- **Licencias:** no hay registro público de concesiones; catálogo eAdmin con trámites URBANISME (llicència d'obra 165, DR obres 227, primera ocupació 138, CIU 48, compatibilitat 237).

## Licencias de obra

- Trámites informativos vía `Registrar.do?action=infoTramite&tipoReg=…` en sede eAdmin.
- Edictos del tablón filtrados por regex (licencia/obra/compatibilitat) cuando aparecen.
- Sin dataset ni geometría por licencia individual.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `ms:InventarioSuSuz` en `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Formato: GML3 (`outputFormat=GML3`, `srsName=EPSG:4326`), paginación `STARTINDEX`
  - Filtro cliente: `cod_ine_mun=46007` (Algemesí) — ~25 sectores SU/SUZ
  - Visor GVA: `https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz`
- **Estrategia:** descargar inventario ICV como proyectos con polígono; enriquecer filas del tablón por coincidencia de tokens sectoriales (UE-*, SECTOR *, etc.)
- **Limitaciones:**
  - No hay visor municipal ArcGIS enlazado al expediente
  - CQL_FILTER del WFS no funciona; requiere paginar ~12k features y filtrar por INE
  - `algemesi.sedelectronica.es` (espublico gestiona) no operativo
  - Web algemesi.es muy lenta; crawl limitado a semillas urbanismo

## Limitaciones generales

- Sede espublico (`algemesi.sedelectronica.es`) rota — usar `sede.algemesi.es/eAdmin`
- Tablón mezcla urbanismo con RRHH, créditos, subvenciones (filtro regex)
- Transparencia WordPress sin PDFs indexados en planejament (página vacía de contenido)
- Trámites eAdmin requieren identificación para presentación; solo scrape informativo
