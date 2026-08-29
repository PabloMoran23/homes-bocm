# Antas — investigación portal ayuntamiento

Municipio: **Antas** (Almería, Andalucía). INE: **04016**. Boletín: BOJA (2 entradas en CSV).

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.antas.es | WordPress (Astra + Elementor), REST API `/wp-json/` |
| Urbanismo | https://www.antas.es/urbanismo/ | Modelos DR obras, comunicación previa, ocupación |
| Sede electrónica | https://antas.sedelectronica.es | espublico gestiona |
| Tablón anuncios | https://antas.sedelectronica.es/board/ | Tabla HTML `class_name`, preview-document |
| Catálogo trámites | https://antas.sedelectronica.es/dossier | Licencias vía sede (sin histórico público) |
| Consulta expedientes | https://antas.sedelectronica.es/expedientes | Requiere autenticación |
| SITUA | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Visor regional planeamiento Junta |

## Cómo se listan expedientes / proyectos

1. **WordPress REST** (`/wp-json/wp/v2/posts?search=...`): noticias del ayuntamiento sobre PBOM, PGOU, sectores SR-1/SR-6, polígono industrial Aljoroque, plantas solares, regularizaciones. HTML en posts, sin tabla de expedientes.
2. **Página urbanismo**: enlaces a modelos ODT/DOCX/PDF en `wp-content/uploads/` (trámites informativos, no expedientes).
3. **Tablón sede**: 6 anuncios vigentes (ago 2026); ninguno de planeamiento/licencias en el momento de la investigación (presupuesto, mercadillo, bandos limpieza).
4. **SITUA**: metadata regional; PBOM en tramitación (contrato 2022, presentación 2025).

## Licencias de obra

- **No hay listado público** de licencias concedidas.
- Modelos en `/urbanismo/`: DR obras 2024, comunicación previa, ocupación edificios.
- Trámites en sede (`/dossier`, `/expedientes`) sin tabla pública.
- Adapter devuelve páginas informativas de trámites + modelos DR (patrón Vera/Cómpeta).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS Diputación de Almería GeoServer  
  `https://app.dipalme.org/geoserver/urbanismo/ows`  
  Capa: `urbanismo:v_siu_ambitos_o_sectores`  
  Filtro: `cod_ine='04016'` (3 sectores: EL REAL SUR CTRA, PARAJE LA SALAOSA, EL REAL SALMERON).
- **Estrategia:** Tras obtener título de proyecto, buscar token `SR-N` o nombre de sector en WFS; enriquecer con polígono EPSG:4326 y centroide.
- **Limitaciones:** Sectores SR-1 Aljoroque y SR-6 citados en noticias **no** están en WFS Dipalme (solo 3 sectores «El Real»). Sin visor municipal ArcGIS. PBOM en elaboración sin geometría publicada. Licencias sin georreferencia.

## Limitaciones

- Tablón sede con pocos anuncios y sin urbanismo reciente.
- Licencias: solo trámites/modelos, no concesiones históricas.
- Geometría parcial: 3/∞ sectores en WFS vs. más actuaciones documentadas en web.
- SSL sede: certificado gestionado por espublico; `insecure_ssl: true` en manifest por compatibilidad CI.
