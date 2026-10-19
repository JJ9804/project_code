"""Streamlit — ออกแบบเสาคอนกรีตเสริมเหล็ก ACI 318-19 + น้ำหนักบรรทุกตามกฎกระทรวง 2566

รัน:  streamlit run app.py
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from column_design import aci_column as ac
from column_design import loads as ld

st.set_page_config(page_title="ออกแบบเสา คสล. ACI 318-19", page_icon="🏛️", layout="wide")

KSC_PER_MPA = 10.197

# ---------------------------------------------------------------------------
# Sidebar — เกณฑ์การออกแบบ
# ---------------------------------------------------------------------------
st.sidebar.title("🏛️ ออกแบบเสา คสล.")
st.sidebar.caption("ACI 318-19 (กำลัง) + กฎกระทรวงออกแบบโครงสร้างอาคาร พ.ศ. 2566 / ประกาศ มท. 2567")

project = st.sidebar.text_input("ชื่อโครงการ", "โครงการตัวอย่าง")
col_mark = st.sidebar.text_input("ชื่อเสา", "C1")

st.sidebar.subheader("เกณฑ์การออกแบบ")
combo_set = st.sidebar.radio(
    "Load combination",
    ["กฎกระทรวง 2566 ข้อ 7 (1.4D+1.7L)", "ACI 318-19 Table 5.3.1 (1.2D+1.6L)"],
    help="ค่าตั้งต้นตามกฎกระทรวง 2566 ข้อ 7; ชุด ACI ใช้ได้เมื่อมีเอกสารรับรองตามข้อ 5 วรรคสอง",
)
thai_combo = combo_set.startswith("กฎกระทรวง")
phi_opts = {
    "กฎกระทรวง ข้อ 8 — มีการระบุมาตรฐาน/ควบคุมคุณภาพ": ac.PHI_THAI_QC,
    "กฎกระทรวง ข้อ 8 — ไม่มีการระบุ": ac.PHI_THAI_NOQC,
    "ACI 318-19 Table 21.2.2": ac.PHI_ACI,
}
default_phi = 0 if thai_combo else 2
phi_key = st.sidebar.selectbox("ตัวคูณลดกำลัง φ", list(phi_opts), index=default_phi)
phis = phi_opts[phi_key]
if thai_combo and phis is ac.PHI_ACI or (not thai_combo and phis is not ac.PHI_ACI):
    st.sidebar.warning("⚠️ ชุด load factor และ φ มาจากคนละมาตรฐาน — ไม่ควรใช้ปนกัน")
st.sidebar.caption(
    f"φ เสาปลอกเดี่ยว {phis.tied} · ปลอกเกลียว {phis.spiral} · ดัด {phis.tension} · เฉือน {phis.shear}"
)
use_wind = st.sidebar.checkbox("รวมแรงลม (Wx, Wy)", True)
use_eq = st.sidebar.checkbox("รวมแรงแผ่นดินไหว (Ex, Ey)", False)
if use_eq:
    st.sidebar.info("แรง E ระดับกำลัง (มยผ.1301/1302-61). เสาในระบบต้านแผ่นดินไหวต้องตรวจ detailing "
                    "ตาม ACI 318-19 บทที่ 18 เพิ่มเติม (โปรแกรมนี้ไม่ครอบคลุม)")

combos = (ld.combos_thai_usd(use_wind, use_eq) if thai_combo
          else ld.combos_aci_318_25(use_wind, use_eq))

tab_load, tab_force, tab_design, tab_report = st.tabs(
    ["① น้ำหนักบรรทุก (Load takedown)", "② แรงในเสา & Load combination",
     "③ หน้าตัด & ตรวจสอบกำลัง", "④ สรุปรายการคำนวณ"]
)

# ---------------------------------------------------------------------------
# ① Load takedown
# ---------------------------------------------------------------------------
LL_OPTIONS = {f"{g} | {u}": v for g, d in ld.LIVE_LOADS.items() for u, v in d.items()}
LL_KEYS = list(LL_OPTIONS)


def _ll_key(fragment_group: str, fragment_use: str) -> str:
    return next(k for k in LL_KEYS if fragment_group in k and fragment_use in k)


DEFAULT_FLOORS = pd.DataFrame([
    {"ชั้น": "ดาดฟ้า", "การใช้งาน (ข้อ 11)": _ll_key("7. อื่น", "ดาดฟ้า"), "LL กำหนดเอง (kg/m²)": 0.0,
     "พื้นที่รับน้ำหนัก (m²)": 24.0, "พื้นหนา (m)": 0.15, "SDL (kg/m²)": 150.0,
     "คานยาวรวม (m)": 10.0, "คานกว้าง (m)": 0.25, "คานลึกใต้พื้น (m)": 0.35,
     "ผนังยาว (m)": 0.0, "ผนังสูง (m)": 0.0, "น้ำหนักผนัง (kg/m²)": 180.0, "ความสูงเสาชั้นล่าง (m)": 3.2},
] + [
    {"ชั้น": f"ชั้น {n}", "การใช้งาน (ข้อ 11)": _ll_key("2. สำนักงาน", "พื้นที่สำนักงาน"), "LL กำหนดเอง (kg/m²)": 0.0,
     "พื้นที่รับน้ำหนัก (m²)": 24.0, "พื้นหนา (m)": 0.15, "SDL (kg/m²)": 150.0,
     "คานยาวรวม (m)": 10.0, "คานกว้าง (m)": 0.25, "คานลึกใต้พื้น (m)": 0.35,
     "ผนังยาว (m)": 6.0, "ผนังสูง (m)": 2.8, "น้ำหนักผนัง (kg/m²)": 180.0, "ความสูงเสาชั้นล่าง (m)": 3.2}
    for n in range(5, 1, -1)
])

with tab_load:
    st.subheader("การถ่ายน้ำหนักลงเสา (เรียงจากหลังคาลงล่าง)")
    st.markdown(
        "- **DL** (กฎกระทรวง ข้อ 9–10 / ประกาศ มท. ตาราง 2): คสล. 2,400 kg/m³ + SDL + คาน + ผนัง + น้ำหนักเสา\n"
        "- **LL ขั้นต่ำ** ตามตารางข้อ 11 (เลือกการใช้งาน หรือใส่ค่ากำหนดเองที่มากกว่า — ข้อ 12)\n"
        "- **ลด LL ตามจำนวนชั้น** ข้อ 13 (ฐานราก/เสา/กำแพง) — ไม่ลดสำหรับอาคารตามข้อ 14(1) หรือ LL > 500 kg/m²"
    )
    c1, c2, c3 = st.columns(3)
    gamma_c = c1.number_input("หน่วยน้ำหนัก คสล. (kg/m³)", 2000.0, 2600.0, 2400.0, 50.0)
    col_bx = c2.number_input("ขนาดเสาสำหรับคิดน้ำหนักตัวเอง b (m)", 0.15, 2.0, 0.40, 0.05)
    col_hy = c3.number_input("h (m)", 0.15, 2.0, 0.40, 0.05)
    apply_red = st.checkbox("ลดน้ำหนักบรรทุกจรตามจำนวนชั้น (ข้อ 13)", True)

    floors_df = st.data_editor(
        DEFAULT_FLOORS, num_rows="dynamic", width="stretch", key="floors",
        column_config={
            "การใช้งาน (ข้อ 11)": st.column_config.SelectboxColumn(options=LL_KEYS, width="large", required=True),
            "LL กำหนดเอง (kg/m²)": st.column_config.NumberColumn(help="0 = ใช้ค่าตามตารางข้อ 11"),
            "น้ำหนักผนัง (kg/m²)": st.column_config.NumberColumn(
                help="อิฐมอญครึ่งแผ่นฉาบ 2 ด้าน ≈ 180, อิฐมอญเต็มแผ่น ≈ 360, คอนกรีตบล็อก ≈ 120, อิฐมวลเบา 7.5 ซม. ≈ 90"),
        },
    )
    floors: list[ld.Floor] = []
    for _, r in floors_df.dropna(subset=["ชั้น"]).iterrows():
        ll_tab, no_red = LL_OPTIONS.get(r["การใช้งาน (ข้อ 11)"], (0.0, False))
        ll_use = max(float(r["LL กำหนดเอง (kg/m²)"] or 0.0), ll_tab)
        col_w = col_bx * col_hy * float(r["ความสูงเสาชั้นล่าง (m)"] or 0.0) * gamma_c * ld.KG_TO_KN
        floors.append(ld.Floor(
            str(r["ชั้น"]), float(r["พื้นที่รับน้ำหนัก (m²)"]), float(r["พื้นหนา (m)"]),
            float(r["SDL (kg/m²)"]), ll_use, no_red,
            float(r["คานยาวรวม (m)"]), float(r["คานกว้าง (m)"]), float(r["คานลึกใต้พื้น (m)"]),
            float(r["ผนังยาว (m)"]), float(r["น้ำหนักผนัง (kg/m²)"]), float(r["ผนังสูง (m)"]), col_w,
        ))
    rows = ld.column_takedown(floors, gamma_c, apply_red)
    td = pd.DataFrame([{
        "ชั้น": r.name, "LL ใช้ (kg/m²)": f.ll, "DL ชั้น (kN)": r.dl, "LL ชั้น (kN)": r.ll,
        "% ลด LL": r.reduction_pct, "LL หลังลด (kN)": r.ll_reduced,
        "ΣDL (kN)": r.sum_dl, "ΣLL (kN)": r.sum_ll_reduced,
        "ΣDL (tf)": r.sum_dl / 9.81, "ΣLL (tf)": r.sum_ll_reduced / 9.81,
    } for r, f in zip(rows, floors)])
    st.dataframe(td.style.format(precision=1), width="stretch", hide_index=True)
    if rows:
        PD_tk, PL_tk = rows[-1].sum_dl, rows[-1].sum_ll_reduced
        m1, m2, m3 = st.columns(3)
        m1.metric("ΣDL ที่โคนเสา", f"{PD_tk:,.1f} kN", f"{PD_tk / 9.81:,.1f} tf", delta_color="off")
        m2.metric("ΣLL (หลังลด)", f"{PL_tk:,.1f} kN", f"{PL_tk / 9.81:,.1f} tf", delta_color="off")
        pu_tk = 1.4 * PD_tk + 1.7 * PL_tk if thai_combo else max(1.4 * PD_tk, 1.2 * PD_tk + 1.6 * PL_tk)
        m3.metric("Pu (D+L)", f"{pu_tk:,.1f} kN", f"{pu_tk / 9.81:,.1f} tf", delta_color="off")
    else:
        PD_tk = PL_tk = 0.0

    with st.expander("ตารางน้ำหนักบรรทุกจรขั้นต่ำ — กฎกระทรวง 2566 ข้อ 11"):
        st.dataframe(pd.DataFrame([
            {"กลุ่ม": g, "ส่วนของอาคาร": u, "LL (kg/m²)": v[0], "LL (kN/m²)": v[0] * ld.KG_TO_KN,
             "ห้ามลด LL (ข้อ 14)": "✓" if (v[1] or v[0] > 500) else ""}
            for g, d in ld.LIVE_LOADS.items() for u, v in d.items()
        ]).style.format({"LL (kN/m²)": "{:.2f}"}), width="stretch", hide_index=True)
    with st.expander("หน่วยน้ำหนักวัสดุ — ประกาศ มท. 2567 ตาราง 2 / ส่วนลด LL ข้อ 13"):
        cA, cB = st.columns(2)
        cA.dataframe(pd.DataFrame({"วัสดุ": list(ld.UNIT_WEIGHTS), "kg/m³": list(ld.UNIT_WEIGHTS.values())}),
                     hide_index=True, width="stretch")
        cB.dataframe(pd.DataFrame({
            "ชั้นถัดจากหลังคา": ["หลังคา/ดาดฟ้า", "1", "2", "3", "4", "5", "6", "≥ 7"],
            "% ลด LL": ld.LL_REDUCTION_PCT}), hide_index=True, width="stretch")

# ---------------------------------------------------------------------------
# ② Forces & combinations
# ---------------------------------------------------------------------------
CASES = ["D", "L"] + (["Wx", "Wy"] if use_wind else []) + (["Ex", "Ey"] if use_eq else [])
FORCE_COLS = ["P (kN)", "Mx บน (kN·m)", "Mx ล่าง (kN·m)", "My บน (kN·m)", "My ล่าง (kN·m)",
              "Vx (kN)", "Vy (kN)"]

with tab_force:
    st.subheader("แรงในเสาจากแต่ละ load case (ที่ชั้นที่ออกแบบ)")
    st.caption(
        "P อัดเป็นบวก · Mx = โมเมนต์รอบแกน x (ดัดในทิศ h) · My = รอบแกน y (ดัดในทิศ b) · "
        "โมเมนต์ปลายบน/ล่างใช้ค่าจากแผนภาพโมเมนต์ภายใน (เช่น M3/M2 ของ ETABS ที่ปลาย j/i): "
        "**เครื่องหมายเดียวกัน = ดัดโค้งทางเดียว**"
    )
    use_tk = st.checkbox("ใช้ P ของ D และ L จากแท็บ ① (Load takedown)", True)
    base = {
        "D": [PD_tk if use_tk else 800.0, 12.0, -8.0, 6.0, -4.0, 2.0, 4.0],
        "L": [PL_tk if use_tk else 300.0, 6.0, -4.0, 3.0, -2.0, 1.0, 2.0],
        "Wx": [20.0, 0.0, 0.0, 35.0, -30.0, 18.0, 0.0],
        "Wy": [25.0, 40.0, -35.0, 0.0, 0.0, 0.0, 22.0],
        "Ex": [30.0, 0.0, 0.0, 60.0, -55.0, 32.0, 0.0],
        "Ey": [35.0, 70.0, -65.0, 0.0, 0.0, 0.0, 40.0],
    }
    df_cases = pd.DataFrame([[c] + base[c] for c in CASES], columns=["Case"] + FORCE_COLS)
    edited = st.data_editor(df_cases, width="stretch", hide_index=True, key=f"cases_{use_tk}_{len(CASES)}",
                            disabled=["Case"])
    if use_tk:
        edited.loc[edited["Case"] == "D", "P (kN)"] = PD_tk
        edited.loc[edited["Case"] == "L", "P (kN)"] = PL_tk
    cases = {
        r["Case"]: ld.LoadCase(r["P (kN)"], r["Mx บน (kN·m)"], r["Mx ล่าง (kN·m)"],
                               r["My บน (kN·m)"], r["My ล่าง (kN·m)"], r["Vy (kN)"], r["Vx (kN)"])
        for _, r in edited.iterrows()
    }
    forces = ld.factor_loads(cases, combos)
    st.subheader("น้ำหนักบรรทุกปรับค่า")
    st.dataframe(pd.DataFrame([{
        "Combo": f.combo, "สมการ": f.label, "Pu (kN)": f.Pu, "Mx บน": f.Mx_top, "Mx ล่าง": f.Mx_bot,
        "My บน": f.My_top, "My ล่าง": f.My_bot, "Vux": f.Vux, "Vuy": f.Vuy, "βdns": f.sustained_ratio,
    } for f in forces]).style.format(precision=2), width="stretch", hide_index=True)

    with st.expander("Service combination (กฎกระทรวง ข้อ 6) — สำหรับตรวจฐานราก/เสาเข็ม"):
        sv = ld.factor_loads(cases, ld.combos_thai_asd(use_wind, use_eq))
        st.dataframe(pd.DataFrame([{
            "Combo": f.combo, "สมการ": f.label, "P (kN)": f.Pu, "P (tf)": f.Pu / 9.81,
            "Mx ล่าง (kN·m)": f.Mx_bot, "My ล่าง (kN·m)": f.My_bot,
        } for f in sv]).style.format(precision=2), width="stretch", hide_index=True)

# ---------------------------------------------------------------------------
# ③ Section & design
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner=False)
def surface_cached(shape, b, h, fc, fy, fyt, cover, db, dt, spiral, bars_t, phi_t):
    sec = ac.Section(shape, b, h, fc, fy, fyt, cover, db, dt, spiral, np.array(bars_t))
    return ac.build_surface(sec, ac.PhiSet(*phi_t))


def make_section(shape, b, h, fc, fy, fyt, cover, db, dt, spiral, nx, ny, n_circ):
    bars = (ac.rect_bars(b, h, cover, dt, db, nx, ny) if shape == "rect"
            else ac.circle_bars(b, cover, dt, db, n_circ))
    return ac.Section(shape, b, h if shape == "rect" else b, fc, fy, fyt, cover, db, dt, spiral, bars)


def get_surface(sec: ac.Section) -> ac.Surface:
    return surface_cached(sec.shape, sec.b, sec.h, sec.fc, sec.fy, sec.fyt, sec.cover, sec.db, sec.dt,
                          sec.spiral, tuple(map(tuple, sec.bars.round(3))),
                          (phis.name, phis.tied, phis.spiral, phis.tension, phis.shear))


def evaluate(sec: ac.Section, forces, lu_x, lu_y, kx, ky, sway, transverse):
    """ตรวจทุก combo — คืน DataFrame + รายละเอียด"""
    surf = get_surface(sec)
    out, detail = [], []
    for f in forces:
        Pu = f.Pu * 1e3
        bd = f.sustained_ratio if not sway else 0.0
        sx = ac.slenderness(sec, "x", Pu, f.Mx_top * 1e6, f.Mx_bot * 1e6, lu_x, kx, bd, sway, transverse)
        sy = ac.slenderness(sec, "y", Pu, f.My_top * 1e6, f.My_bot * 1e6, lu_y, ky, bd, sway, transverse)
        checks = [(sx.Mc, sy.Mc)]
        if sx.Mc_min > sx.Mc:
            checks.append((sx.Mc_min, sy.Mc))
        if sy.Mc_min > sy.Mc:
            checks.append((sx.Mc, sy.Mc_min))
        best = (-1.0, 0.0, 0.0, 0.0)
        for mx, my in checks:
            if math.isinf(mx) or math.isinf(my):
                best = (float("inf"), mx, my, 0.0)
                break
            r, cap = ac.capacity_ratio(surf, Pu, mx, my)
            if r > best[0]:
                best = (r, mx, my, cap)
        ratio, mx, my, cap = best
        out.append({
            "Combo": f.combo, "Pu (kN)": f.Pu,
            "kℓu/r x": sx.klu_r, "δx": sx.delta, "Mux (kN·m)": mx / 1e6,
            "kℓu/r y": sy.klu_r, "δy": sy.delta, "Muy (kN·m)": my / 1e6,
            "φMn ทิศ Mu (kN·m)": cap / 1e6, "D/C": ratio,
        })
        detail.append((f, sx, sy, ratio, mx, my))
    return surf, pd.DataFrame(out), detail


with tab_design:
    cL, cR = st.columns([1, 1])
    with cL:
        st.subheader("วัสดุ")
        m1, m2, m3 = st.columns(3)
        fc_ksc = m1.number_input("f'c (ksc, ทรงกระบอก)", 180.0, 600.0, 280.0, 10.0)
        fc = fc_ksc / KSC_PER_MPA
        m1.caption(f"= {fc:.1f} MPa")
        grade = m2.selectbox("เหล็กยืน", ["SD40", "SD50", "SD30"], index=0)
        fy = ac.STEEL_GRADES[grade]
        m2.caption(f"fy = {fy:.0f} MPa")
        grade_t = m3.selectbox("เหล็กปลอก", ["SR24", "SD40", "SD30"], index=0)
        fyt = ac.STEEL_GRADES[grade_t]
        m3.caption(f"fyt = {fyt:.0f} MPa")

        st.subheader("หน้าตัด")
        shape_th = st.radio("รูปร่าง", ["สี่เหลี่ยม (ปลอกเดี่ยว)", "กลม (ปลอกเดี่ยว)", "กลม (ปลอกเกลียว)"],
                            horizontal=True)
        shape = "rect" if shape_th.startswith("สี่เหลี่ยม") else "circle"
        spiral = "เกลียว" in shape_th
        g1, g2, g3 = st.columns(3)
        if shape == "rect":
            b = g1.number_input("b (mm) — ทิศ x", 150.0, 2000.0, 400.0, 50.0)
            h = g2.number_input("h (mm) — ทิศ y", 150.0, 2000.0, 400.0, 50.0)
        else:
            b = g1.number_input("D (mm)", 200.0, 2500.0, 450.0, 50.0)
            h = b
        cover = g3.number_input("ระยะหุ้มถึงผิวปลอก (mm)", 20.0, 100.0, 40.0, 5.0,
                                help="ประกาศ มท. ตาราง 13: เสาภายใน ≥ 35, สัมผัสดิน/แดดฝน 40–50, หล่อติดดิน 75")
        r1, r2, r3, r4 = st.columns(4)
        db = r1.selectbox("เหล็กยืน DB (mm)", ac.BAR_SIZES, index=ac.BAR_SIZES.index(20))
        if shape == "rect":
            nx = r2.number_input("จำนวนเส้นด้าน b", 2, 20, 3)
            ny = r3.number_input("จำนวนเส้นด้าน h", 2, 20, 3)
            n_circ = 0
        else:
            n_circ = r2.number_input("จำนวนเส้น", 6 if spiral else 4, 40, 8)
            nx = ny = 0
        dt = r4.selectbox("เหล็กปลอก (mm)", [6, 9, 10, 12, 16], index=2)
        s1, s2, s3 = st.columns(3)
        n_legs = s1.number_input("จำนวนขาปลอก (ต่อทิศ)", 2, 8, 2) if shape == "rect" else 2
        sec0 = make_section(shape, b, h, fc, fy, fyt, cover, db, dt, spiral, nx, ny, n_circ)
        s_tie = s2.number_input("ระยะเรียงปลอก (mm)", 25.0, 600.0,
                                float(min(ac.auto_spacing_tie(sec0), 200.0)) if not spiral else 60.0, 5.0)

        st.subheader("ความชะลูด (ACI 318-19 6.2.5 / 6.6.4)")
        k1, k2, k3 = st.columns(3)
        lu_x = k1.number_input("ℓu ดัดรอบแกน x (m)", 0.5, 30.0, 3.2, 0.1) * 1000
        lu_y = k1.number_input("ℓu ดัดรอบแกน y (m)", 0.5, 30.0, 3.2, 0.1) * 1000
        kx = k2.number_input("kx", 0.5, 3.0, 1.0, 0.05)
        ky = k2.number_input("ky", 0.5, 3.0, 1.0, 0.05)
        sway = k3.checkbox("โครงข้อแข็งแบบเซ (sway)", False,
                           help="ระบบเซ: ใส่โมเมนต์ปลายที่ได้จากการวิเคราะห์อันดับสอง หรือขยายด้วย δs แล้วในแท็บ ②")
        transverse = k3.checkbox("มีแรงกระทำทางขวางระหว่างปลาย (Cm = 1)", False)

    sec = sec0
    surf, res, detail = evaluate(sec, forces, lu_x, lu_y, kx, ky, sway, transverse)
    gov_i = int(res["D/C"].values.argmax()) if len(res) else 0

    with cR:
        st.subheader("หน้าตัด")
        fig = go.Figure()
        if shape == "rect":
            fig.add_shape(type="rect", x0=-b / 2, y0=-h / 2, x1=b / 2, y1=h / 2,
                          line=dict(color="#555"), fillcolor="#e6e6e6")
            e = cover + dt / 2
            fig.add_shape(type="rect", x0=-b / 2 + e, y0=-h / 2 + e, x1=b / 2 - e, y1=h / 2 - e,
                          line=dict(color="#1f6feb", width=2))
        else:
            fig.add_shape(type="circle", x0=-b / 2, y0=-b / 2, x1=b / 2, y1=b / 2,
                          line=dict(color="#555"), fillcolor="#e6e6e6")
            e = cover + dt / 2
            fig.add_shape(type="circle", x0=-b / 2 + e, y0=-b / 2 + e, x1=b / 2 - e, y1=b / 2 - e,
                          line=dict(color="#1f6feb", width=2, dash="dot" if spiral else "solid"))
        for x, y in sec.bars:
            fig.add_shape(type="circle", x0=x - db / 2, y0=y - db / 2, x1=x + db / 2, y1=y + db / 2,
                          fillcolor="#c0392b", line=dict(color="#7b241c"))
        lim = max(b, h) / 2 * 1.15
        fig.update_xaxes(range=[-lim, lim], title="x (mm)", scaleanchor="y", zeroline=True)
        fig.update_yaxes(range=[-lim, lim], title="y (mm)")
        fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="white")
        st.plotly_chart(fig, width="stretch")
        q1, q2 = st.columns(2)
        q3, q4 = st.columns(2)
        q1.metric("เหล็กยืน", f"{sec.n_bars}-DB{db:.0f}")
        q2.metric("Ast", f"{sec.Ast:,.0f} mm²")
        q3.metric("ρg", f"{sec.rho * 100:.2f}%")
        q4.metric("φPn,max", f"{surf.phiPn_max / 1e3:,.0f} kN")

    st.divider()
    st.subheader("ผลการตรวจสอบกำลังรับแรงอัดร่วมแรงดัดสองแกน")
    if len(res):
        dc_max = res["D/C"].max()
        ok = dc_max <= 1.0
        (st.success if ok else st.error)(
            f"{'✅ ผ่าน' if ok else '❌ ไม่ผ่าน'} — D/C สูงสุด = {dc_max:.3f} (combo {res.iloc[gov_i]['Combo']})"
        )
        st.dataframe(
            res.style.format({c: ("{:.3f}" if c in ("D/C", "δx", "δy") else "{:,.1f}")
                              for c in res.columns if c != "Combo"})
            .map(lambda v: "background-color:#f8d7da" if isinstance(v, float) and v > 1 else "", subset=["D/C"]),
            width="stretch", hide_index=True)

        f_g, sx_g, sy_g, _, mx_g, my_g = detail[gov_i]
        with st.expander(f"รายละเอียดความชะลูด — combo {f_g.combo}"):
            st.dataframe(pd.DataFrame([{
                "แกน": s.axis, "kℓu/r": s.klu_r, "ขีดจำกัด": s.limit, "เสาชะลูด": "ใช่" if s.slender else "ไม่",
                "M1 (kN·m)": s.M1 / 1e6, "M2 (kN·m)": s.M2 / 1e6, "M2,min (kN·m)": s.M2min / 1e6,
                "Cm": s.Cm, "Pc (kN)": s.Pc / 1e3, "δ": s.delta, "Mc (kN·m)": s.Mc / 1e6,
                "Mc กับ M2,min": s.Mc_min / 1e6, "หมายเหตุ": s.note,
            } for s in (sx_g, sy_g)]).style.format(precision=2), width="stretch", hide_index=True)

        # Interaction diagrams
        p1, p2, p3 = st.columns(3)
        for col, axis, title in ((p1, "x", "P–Mx (ดัดรอบแกน x)"), (p2, "y", "P–My (ดัดรอบแกน y)")):
            cur = ac.uniaxial_curve(surf, axis)
            fig = go.Figure()
            # สาขา neg (แรงอัดด้านลบ) มีโมเมนต์ติดลบอยู่แล้ว — ต่อเป็นวงปิด
            M_all = np.concatenate([cur["Mn_neg"][::-1], cur["Mn_pos"]])
            P_all = np.concatenate([cur["Pn_neg"][::-1], cur["Pn_pos"]])
            fM_all = np.concatenate([cur["phiMn_neg"][::-1], cur["phiMn_pos"]])
            fP_all = np.concatenate([cur["phiPn_neg"][::-1], cur["phiPn_pos"]])
            fig.add_trace(go.Scatter(x=M_all, y=P_all, name="Pn–Mn", line=dict(color="#999", dash="dash")))
            fig.add_trace(go.Scatter(x=fM_all, y=fP_all, name="φPn–φMn", line=dict(color="#1f6feb", width=3)))
            key = "Mux (kN·m)" if axis == "x" else "Muy (kN·m)"
            fig.add_trace(go.Scatter(x=res[key], y=res["Pu (kN)"], mode="markers+text",
                                     text=res["Combo"], textposition="top right", name="Pu, Mu",
                                     marker=dict(color=np.where(res["D/C"] > 1, "#c0392b", "#27ae60"), size=9)))
            fig.update_layout(title=title, xaxis_title="M (kN·m)", yaxis_title="P (kN)", height=430,
                              margin=dict(l=10, r=10, t=40, b=10), showlegend=False)
            col.plotly_chart(fig, width="stretch")
        cont = ac.moment_contour(surf, f_g.Pu * 1e3)
        fig = go.Figure()
        if cont is not None:
            mx_c, my_c = cont
            fig.add_trace(go.Scatter(x=np.append(mx_c, mx_c[0]) / 1e6, y=np.append(my_c, my_c[0]) / 1e6,
                                     name="φMnx–φMny", line=dict(color="#1f6feb", width=3)))
        sgx = 1 if sx_g.M2 >= 0 else -1
        sgy = 1 if sy_g.M2 >= 0 else -1
        fig.add_trace(go.Scatter(x=[0, sgx * mx_g / 1e6], y=[0, sgy * my_g / 1e6], mode="lines+markers",
                                 name="Mu", marker=dict(color="#c0392b", size=10)))
        fig.update_layout(title=f"Mx–My ที่ Pu = {f_g.Pu:,.0f} kN ({f_g.combo})", xaxis_title="Mx (kN·m)",
                          yaxis_title="My (kN·m)", height=430, margin=dict(l=10, r=10, t=40, b=10),
                          showlegend=False)
        fig.update_yaxes(scaleanchor="x")
        p3.plotly_chart(fig, width="stretch")

    # Shear
    st.subheader("แรงเฉือน (ACI 318-19 22.5, 10.7.6.5)")
    sh_rows = []
    worst_sh = 0.0
    for f in forces:
        for dirn, V in (("x", f.Vux), ("y", f.Vuy)):
            r = ac.shear_check(sec, dirn, V * 1e3, f.Pu * 1e3, s_tie, n_legs, phis.shear)
            worst_sh = max(worst_sh, r.ratio)
            sh_rows.append({"Combo": f.combo, "ทิศ": dirn, "Vu (kN)": r.Vu / 1e3, "Nu (kN)": f.Pu,
                            "bw (mm)": r.bw, "d (mm)": r.d, "Vc (kN)": r.Vc / 1e3, "Vs (kN)": r.Vs / 1e3,
                            "φVn (kN)": r.phiVn / 1e3, "Av (mm²)": r.Av, "Av,min (mm²)": r.Av_min,
                            "s,max (mm)": r.s_max, "ต้องเสริมเฉือน": r.needs_reinf,
                            "สมการ Vc": r.eq, "D/C": r.ratio})
    sh_df = pd.DataFrame(sh_rows)
    (st.success if worst_sh <= 1 else st.error)(f"แรงเฉือน D/C สูงสุด = {worst_sh:.3f}")
    with st.expander("ตารางตรวจแรงเฉือน"):
        st.dataframe(sh_df.style.format(precision=2), width="stretch", hide_index=True)
    need_sh = sh_df[sh_df["ต้องเสริมเฉือน"]] if len(sh_df) else sh_df
    # Detailing
    st.subheader("ข้อกำหนดการเสริมเหล็ก")
    chk = ac.detailing_checks(sec, s_tie)
    if len(need_sh):
        s_max_sh = need_sh["s,max (mm)"].min()
        av_ok = bool((need_sh["Av (mm²)"] >= need_sh["Av,min (mm²)"]).all())
        chk.append(ac.Check("ระยะเรียงปลอกสำหรับแรงเฉือน (Vu > 0.5φVc)", f"{s_tie:.0f} mm",
                            f"≤ {s_max_sh:.0f} mm", s_tie <= s_max_sh, "ACI 10.6.2.1 / Table 10.7.6.5.2"))
        chk.append(ac.Check("Av ≥ Av,min (Vu > 0.5φVc)", "ดูตารางแรงเฉือน", "Av ≥ Av,min", av_ok,
                            "ACI 10.6.2.2"))
    det_df = pd.DataFrame([{"รายการ": c.item, "ค่าที่ใช้": c.value, "เกณฑ์": c.limit,
                            "ผล": "✅" if c.ok else "❌", "อ้างอิง": c.ref} for c in chk])
    st.dataframe(det_df, width="stretch", hide_index=True)

    # Auto-design
    st.divider()
    st.subheader("🔧 หาเหล็กยืนที่เหมาะสม (ขนาดหน้าตัดคงที่)")
    if st.button("ค้นหา"):
        cands = []
        for dbi in ac.BAR_SIZES[1:]:
            if shape == "rect":
                layouts = [(i, j) for i in range(2, 9) for j in range(2, 9)]
            else:
                layouts = [(n, 0) for n in range(6 if spiral else 4, 33, 2)]
            for i, j in layouts:
                s_ = make_section(shape, b, h, fc, fy, fyt, cover, dbi, dt, spiral, i, j, i)
                if not (0.01 <= s_.rho <= 0.08):
                    continue
                cands.append((s_.Ast, dbi, i, j, s_))
        cands.sort(key=lambda t: t[0])
        found = []
        prog = st.progress(0.0)
        for k, (Ast, dbi, i, j, s_) in enumerate(cands):
            prog.progress(min(k / max(len(cands), 1), 1.0))
            dchk = ac.detailing_checks(s_, s_tie)
            if not all(c.ok for c in dchk if "ระยะช่องว่างเหล็กยืน" in c.item):
                continue
            _, r_, _ = evaluate(s_, forces, lu_x, lu_y, kx, ky, sway, transverse)
            if r_["D/C"].max() <= 1.0:
                found.append({"เหล็กยืน": f"{s_.n_bars}-DB{dbi}",
                              "การจัด": f"{i}×{j}" if shape == "rect" else f"{i} เส้นรอบวง",
                              "Ast (mm²)": Ast, "ρg (%)": s_.rho * 100, "D/C": r_["D/C"].max()})
                if len(found) >= 5:
                    break
        prog.empty()
        if found:
            st.dataframe(pd.DataFrame(found).style.format(precision=3), hide_index=True, width="stretch")
        else:
            st.warning("ไม่พบการเสริมเหล็กที่ผ่านภายใน ρ ≤ 8% — ควรเพิ่มขนาดหน้าตัดหรือ f'c")

# ---------------------------------------------------------------------------
# ④ Report
# ---------------------------------------------------------------------------
with tab_report:
    st.subheader(f"สรุปรายการคำนวณเสา {col_mark} — {project}")
    if len(res):
        f_g, sx_g, sy_g, dc_g, mx_g, my_g = detail[gov_i]
        det_ok = all(c.ok for c in chk)
        overall = res["D/C"].max() <= 1 and worst_sh <= 1 and det_ok
        lines = [
            f"# รายการคำนวณเสา {col_mark}",
            f"**โครงการ:** {project}",
            "",
            "## เกณฑ์การออกแบบ",
            "- มาตรฐานกำลัง: ACI 318-19 (strain compatibility, stress block 0.85f'c·β1c)",
            f"- Load combination: {combo_set}",
            f"- ตัวคูณลดกำลัง: {phis.name} — ปลอกเดี่ยว {phis.tied}, ปลอกเกลียว {phis.spiral}, "
            f"ดัด {phis.tension}, เฉือน {phis.shear}",
            "- น้ำหนักบรรทุก: กฎกระทรวง พ.ศ. 2566 ข้อ 9–14 / ประกาศ มท. พ.ศ. 2567 ตาราง 2, 4",
            "",
            "## วัสดุและหน้าตัด",
            f"- f'c = {fc_ksc:.0f} ksc ({fc:.1f} MPa), β1 = {ac.beta1(fc):.3f}, Ec = {ac.ec_modulus(fc):,.0f} MPa",
            f"- เหล็กยืน {grade} fy = {fy:.0f} MPa · เหล็กปลอก {grade_t} fyt = {fyt:.0f} MPa",
            f"- หน้าตัด: {shape_th} " + (f"{b:.0f}×{h:.0f} mm" if shape == "rect" else f"D = {b:.0f} mm"),
            f"- เหล็กยืน {sec.n_bars}-DB{db:.0f} (Ast = {sec.Ast:,.0f} mm², ρg = {sec.rho * 100:.2f}%)",
            f"- เหล็กปลอก {'RB' if grade_t == 'SR24' else 'DB'}{dt} @ {s_tie:.0f} mm, ระยะหุ้ม {cover:.0f} mm",
            "",
            "## น้ำหนักบรรทุก (Load takedown)",
            f"- ΣDL = {PD_tk:,.1f} kN ({PD_tk / 9.81:,.1f} tf) · ΣLL หลังลด = {PL_tk:,.1f} kN ({PL_tk / 9.81:,.1f} tf)",
            "",
            "## กำลังรับแรงอัดตามแนวแกน",
            f"- Po = 0.85f'c(Ag − Ast) + fy·Ast = {surf.Po / 1e3:,.0f} kN",
            f"- Pn,max = {0.85 if spiral else 0.80}·Po = {surf.Pn_max / 1e3:,.0f} kN · φPn,max = {surf.phiPn_max / 1e3:,.0f} kN",
            "",
            f"## Combo วิกฤต: {f_g.combo} ({f_g.label})",
            f"- Pu = {f_g.Pu:,.1f} kN · Mux = {mx_g / 1e6:,.1f} kN·m (δx = {sx_g.delta:.3f}) · "
            f"Muy = {my_g / 1e6:,.1f} kN·m (δy = {sy_g.delta:.3f})",
            f"- kℓu/r: x = {sx_g.klu_r:.1f} (ขีดจำกัด {sx_g.limit:.1f}), y = {sy_g.klu_r:.1f} (ขีดจำกัด {sy_g.limit:.1f})",
            f"- **D/C (P–M สองแกน) = {dc_g:.3f}**",
            f"- **D/C แรงเฉือน = {worst_sh:.3f}**",
            "",
            "## ข้อกำหนดการเสริมเหล็ก",
        ] + [f"- {'✅' if c.ok else '❌'} {c.item}: {c.value} ({c.limit}) — {c.ref}" for c in chk] + [
            "",
            f"## สรุป: {'✅ ผ่านเกณฑ์ทุกข้อ' if overall else '❌ ไม่ผ่าน — ต้องแก้ไข'}",
            "",
            "> หมายเหตุ: โปรแกรมไม่ครอบคลุม detailing ระบบต้านแผ่นดินไหว (ACI 318-19 บทที่ 18), "
            "การต่อทาบ/ระยะฝัง และการวิเคราะห์โครงสร้าง — วิศวกรผู้ออกแบบต้องตรวจสอบและรับรองผลเอง",
        ]
        md = "\n".join(lines)
        st.markdown(md)
        d1, d2, d3 = st.columns(3)
        d1.download_button("⬇️ รายการคำนวณ (.md)", md.encode("utf-8"), f"{col_mark}_calc.md", "text/markdown")
        d2.download_button("⬇️ ผลตรวจ P–M (.csv)", res.to_csv(index=False).encode("utf-8-sig"),
                           f"{col_mark}_PM.csv", "text/csv")
        d3.download_button("⬇️ Load takedown (.csv)", td.to_csv(index=False).encode("utf-8-sig"),
                           f"{col_mark}_takedown.csv", "text/csv")
