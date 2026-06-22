# Galapagar — investigación portal ayuntamiento

**Slug:** `galapagar`  
**Nombre oficial:** Galapagar  
**BOCM (referencia):** 31 anuncios  
**Fecha investigación:** 2026-06-22

## Dominios

| Rol | URL | Estado |
|-----|-----|--------|
| Sede electrónica (add4u/eAdmin) | https://sede.galapagar.es/eAdmin | Accesible |
| Transparencia (WordPress) | https://transparencia.galapagar.es | Accesible |
| Web corporativa | https://www.galapagar.es | Timeout / vacío desde CI |
| Visor SIT CM (Comunidad de Madrid) | https://idem.comunidad.madrid/cartografia/sitcm/html/visor.htm | Accesible (visor interactivo) |

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Tablón edictos | `/eAdmin/Tablon.do?action=verAnuncios` | HTML tabla | 228 anuncios vigentes; UA-8 en IP (jun 2026) |
| Búsqueda tablón | POST `Tablon.do?action=verAnuncios` + `referenciaBusqueda` | HTML tabla | Filtrado por palabra clave |
| Detalle anuncio | `/eAdmin/Tablon.do?action=verAnuncio&id={hex}` | HTML | Periodo publicación, PDF original |
| PDF documento | `/eAdmin/ValidarDocumento.do?id_Documento={token}&tipo=doc&mode=ori` | PDF/PPTX (redirect) | Documento del edicto |
| Catálogo trámites urbanismo | `/eAdmin/Registrar.do?action=listadoEntradas` (filtro Urbanismo) | HTML modales | 11 trámites licencia/DR |
| Planeamiento (transparencia) | `https://transparencia.galapagar.es/?page_id=9196` | WordPress + `abrir('{token}')` | PGOU, UA-8, UA-10, UE-11B, convenios (~70 docs) |
| OpenData transparencia | `https://transparencia.galapagar.es/?page_id=8993` | HTML | Enlace al visor SIT CM |

## Estructura HTML tablón

Misma plataforma eAdmin que Colmenar Viejo / Meco. Tabla con filas:

1. Iconos: `abrirOriginal('{token}')` (PDF) y `verAnuncio&id={id}` (detalle)
2. Título
3. Periodo: `DD/MM/YYYY - DD/MM/YYYY`

Ejemplos vigentes (jun 2026):

- `UA-8 DOCUMENTO AMBIENTAL ESTRATEGICO` — plan parcial iniciativa particular (13 docs en tablón)
- `MODIFICACIÓN ORDENANZA DE TRAMITACION DE LICENCIAS...` — normativa licencias

## Transparencia — planeamiento

Secciones en `page_id=9196`:

- Avance PGOU (presentación, memoria, planimetría, fichas)
- Plan Parcial Navalonguilla
- Plan Parcial Las Cuestas
- Plan Reparcelación UA-10 Calle Mandril
- Iniciativa UE-11B
- UA-8 (plan parcial iniciativa particular)
- Plan Especial Carretera de El Escorial

Documentos servidos vía `javascript:abrir('{token}')` → `ValidarDocumento.do` en la sede.

## Licencias

No hay listado tabular de concesiones con coordenadas.

Fuentes:

- Edictos del tablón con mención a licencias/ordenanza
- Páginas informativas de trámites urbanismo (tipoReg 12, 38–46, 413)

## Proyectos / expedientes

- ~70 documentos de planeamiento en transparencia
- Edictos UA-8 y similares en tablón digital

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** Visor SIT CM de la Comunidad de Madrid (`idem.comunidad.madrid/cartografia/sitcm/html/visor.htm`) enlazado desde OpenData municipal. Muestra planeamiento vigente del municipio (capas regionales).
- **Estrategia:** No hay API ArcGIS/WFS accesible desde CI ni enlace expediente→polígono en tablón/transparencia. Los planos se publican como PDF/PPTX sin georreferencia embebida. El orquestador aplicará centroide municipal + jitter.
- **Limitaciones:** Sin visor municipal propio; SIT CM no expone endpoint REST/WFS consultable; tablón y transparencia solo PDFs; sin campo expediente enlazable a geometría.

## Limitaciones

- `www.galapagar.es` no responde desde entorno CI
- Tablón muestra anuncios **vigentes**; histórico vía búsqueda por términos
- PDFs vía token codificado en sede
- Sin geolocalización en fuentes scrapeables (`lat`/`lon` = null; sin `geom_geojson`)

## Referencia adapters

- Tablón eAdmin: `colmenar_viejo.py`, `meco.py`
- Transparencia WordPress: `meco.py`
