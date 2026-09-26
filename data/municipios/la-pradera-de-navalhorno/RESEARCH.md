# La Pradera de Navalhorno — investigación portal ayuntamiento

**Fecha:** 2026-09-20  
**Slug:** `la-pradera-de-navalhorno`  
**BOCYL regional (referencia):** 1 fila

## Resumen territorial (bloqueo parcial)

**La Pradera de Navalhorno no es un municipio INE independiente.** Es una **entidad singular / localidad** dentro del municipio de **Real Sitio de San Ildefonso** (INE `40181`, PlanPublica `provincia=40&municipio=181`).

La entrada en `queue.yaml` proviene de una mención en BOCYL al ámbito urbanístico «La Pradera de Navalhorno» dentro del PGOU del Real Sitio. El adapter filtra documentos del ayuntamiento matriz (Real Sitio) que citan explícitamente esta localidad.

| Aspecto | Valor |
|---------|-------|
| Municipio INE matriz | Real Sitio de San Ildefonso (`40181`) |
| Entidad singular | La Pradera de Navalhorno |
| Cola duplicada | `real-sitio-de-san-ildefonso` / `el-real-sitio-de-san-ildefonso` (pendientes) |

## Portales investigados

| Portal | URL | Estado | Contenido |
|--------|-----|--------|-----------|
| Web propia | `www.lapraderadenavalhorno.es`, `.com` | **No responde** | Sin sitio municipal propio |
| Sede espublico | `lapradera.sedelectronica.es`, `lapraderadenavalhorno.sedelectronica.es` | **Inactiva** («Sede Electrónica Indeterminada») | Sin tablón ni catálogo |
| DipSegovia | `/web/ayuntamiento-de-la-pradera-de-navalhorno` | **404** | No existe micrositio |
| PlanPublica JCyL (matriz) | `provincia=40&municipio=181` | **Activo** | 13 docs Real Sitio; **2 citan La Pradera de Navalhorno** |
| IDECyL WFS (matriz) | `c_mun='40181'` | **Activo** | 9 sectores Real Sitio; ninguno nombrado «Pradera de Navalhorno» |

## Fuentes de proyectos / expedientes

### PlanPublica — Real Sitio de San Ildefonso (filtrado)

- **Aprobado:** `searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=40&municipio=181`
- **Info pública:** `searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=40&municipio=181`
- **Documentos con mención a La Pradera de Navalhorno (2):**

| Fecha pub. | Instrumento | Título |
|------------|-------------|--------|
| 2001-02-07 | PGOU | Modificación puntual: cambio de ordenanza Grado 1/2 → Grado 3 en parcela de «La Pradera de Navalhorno» |
| 2002-01-23 | PGOU | Modificación puntual del PGOU referido al cambio de aprovechamiento en La Pradera de Navalhorno |

- **Enlaces:** `openBoletin.do?cDocId=...` / `openDocumento.do?cDocId=...`

### Sede electrónica

- `realsitodesanildefonso.sedelectronica.es` y `sanildefonso.sedelectronica.es` → **inactivas** (mismo mensaje «indeterminada»)
- Sin tablón de licencias ni expedientes publicados

## Fuentes de licencias

- No hay listado público de concesiones para la localidad
- Sede inactiva → sin catálogo de trámites accesible
- El adapter devuelve lista vacía (`min_rows: 0`)

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes consultadas:**
  - IDECyL WFS `urbanismo:plau_cyl_*` con `c_mun='40181'` (Real Sitio): 1 instrumento + 9 sectores (Ensanche, Huertas, Llano Amarillo, Valsaín…)
  - Ningún sector WFS lleva el nombre «La Pradera de Navalhorno»
- **Estrategia:** sin visor ni capa GIS enlazable a esta localidad; el orquestador aplicará centroide municipio + jitter
- **Limitaciones:** expedientes históricos solo en PDF BOCYL/PlanPublica sin georreferencia

## Limitaciones

1. **No es municipio INE** — los datos urbanísticos pertenecen al ayuntamiento de Real Sitio de San Ildefonso
2. Sin web ni sede propia para la localidad
3. Solo 2 expedientes PGOU filtrables por nombre; el resto del planeamiento de Real Sitio queda fuera de este slug
4. Recomendación: incorporar `real-sitio-de-san-ildefonso` para cobertura completa del municipio matriz

## Estrategia adapter

1. **proyectos.jsonl:** PlanPublica Real Sitio (`municipio=181`) filtrado por `pradera|navalhorno` en título + páginas semilla JCyL
2. **licencias.jsonl:** vacío (sin fuente pública)
3. **Geometría:** no aplicable (`geometry_status: unavailable`)
