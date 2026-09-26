# Ador — investigación portal ayuntamiento

Municipio: **Ador** (`ador`) — Comunitat Valenciana / Valencia — INE **46002** — DOGV (`dogv`)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Sede electrónica | https://ador.sedelectronica.es | espublico gestiona — tablón, trámites, transparencia |
| Tablón | https://ador.sedelectronica.es/board | Anuncios publicados (pocos; sin urbanismo reciente) |
| Transparencia sede — planeamiento | https://ador.sedelectronica.es/transparency/08b9f48a-afcd-4001-a9ae-af097842652b/ | PDFs PGOU (fases I–V), planos sectoriales |
| Portal transparencia | https://transparencia.ador.es | DigitalValue/Zity — sección urbanismo, PGOU |
| PGOU transparencia | https://transparencia.ador.es/es/transparencia/pla-general-d-ordenacio-urbana | Enlace externo PGOU |
| Planejament urbanístic | https://transparencia.ador.es/es/transparencia/planejament-urbanistic | Redirige a transparencia sede |
| Repositorio GVA | https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/4%20VALENCIA/46002%20ADOR/ | Índice Apache PG + PD (PDFs) |
| Web corporativa | https://www.ador.es | **502 Bad Gateway** (marzo 2026) |
| ADL Diputación | https://ador.divaladl.es | Empleo/emprendimiento (no urbanismo) |

## Cómo se listan expedientes / planeamiento

1. **Sede transparencia (espublico):** HTML estático con enlaces `preview-document/{uuid}` a PDFs del PGOU y revisiones sectoriales (Raconc, OVO).
2. **Repositorio GVA:** directorio Apache con carpetas por instrumento (`46002-0010 1995-0008 PP RACONC IND/`, etc.) y PDFs internos.
3. **ICV WFS InventarioSuSuz:** metadatos de 11 ámbitos SUZ/SU para INE 46002 (planes parciales Pinaret, Raconc, Monte Corona, etc.).
4. **Tablón sede:** tabla HTML wicket; actualmente solo anuncios no urbanísticos (presupuestos participativos).

No hay visor municipal propio ni consulta pública de expedientes urbanísticos (requiere identificación en `/expedientes`).

## Licencias de obra

- **Tablón:** sin concesiones de licencia publicadas en el momento de la investigación.
- **Trámites:** catálogo en `/dossier` (presentación vía sede; sin histórico público).
- **Transparencia:** catálogo de servicios indica que no hay carta de servicios digital para licencias; gestión presencial.

El adapter devuelve páginas informativas (tablón, trámites, consulta expedientes) como en otros municipios espublico sin listado histórico.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `InventarioSuSuz`: `https://terramapas.icv.gva.es/0702_Planeamiento` — 11 features `cod_ine_mun=46002` (STARTINDEX≈500)
  - Visor GVA: https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz
  - Enlaces ICV/mediambient en transparencia sede
- **Estrategia:** ingestar metadatos WFS (pp, ue, f_aprob); intentar geometría vía GML — **sin polígonos** en la respuesta WFS para los ids 999–1009 de Ador.
- **Limitaciones:** WFS devuelve atributos pero no `msGeometry` para Ador; tablón/PDFs sin georreferencia; web municipal caída. El orquestador aplicará centroide municipal + jitter.

## Limitaciones

- `www.ador.es` inaccesible (502).
- Tablón casi vacío de urbanismo.
- Licencias: solo trámites informativos, no concesiones publicadas.
- ICV: metadatos sí, geometría no disponible en WFS para este municipio.
- Paginación WFS nacional lenta si no se acota STARTINDEX (≈500 para Ador).
