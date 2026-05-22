from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

POC_ROOT = Path(__file__).resolve().parents[1]
MUNICIPIOS_DIR = POC_ROOT / "data" / "municipios"


@dataclass
class PortalConfig:
    """Portal del ayuntamiento — fuente principal del pipeline multi-municipio."""

    base_url: str
    adapter: str | None
    config: dict[str, Any] = field(default_factory=dict)
    notes: str = ""


@dataclass
class LicenciasConfig:
    enabled: bool
    adapter: str | None  # legacy; preferir portal.adapter
    config: dict[str, Any] = field(default_factory=dict)
    notes: str = ""


@dataclass
class ProyectosConfig:
    enabled: bool
    source: str  # ayuntamiento | bocm_legacy
    municipio_aliases: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class MunicipioManifest:
    slug: str
    nombre: str
    provincia: str
    comunidad_autonoma: str
    portal: PortalConfig
    licencias: LicenciasConfig
    proyectos: ProyectosConfig
    path: Path

    @property
    def output_dir(self) -> Path:
        return POC_ROOT / "output" / "municipios" / self.slug

    def ensure_output_dir(self) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return self.output_dir


def _norm(s: str) -> str:
    t = unicodedata.normalize("NFD", str(s or "").strip().lower())
    return t.encode("ascii", "ignore").decode("ascii")


def slugify(name: str) -> str:
    s = _norm(name)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "municipio"


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as e:
        raise RuntimeError(
            "PyYAML requerido: pip install -r requirements-municipio.txt"
        ) from e
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Manifest inválido: {path}")
    return data


def load_manifest(slug_or_path: str | Path) -> MunicipioManifest:
    path = Path(slug_or_path)
    if path.suffix in (".yaml", ".yml"):
        manifest_path = path
        slug = slugify(path.parent.name)
    else:
        slug = str(slug_or_path).strip()
        manifest_path = MUNICIPIOS_DIR / slug / "manifest.yaml"

    if not manifest_path.is_file():
        raise FileNotFoundError(f"No hay manifest: {manifest_path}")

    raw = load_yaml(manifest_path)
    slug = str(raw.get("slug") or slug)
    portal = raw.get("portal") or {}
    lic = raw.get("licencias") or {}
    proy = raw.get("proyectos") or {}
    aliases = proy.get("municipio_aliases") or [raw.get("nombre", slug)]
    if isinstance(aliases, str):
        aliases = [aliases]

    source = str(proy.get("source") or "ayuntamiento")
    if source == "bocm":
        source = "bocm_legacy"

    return MunicipioManifest(
        slug=slug,
        nombre=str(raw.get("nombre") or slug),
        provincia=str(raw.get("provincia") or "Madrid"),
        comunidad_autonoma=str(raw.get("comunidad_autonoma") or "comunidad-madrid"),
        portal=PortalConfig(
            base_url=str(portal.get("base_url") or ""),
            adapter=portal.get("adapter"),
            config=dict(portal.get("config") or {}),
            notes=str(portal.get("notes") or ""),
        ),
        licencias=LicenciasConfig(
            enabled=bool(lic.get("enabled", False)),
            adapter=lic.get("adapter"),
            config=dict(lic.get("config") or {}),
            notes=str(lic.get("notes") or ""),
        ),
        proyectos=ProyectosConfig(
            enabled=bool(proy.get("enabled", False)),
            source=source,
            municipio_aliases=[str(a) for a in aliases],
            notes=str(proy.get("notes") or ""),
        ),
        path=manifest_path,
    )


def list_manifest_slugs() -> list[str]:
    if not MUNICIPIOS_DIR.is_dir():
        return []
    out = []
    for d in sorted(MUNICIPIOS_DIR.iterdir()):
        if d.is_dir() and (d / "manifest.yaml").is_file() and not d.name.startswith("_"):
            out.append(d.name)
    return out


def municipio_matches(name: str | None, aliases: list[str]) -> bool:
    n = _norm(name)
    if not n:
        return False
    keys = {_norm(a) for a in aliases}
    if n in keys:
        return True
    for a in keys:
        if a and (a in n or n in a):
            return True
    return False
