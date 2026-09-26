# Algodonales — investigación portal ayuntamiento

Municipio: **Algodonales** (`algodonales`), provincia Cádiz, Andalucía. Boletín: BOJA (2 entradas).

## URLs base y páginas semilla

| Fuente | URL | Tipo |
|--------|-----|------|
| Web municipal | https://www.algodonales.es | Joomla rsnoticia (requiere User-Agent Mozilla; 403 sin él) |
| Tablón de anuncios | https://www.algodonales.es/tablondeanuncios | Tabla HTML + PDFs locales (~600 filas) |
| Sede electrónica | https://sede.algodonales.es | Liferay ecadiz / EPICSA (Diputación Cádiz) |
| Tablón sede | https://sede.algodonales.es/tablon-electronico-de-anuncios-y-edictos | Enlace a EPICSA idOrgan=6 |
| Edictos EPICSA | https://sede.algodonales.es/edictos/publico?idOrgan=6 | Tabla edictos (vacía al 2026-08) |
| Trámites | https://sede.algodonales.es/tramites-disponibles | Catálogo procedimientos |
| Polígono industrial | https://www.algodonales.es/poligono-industrial/ | Landing parcelas (imagen mapa, sin GIS) |
| Transparencia Dip. Cádiz | https://gobiernoabierto.dipucadiz.es/catalogo-de-informacion-publica?entidadId=2101 | Catálogo información pública |
| SITUA | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | PGOU digitalizado (cod. INE 11004) |
| Web antigua | https://antigua.algodonales.es/ayuntamiento/organigrama | Organigrama con área Urbanismo (referencia) |

**Nota:** `algodonales.sedelectronica.es` devuelve página genérica "seleccione su sede" (inactiva). La sede activa es `sede.algodonales.es`. El idOrgan=11 en EPICSA corresponde a otro municipio (Bornos); Algodonales usa **idOrgan=6**.

## Expedientes / proyectos

1. **Tablón web municipal (principal):** Tabla HTML con columnas fecha publicación/inicio/fin, título y enlace PDF. ~37 anuncios urbanísticos históricos: informaciones públicas (licencias actividad/obra), convenios urbanísticos UE-15/UE-2a, modificaciones puntuales PGOU (Cerros y Cimas, Sierra de Líjar), reparcelación Cabezadas, estudio ambiental estratégico.
2. **PGOU:** Instrumento vigente aprobado 2003; modificación puntual "Cerros y Cimas" aprobada definitivamente 2024 (BOJA). Consulta en SITUA (raster escaneado).
3. **Polígono industrial:** Landing con mapa imagen y parcelas; sin datos vectoriales descargables.
4. **Edictos EPICSA (idOrgan=6):** Sin registros publicados al momento de la investigación.
5. **Transparencia Diputación:** Catálogo general sin datasets GIS urbanísticos enlazables.

## Licencias de obra

- **Sin listado histórico** de licencias concedidas en portal público.
- Las **informaciones públicas** del tablón web documentan solicitudes de licencia de actividad/obra (bares, comercios, estación de servicio, naves, planta solar, etc.).
- Trámites en sede ecadiz sin listado de concesiones históricas.
- Adapter incluye páginas informativas de tablón + trámites (patrón Bornos/Pozuelo).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - Polígono industrial: mapa imagen con `<area>` HTML, sin GeoJSON/WFS.
  - SITUA Junta de Andalucía: PGOU digitalizado raster (cod. INE 11004), sin capa vectorial enlazable a expediente.
  - Tablón web y sede: solo PDFs, sin coordenadas ni visor ArcGIS.
  - Diputación Cádiz gobierno abierto: sin WFS urbanístico para Algodonales.
  - Callejero web (`/algodonales/callejero`): sin capa SIG enlazada a expedientes.
- **Estrategia:** No aplicable; orquestador usará centroide municipio + jitter.
- **Limitaciones:** Sin visor urbanístico municipal; anuncios mayoritariamente PDF sin georreferenciación.

## Limitaciones técnicas

- Web municipal bloquea peticiones sin User-Agent Mozilla (403 Forbidden).
- Sede Liferay ecadiz compartida; EPICSA idOrgan=6 sin edictos publicados.
- Tablón web: una sola página HTML con todos los años (sin paginación API).
- `insecure_ssl: true` en sede por compatibilidad CI (certificados ecadiz).
