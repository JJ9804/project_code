import math

import numpy as np
import pytest

from column_design import aci_column as ac
from column_design import loads as ld


def make_rect(nx=3, ny=3, fc=28.0, fy=390.0, db=20.0):
    bars = ac.rect_bars(400, 400, 40, 10, db, nx, ny)
    return ac.Section("rect", 400, 400, fc, fy, 240, 40, db, 10, False, bars)


def test_bar_layout_counts():
    assert len(ac.rect_bars(400, 600, 40, 10, 20, 3, 4)) == 10
    assert len(ac.circle_bars(500, 40, 10, 20, 8)) == 8


def test_po_and_pnmax():
    sec = make_rect()
    s = ac.build_surface(sec, ac.PHI_THAI_QC)
    Ast = 8 * math.pi * 100
    Po = 0.85 * 28 * (160000 - Ast) + 390 * Ast
    assert s.Po == pytest.approx(Po)
    assert s.Pn_max == pytest.approx(0.8 * Po)
    # c ใหญ่มาก → Pn เข้าใกล้ Po
    assert s.Pn[:, -1].max() == pytest.approx(Po, rel=0.02)


def test_pure_bending_matches_hand_calc():
    # 2 ชั้นเหล็ก (3 เส้นบน/ล่าง) + เหล็กกลาง 2 เส้น — หา Mn ที่ Pn = 0 ด้วยวิธีมือแบบ iteration
    sec = make_rect()
    s = ac.build_surface(sec, ac.PHI_ACI, n_fiber=80)
    cur = ac.uniaxial_curve(s, "x")
    order = np.argsort(cur["Pn_pos"])
    Mn0 = np.interp(0.0, cur["Pn_pos"][order], cur["Mn_pos"][order])
    # hand: solve c
    As = math.pi * 100
    e = 40 + 10 + 10
    ys = [400 - e, 200, e]  # depth from top
    nb = [3, 2, 3]
    b1 = 0.85

    def P(c):
        f = 0.85 * 28 * b1 * c * 400
        for d, n in zip(ys, nb):
            eps = 0.003 * (c - d) / c
            fs = max(min(eps * 200000, 390), -390)
            if d <= b1 * c:
                fs -= 0.85 * 28
            f += fs * n * As
        return f

    lo, hi = 1.0, 400.0
    for _ in range(100):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if P(mid) < 0 else (lo, mid)
    c = lo
    M = 0.85 * 28 * b1 * c * 400 * (200 - b1 * c / 2)
    for d, n in zip(ys, nb):
        eps = 0.003 * (c - d) / c
        fs = max(min(eps * 200000, 390), -390)
        if d <= b1 * c:
            fs -= 0.85 * 28
        M += fs * n * As * (200 - d)
    assert Mn0 == pytest.approx(M / 1e6, rel=0.02)


def test_biaxial_square_symmetry():
    sec = make_rect()
    s = ac.build_surface(sec, ac.PHI_THAI_QC)
    r1, cap1 = ac.capacity_ratio(s, 1000e3, 100e6, 0)
    r2, cap2 = ac.capacity_ratio(s, 1000e3, 0, 100e6)
    assert cap1 == pytest.approx(cap2, rel=0.02)
    # 45° capacity smaller than uniaxial for square column
    _, cap45 = ac.capacity_ratio(s, 1000e3, 70.7e6, 70.7e6)
    assert cap45 < cap1


def test_axial_overload_ratio():
    sec = make_rect()
    s = ac.build_surface(sec, ac.PHI_THAI_QC)
    r, _ = ac.capacity_ratio(s, 2 * s.phiPn_max, 0, 0)
    assert r == pytest.approx(2.0)


def test_phi_transition():
    eps_ty = 390 / 200000
    phi = ac.phi_from_strain(np.array([0.0, eps_ty, eps_ty + 0.0015, 0.01]), eps_ty, 0.70, 0.90)
    assert phi.tolist() == pytest.approx([0.70, 0.70, 0.80, 0.90])


def test_slenderness_short_column():
    sec = make_rect()
    r = ac.slenderness(sec, "x", 1000e3, 50e6, -30e6, 3000, 1.0, 0.6)
    assert not r.slender  # 3000/120 = 25 < 34+12*0.6
    assert r.klu_r == pytest.approx(25.0)


def test_slenderness_magnification():
    sec = make_rect()
    r = ac.slenderness(sec, "x", 1000e3, 50e6, 50e6, 6000, 1.0, 0.6)
    assert r.slender
    assert r.Cm == pytest.approx(1.0)
    assert r.delta > 1.0


def test_shear_basic():
    sec = make_rect()
    r = ac.shear_check(sec, "y", 100e3, 500e3, 150, 2, 0.85)
    assert r.Vc > 0 and r.Vs > 0 and r.phiVn > 0


def test_ll_reduction():
    assert [ld.ll_reduction_pct(i) for i in range(10)] == [0, 0, 0, 10, 20, 30, 40, 50, 50, 50]
    assert not ld.ll_reducible(600, False)
    assert not ld.ll_reducible(300, True)


def test_takedown_and_combos():
    floors = [ld.Floor("Roof", 20, 0.15, 100, 200)] + [ld.Floor(f"F{i}", 20, 0.15, 150, 250) for i in range(5)]
    rows = ld.column_takedown(floors)
    assert rows[-1].reduction_pct == 30
    assert rows[-1].sum_ll_reduced < rows[-1].sum_ll
    cmb = ld.combos_thai_usd()
    assert cmb[0].factors == {"D": 1.4, "L": 1.7}
    f = ld.factor_loads({"D": ld.LoadCase(P=100), "L": ld.LoadCase(P=50)}, cmb[:1])[0]
    assert f.Pu == pytest.approx(225)
    assert f.sustained_ratio == pytest.approx(140 / 225)
