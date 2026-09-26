# Onda — investigación portal ayuntamiento

Municipio: **Onda** (`onda`) — Castellón, Comunitat Valenciana  
Boletín: DOGV (`dogv`, 3 entradas BOCM)

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web corporativa (Woden/Insyde) | https://www.onda.es |
| Urbanismo | https://www.onda.es/ond/web_php/index.php?contenido=subapartados_woden&id_boto=158 |
| SAT / trámites | https://www.onda.es/ond/web_php/index.php?contenido=subapartados_woden&id_boto=167 |
| Sede electrónica (OpenSEA) | https://seu.onda.es |
| Transparencia (Digital Value) | https://transparencia.onda.es |
| SITAE municipal | https://ondasitae.sede.gva.es/sitae/ |
| Registro autonómico planeamiento | https://politicaterritorial.gva.es/es/web/urbanismo/registro-autonomico-de-instrumentos-de-planeamiento-urbanistico |
| RSS noticias | https://www.onda.es/ond/web_php/rss/ |

## Cómo se listan expedientes / proyectos

1. **CMS Woden (Insyde S.L.)** — página Urbanismo (`id_boto=158`) con ~109 PDFs estáticos en `/ond/uploaded/AreasMunicipales/urbanismo/`: modificaciones puntuales PGOU, plan parcial SUR-11, DIE/estudio estratégico, expropiaciones (río Sonella), normativa por zonas, planos PGOU 1998, acuerdos plenario.
2. **SITAE** (`ondasitae.sede.gva.es`) — plataforma NovaSoft/DWR para consulta de instrumentos de planeamiento; requiere sesión; no expone listado público scrapeable sin login.
3. **Sede OpenSEA** (`seu.onda.es`) — trámites electrónicos con certificado (ACCV, FNMT, CamerFirma); sin tablón de anuncios público ni consulta de expedientes anónima.
4. **Transparencia Digital Value** — `api.digitalvalue.es/contents/onda` con colecciones (articulos, paginas); sin documentos urbanísticos indexados en `documents` (vacío).

## Licencias de obra

- No hay listado histórico público de licencias concedidas.
- Formularios SAT en web corporativa (`SAT2022/urbanismo/`): licencia edificación, obras mayores/menores, demolición, grúa, etc. — solo instancias PDF, no concesiones publicadas.
- Tramitación vía sede OpenSEA con identificación digital.
- El adapter devuelve páginas informativas del SAT y sede (patrón Pozuelo/Burriana).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV GVA WFS `InventarioSuSuz`: `https://terramapas.icv.gva.es/0702_Planeamiento?service=WFS&typeName=InventarioSuSuz` — 45 sectores/unidades (SU/SUZ) en Onda (`cod_ine_mun=12084`), polígonos EPSG:4326.
  - Diputación Castellón (OpenDataSoft): `planeamiento-urbanistico`, `cod_mun=12084` → 368 polígonos GeoJSON (calificación suelo PGOU).
  - Visor GVA: https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz
  - SITAE: visor municipal vinculado a instrumentos; acceso con sesión.
- **Estrategia:** filas ICV SUZ con geometría directa; PDFs urbanismo enriquecidos por matching de palabras clave (SUR-11, sector, UE, modificación…) contra DipCAS + ICV.
- **Limitaciones:** sin visor municipal público enlazado a expediente concreto; OpenSEA/SITAE requieren login; licencias sin coords ni polígonos.

## Limitaciones generales

- CMS Woden sin API JSON; HTML estático con enlaces PDF.
- Sede OpenSEA sin tablón público de anuncios urbanísticos.
- ICV WFS paginado (~500 features/página, filtrado client-side por `cod_ine_mun`); primera carga lenta (20–30 s).
- DipCAS API con 368 registros; matching heurístico por denominación.
- Sin re-parse DOGV; proyectos del boletín ya en `projects.json`.
