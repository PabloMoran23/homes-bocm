"""Tests coherencia viviendas ↔ m²."""

from sector_geometry.madrid_nti_vivienda_sanity import (
    cap_viviendas_por_superficie,
    sanitize_viviendas_en_metrics,
    viviendas_coherentes_con_superficie,
)


def test_velazquez_21_descartado():
    assert not viviendas_coherentes_con_superficie(6343, 1016, None)
    m = sanitize_viviendas_en_metrics(
        {"num_viviendas_max": 6343, "sup_total_m2": 1016, "genera_vivienda_nueva": "probable_si"}
    )
    assert m["num_viviendas_max"] is None


def test_plan_parcial_grande_ok():
    assert viviendas_coherentes_con_superficie(1200, 80_000, None)
    assert cap_viviendas_por_superficie(80_000, None) >= 1200
