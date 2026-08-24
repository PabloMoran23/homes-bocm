# Alhaurín el Grande/Mijas — entrada combinada (no es un municipio)

**Slug cola:** `alhaurin-el-grande-mijas`  
**Nombre en CSV:** Alhaurín el Grande/Mijas  
**Provincia (CSV):** Alhaurín el Grande/Mijas  
**Comunidad autónoma:** Andalucía  
**Boletín:** BOJA (`boja`, 2 entradas en histórico parseado)

## Conclusión

**No procede adapter propio.** Este slug es un artefacto del agregado CSV: el campo `municipio` del boletín incluye dos municipios distintos de la provincia de Málaga separados por `/`. No existe un ayuntamiento «Alhaurín el Grande/Mijas».

Ambos municipios reales **ya están incorporados** al pipeline con adapters y manifests independientes:

| Municipio real | Slug | Adapter | Estado cola |
|----------------|------|---------|-------------|
| Alhaurín el Grande | `alhaurin-el-grande` | `municipio.adapters.alhaurin_el_grande:AlhaurinElGrandeAyuntamientoAdapter` | `done` (merge batch 2026-08-01) |
| Mijas | `mijas` | `municipio.adapters.mijas:MijasAyuntamientoAdapter` | `done` (merge batch 2026-08-01) |

Entrada duplicada relacionada en cola (mismo artefacto, distinto orden): `mijas-alhaurin-el-grande` (`pending`).

## Investigación de portales (referencia cruzada)

### Alhaurín el Grande (`alhaurin-el-grande`)

| Fuente | URL |
|--------|-----|
| Web | https://alhaurinelgrande.es |
| Urbanismo | https://alhaurinelgrande.es/concejalia-de-urbanismo/ |
| Sede / tablón | https://alhaurinelgrande.sedelectronica.es/board/ |
| Transparencia | https://alhaurinelgrande.sedelectronica.es/transparency |

- Expedientes: tablón espublico gestiona + PDFs WordPress (PGOU, planes especiales).
- Licencias: edictos en tablón; sin dataset georreferenciado.
- Ver `data/municipios/alhaurin-el-grande/RESEARCH.md` para detalle.

### Mijas (`mijas`)

| Fuente | URL |
|--------|-----|
| Web | https://www.mijas.es/portal/ |
| Urbanismo / expedientes | https://www.mijas.es/portal/urbanismo/ |
| Sede / tablón | https://mijas.sedelectronica.es/board |
| Licencias menor | https://www.mijas.es/portal/urbanismo/licencias-de-obra-menor-concedidas-por-decreto/ |

- Expedientes: WordPress (ZIP/PDF ~220 docs) + tablón espublico.
- Licencias: PDFs históricos obra menor; trámites sede.
- Ver `data/municipios/mijas/RESEARCH.md` para detalle.

## Geometría / visor

- **geometry_status:** `unavailable` (para este slug combinado; no hay portal único)
- **Fuentes:** Ninguna — los dos municipios revisados por separado no exponen visor GIS público enlazable a expedientes (RPGUR/Junta requiere token; sin WFS municipal).
- **Estrategia:** Usar adapters `alhaurin-el-grande` y `mijas`; centroide + jitter vía orquestador.
- **Limitaciones:** Entrada CSV no mapeable a un único portal municipal.

## Recomendación para la cola

1. Marcar `alhaurin-el-grande-mijas` como `failed` o `skipped` (no reintentar onboarding).
2. Aplicar la misma resolución a `mijas-alhaurin-el-grande`.
3. Opcional: filtrar en `aggregate_municipios_from_csv` nombres con `/` que coincidan con slugs `done` ya existentes.

## Adapter

**No implementado** — cubierto por `alhaurin_el_grande.py` y `mijas.py`.
