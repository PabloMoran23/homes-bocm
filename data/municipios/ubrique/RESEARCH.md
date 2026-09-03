# Ubrique — investigación portal ayuntamiento

**Municipio:** Ubrique (Cádiz, Andalucía)  
**INE:** 11039  
**Investigado:** 2026-09-03

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Sede electrónica (espublico gestiona) | https://ubrique.sedelectronica.es/ | Tablón, trámites, transparencia integrada |
| Tablón de anuncios | https://ubrique.sedelectronica.es/board/ | Edictos y anuncios (HTML tabla wicket) |
| Proyectos técnicos urbanismo | https://ubrique.sedelectronica.es/transparency/d3a2fa91-8739-4f7d-85b9-63e798672352/ | Proyectos técnicos publicados (preview-document) |
| PGOU (sede transparencia) | https://ubrique.sedelectronica.es/transparency/22390146-92f7-45cc-ae9b-750cf0d2ac0c/ | Volúmenes revisión PGOU 2025 |
| Portal transparencia WP | https://transparencia.ayuntamientoubrique.es/ | PGOU, licencias, urbanismo (Elementor/Divi) |
| PGOU aprobación provisional | https://transparencia.ayuntamientoubrique.es/pgou-ubrique-documento-de-aprobacion-provisional/ | RAR/ZIP planos y textos |
| Licencias de obras (info) | https://transparencia.ayuntamientoubrique.es/licencias-de-obras/ | Procedimientos y formularios PDF |
| Web corporativa Joomla | https://www.ayuntamientoubrique.es/ | Enlaces a sede y transparencia (www.ubrique.es sin configurar) |
| SITUA Junta Andalucía | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Planeamiento digitalizado autonómico |

**Nota:** `www.ubrique.es` devuelve página por defecto de Plesk; la web activa es `ayuntamientoubrique.es`.

## Cómo se listan expedientes / proyectos

1. **Sede espublico — tablón** (`/board/`): tabla HTML con columnas Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha. Enlaces `preview-document/{uuid}`.
2. **Sede transparencia — carpetas temáticas**: listados wicket con enlaces `preview-document` (proyectos técnicos, PGOU, PMUS, etc.).
3. **WordPress transparencia**: páginas estáticas con enlaces a PDFs en `transparenciaubrique.es/documentos/` y sede.
4. **Consulta expedientes** (`/expedientes`): requiere identificación; no hay listado público indexable.

## Cómo se publican licencias

- **No hay dataset histórico** de licencias concedidas con dirección/coords.
- El tablón publica edictos puntuales (rectificación finca, herederos, etc.) — pocos relacionados con licencias de obra.
- `licencias-de-obras/` documenta **procedimientos** (declaración responsable, licencia ordinaria, comunicación previa) como PDFs informativos.
- Trámites en sede (`/dossier`) sin listado de concesiones públicas.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - SITUA (Junta de Andalucía): planeamiento general digitalizado; no enlaza expedientes del tablón ni proyectos técnicos por código.
  - No hay visor ArcGIS/WFS municipal público en sede ni transparencia.
  - PGOU publicado como PDF/RAR sin servicio WMS/WFS municipal.
- **Estrategia:** el orquestador aplicará centroide municipal + jitter (`centroid: [36.6778, -5.4460]`).
- **Limitaciones:** solo PDFs y preview-document sin georreferencia; consulta expedientes autenticada.

## Limitaciones

- Web principal `ubrique.es` inactiva (Plesk default).
- Tablón con pocos anuncios urbanísticos recientes; mayor volumen en carpetas transparencia sede.
- Licencias: solo páginas informativas de trámites, sin concesiones históricas.
- SSL sede: certificado válido; no requiere `insecure_ssl`.
- SITUA no permite query por expediente municipal concreto.
