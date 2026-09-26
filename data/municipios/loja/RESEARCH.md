# Loja — investigación portal ayuntamiento

Municipio: **Loja** (`loja`), provincia Granada, Andalucía. Boletín: BOJA (1 entrada).

## URLs base y páginas semilla

| Fuente | URL | Tipo |
|--------|-----|------|
| Web municipal | http://aytoloja.org | HTML estático (redirect desde www.loja.es) |
| Planeamiento | http://aytoloja.org/ayuntamiento/planeamiento.htm | Índice ~130 PDFs/ZIPs (PGOU vigente, PMUS, IP, ordenanzas) |
| Ordenanzas | http://aytoloja.org/ayuntamiento/ordenanzasyreglamentos.htm | PDFs normativa urbanística |
| Urbanismo (servicio) | http://aytoloja.org/cartadeservicios/urbanismo.htm | Carta de servicios OTM |
| Transparencia | http://portaldetransparencia.aytoloja.org/ | Portal externo (timeout desde CI) |
| Sede electrónica | https://loja.sedelectronica.es | espublico gestiona — **inactiva** («Sede Electrónica Indeterminada») |
| SITUA | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=18140 | Planeamiento digitalizado Junta (INE 18140) |

**Nota:** `www.loja.es` redirige a `aytoloja.org`. HTTPS en dominio principal no responde desde CI; HTTP funciona.

## Expedientes / proyectos

1. **Planeamiento (web):** Página única con documentación PGOU (planos PV-1…PV-4 por núcleos: Loja, La Bobadilla, Cerro Vidriero, etc.), adaptación LOUA, innovaciones puntuales, PMUS Cuesta Baja, estudios acústicos, información pública y ordenanzas compensatorias. Enlaces relativos a `doc/`, `PLANOS/`, `ANEXO/`, `MEMORIA/`.
2. **Ordenanzas urbanísticas:** PDFs de edificación SNÚ, vertidos, compensación aprovechamiento suelo no urbanizable.
3. **SITUA:** Consulta regional de planeamiento aprobado digitalizado (raster escaneado). Requiere selección de municipio en formulario JSF; no expone listado machine-readable de expedientes.
4. **Sede espublico:** Sin tablón `/board`, sin dossier de trámites ni consulta pública de expedientes.

## Licencias de obra

- **Sin listado histórico** de licencias concedidas en portal público.
- Oficina Técnica Municipal gestiona trámites vía presencial/sede (inactiva).
- Documento informativo «Aviso normativa cartel de obras» (2024) en planeamiento.
- Adapter devuelve páginas informativas de urbanismo + sede inactiva (patrón Bornos/Pozuelo).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - Planos PGOU en `PLANOS/1_PV_PLANEAMIENTO VIGENTE/`: PDFs cartográficos sin georreferenciación vectorial pública.
  - SITUA Junta de Andalucía (cid=18140): visor raster de instrumentos depositados, sin WFS/ArcGIS REST por expediente.
  - Sede espublico inactiva: sin visor ni API.
  - Portal transparencia: no accesible desde entorno CI.
  - Diputación Granada: sin WFS urbanístico municipal identificado para Loja.
- **Estrategia:** No aplicable; orquestador usará centroide municipio + jitter.
- **Limitaciones:** Sin visor urbanístico municipal; planos son PDF escaneados; sede sin tablón de licencias.

## Limitaciones técnicas

- Web HTTP legacy (PHP 5.5 / Tomcat 6 en backend); solo HTTP accesible desde CI.
- Sede `loja.sedelectronica.es` no operativa (página genérica espublico).
- `portaldetransparencia.aytoloja.org` timeout en CI.
- Sin API JSON ni RSS de urbanismo; scrape determinista de enlaces `<a href="*.pdf">`.
