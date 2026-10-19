"""กำลังเสาคอนกรีตเสริมเหล็กตาม ACI 318-19 (หน่วย SI: N, mm, MPa)

- กำลังรับแรงอัดร่วมแรงดัดสองแกน: strain compatibility + Whitney stress block
  (22.2.1–22.2.2) บนตาราง fiber ของคอนกรีต พร้อมการหมุนแกนสะเทิน
- Pn,max (22.4.2.1), φ ตาม strain ที่เหล็กรับแรงดึงสุดขอบ (21.2.2)
- ความชะลูด/การขยายโมเมนต์ระบบไม่เซ (6.2.5, 6.6.4)
- แรงเฉือน (22.5) และข้อกำหนดการเสริมเหล็ก (10.6, 10.7, 25.7)

ชุดตัวคูณ φ เลือกได้: กฎกระทรวง 2566 ข้อ 8 (คู่กับ 1.4D+1.7L) หรือ ACI 318-19 Table 21.2.2
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

ES = 200_000.0      # MPa (20.2.2.2)
ECU = 0.003         # 22.2.2.1

# ขนาดเหล็กข้ออ้อย มอก. 24 (mm) -> พื้นที่ mm²
BAR_SIZES = [10, 12, 16, 20, 25, 28, 32, 36, 40]
STEEL_GRADES = {"SR24": 235.0, "SD30": 295.0, "SD40": 390.0, "SD50": 490.0}


def bar_area(db: float) -> float:
    return math.pi * db ** 2 / 4.0


def beta1(fc: float) -> float:
    """ACI 318-19 Table 22.2.2.4.3"""
    if fc <= 28:
        return 0.85
    if fc >= 55:
        return 0.65
    return 0.85 - 0.05 * (fc - 28) / 7.0


def ec_modulus(fc: float, wc: float = 2400) -> float:
    """19.2.2.1 — Ec = wc^1.5·0.043√f'c (wc kg/m³); normalweight ≈ 4700√f'c"""
    return wc ** 1.5 * 0.043 * math.sqrt(fc)


@dataclass(frozen=True)
class PhiSet:
    name: str
    tied: float
    spiral: float
    tension: float
    shear: float


PHI_THAI_QC = PhiSet("กฎกระทรวง 2566 ข้อ 8 (มีการระบุมาตรฐาน/ควบคุมคุณภาพ)", 0.70, 0.75, 0.90, 0.85)
PHI_THAI_NOQC = PhiSet("กฎกระทรวง 2566 ข้อ 8 (ไม่มีการระบุ)", 0.60, 0.625, 0.75, 0.70)
PHI_ACI = PhiSet("ACI 318-19 Table 21.2.2 / 21.2.1", 0.65, 0.75, 0.90, 0.75)


# ---------------------------------------------------------------------------
# Section
# ---------------------------------------------------------------------------
@dataclass
class Section:
    shape: str              # "rect" | "circle"
    b: float                # mm (แกน x) หรือเส้นผ่านศูนย์กลางเมื่อ circle
    h: float                # mm (แกน y) ; circle: = b
    fc: float               # MPa
    fy: float               # MPa (เหล็กยืน)
    fyt: float              # MPa (เหล็กปลอก)
    cover: float            # mm ถึงผิวเหล็กปลอก
    db: float               # mm เหล็กยืน
    dt: float               # mm เหล็กปลอก
    spiral: bool = False
    bars: np.ndarray = field(default_factory=lambda: np.zeros((0, 2)))  # (n,2) x,y mm

    @property
    def Ag(self) -> float:
        return self.b * self.h if self.shape == "rect" else math.pi * self.b ** 2 / 4

    @property
    def n_bars(self) -> int:
        return len(self.bars)

    @property
    def Ast(self) -> float:
        return self.n_bars * bar_area(self.db)

    @property
    def rho(self) -> float:
        return self.Ast / self.Ag

    @property
    def fy_design(self) -> float:
        # ประกาศ มท. 29(5)(ค): ไม่เกิน 550 MPa (ACI 318-19 Table 20.2.2.4(a) ยอมให้ถึง 690)
        return min(self.fy, 550.0)

    def Ig(self, axis: str) -> float:
        if self.shape == "circle":
            return math.pi * self.b ** 4 / 64
        return self.b * self.h ** 3 / 12 if axis == "x" else self.h * self.b ** 3 / 12

    def r(self, axis: str) -> float:
        """6.2.5.2: 0.30×มิติในทิศที่พิจารณา (สี่เหลี่ยม), 0.25D (วงกลม)"""
        if self.shape == "circle":
            return 0.25 * self.b
        return 0.30 * (self.h if axis == "x" else self.b)

    def depth(self, axis: str) -> float:
        """มิติในทิศทางที่ทำให้เกิดโมเมนต์รอบแกน axis"""
        if self.shape == "circle":
            return self.b
        return self.h if axis == "x" else self.b


def rect_bars(b: float, h: float, cover: float, dt: float, db: float,
              nx: int, ny: int) -> np.ndarray:
    """จัดเหล็กรอบรูปสี่เหลี่ยม: nx เส้นต่อด้าน b (รวมมุม), ny เส้นต่อด้าน h (รวมมุม)"""
    if nx < 2 or ny < 2:
        raise ValueError("ต้องมีอย่างน้อย 2 เส้นต่อด้าน")
    e = cover + dt + db / 2
    xs = np.linspace(-b / 2 + e, b / 2 - e, nx)
    ys = np.linspace(-h / 2 + e, h / 2 - e, ny)
    pts = set()
    for x in xs:
        pts.add((round(x, 6), round(ys[0], 6)))
        pts.add((round(x, 6), round(ys[-1], 6)))
    for y in ys:
        pts.add((round(xs[0], 6), round(y, 6)))
        pts.add((round(xs[-1], 6), round(y, 6)))
    return np.array(sorted(pts))


def circle_bars(D: float, cover: float, dt: float, db: float, n: int) -> np.ndarray:
    rr = D / 2 - cover - dt - db / 2
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False) + np.pi / 2
    return np.column_stack([rr * np.cos(ang), rr * np.sin(ang)])


def _concrete_fibers(sec: Section, n: int = 40) -> tuple[np.ndarray, np.ndarray]:
    if sec.shape == "rect":
        dx, dy = sec.b / n, sec.h / n
        xs = -sec.b / 2 + dx * (np.arange(n) + 0.5)
        ys = -sec.h / 2 + dy * (np.arange(n) + 0.5)
        X, Y = np.meshgrid(xs, ys)
        pts = np.column_stack([X.ravel(), Y.ravel()])
        area = np.full(len(pts), dx * dy)
        return pts, area
    # circle: แบ่งเป็นวงแหวน × เซกเตอร์ (พื้นที่แม่นยำ)
    R = sec.b / 2
    nr, nt = n // 2, 2 * n
    r_edges = np.linspace(0, R, nr + 1)
    t = (np.arange(nt) + 0.5) * 2 * np.pi / nt
    pts, area = [], []
    for i in range(nr):
        r0, r1 = r_edges[i], r_edges[i + 1]
        rc = (2 / 3) * (r1 ** 3 - r0 ** 3) / (r1 ** 2 - r0 ** 2)
        a = math.pi * (r1 ** 2 - r0 ** 2) / nt
        pts.append(np.column_stack([rc * np.cos(t), rc * np.sin(t)]))
        area.append(np.full(nt, a))
    return np.vstack(pts), np.concatenate(area)


# ---------------------------------------------------------------------------
# Interaction surface
# ---------------------------------------------------------------------------
@dataclass
class Surface:
    """ผลลัพธ์บนตาราง (มุมแกนสะเทิน α) × (ความลึก c)
    Pn, Mnx, Mny: กำลังระบุ (N, N·mm) ; phi ; eps_t"""
    alphas: np.ndarray
    Pn: np.ndarray
    Mnx: np.ndarray
    Mny: np.ndarray
    phi: np.ndarray
    eps_t: np.ndarray
    Po: float
    Pn_max: float
    phi_c: float
    Pnt: float          # กำลังรับแรงดึงล้วน (ลบ)

    @property
    def phiPn_max(self) -> float:
        return self.phi_c * self.Pn_max

    def phiPn(self) -> np.ndarray:
        return self.phi * self.Pn

    def phiPn_capped(self) -> np.ndarray:
        return np.minimum(self.phi * self.Pn, self.phiPn_max)


def phi_from_strain(eps_t: np.ndarray, eps_ty: float, phi_c: float, phi_t: float) -> np.ndarray:
    """21.2.2: compression-controlled εt ≤ εty ; tension-controlled εt ≥ εty + 0.003"""
    return np.clip(phi_c + (phi_t - phi_c) * (eps_t - eps_ty) / 0.003, phi_c, phi_t)


def build_surface(sec: Section, phis: PhiSet, n_alpha: int = 72, n_c: int = 90,
                  n_fiber: int = 40) -> Surface:
    fc, fy = sec.fc, sec.fy_design
    b1 = beta1(fc)
    cpts, carea = _concrete_fibers(sec, n_fiber)
    bars = sec.bars
    As = bar_area(sec.db)
    eps_ty = fy / ES
    phi_c = phis.spiral if sec.spiral else phis.tied

    Ag = sec.Ag
    Ast = sec.Ast
    Po = 0.85 * fc * (Ag - Ast) + fy * Ast            # 22.4.2.2
    Pn_max = (0.85 if sec.spiral else 0.80) * Po       # 22.4.2.1
    Pnt = -fy * Ast                                     # 22.4.3.1

    alphas = np.linspace(0, 2 * np.pi, n_alpha, endpoint=False)
    size = max(sec.b, sec.h)
    # c ตั้งแต่เล็กมาก (เกือบดึงล้วน) ถึงใหญ่มาก (อัดล้วน)
    cs = np.concatenate([np.geomspace(0.01 * size, 1.0 * size, n_c - 15),
                         np.geomspace(1.05 * size, 30 * size, 15)])

    shp = (n_alpha, len(cs))
    Pn = np.empty(shp)
    Mx = np.empty(shp)
    My = np.empty(shp)
    et = np.empty(shp)
    for i, a in enumerate(alphas):
        u = np.array([math.cos(a), math.sin(a)])  # ชี้ไปด้านรับแรงอัด
        tc = cpts @ u
        tb = bars @ u
        # ขอบรับแรงอัดสุดของหน้าตัดจริง (ไม่ใช่จุดกึ่งกลาง fiber)
        if sec.shape == "rect":
            tmax = abs(u[0]) * sec.b / 2 + abs(u[1]) * sec.h / 2
        else:
            tmax = sec.b / 2
        dc = tmax - tc            # (nf,)
        dbars = tmax - tb         # (nb,)
        C = cs[:, None]
        # คอนกรีต: stress block ความลึก a = β1c (วัดตั้งฉากแกนสะเทิน)
        inblock = dc[None, :] <= b1 * C
        Fc = np.where(inblock, 0.85 * fc * carea[None, :], 0.0)
        # เหล็ก
        eps = ECU * (C - dbars[None, :]) / C
        fs = np.clip(eps * ES, -fy, fy)
        disp = np.where(dbars[None, :] <= b1 * C, 0.85 * fc, 0.0)  # หักคอนกรีตที่ถูกแทนที่
        Fs = (fs - disp) * As
        Pn[i] = Fc.sum(1) + Fs.sum(1)
        Mx[i] = Fc @ cpts[:, 1] + Fs @ bars[:, 1]
        My[i] = Fc @ cpts[:, 0] + Fs @ bars[:, 0]
        et[i] = -eps.min(axis=1)  # tensile strain ที่เหล็กชั้นนอกสุด (บวก = ดึง)
    phi = phi_from_strain(et, eps_ty, phi_c, phis.tension)
    return Surface(alphas, Pn, Mx, My, phi, et, Po, Pn_max, phi_c, Pnt)


def moment_contour(surf: Surface, Pu: float) -> tuple[np.ndarray, np.ndarray] | None:
    """เส้นขอบ (φMnx, φMny) ที่ระดับ Pu (N) — None ถ้า Pu > φPn,max หรือ < φPnt"""
    if Pu > surf.phiPn_max * (1 + 1e-9):
        return None
    phiPn = surf.phiPn()
    mx, my = [], []
    for i in range(len(surf.alphas)):
        p = phiPn[i]
        order = np.argsort(p)
        p_s = p[order]
        if Pu < p_s[0] or Pu > p_s[-1]:
            return None
        mx.append(np.interp(Pu, p_s, (surf.phi[i] * surf.Mnx[i])[order]))
        my.append(np.interp(Pu, p_s, (surf.phi[i] * surf.Mny[i])[order]))
    return np.array(mx), np.array(my)


def capacity_ratio(surf: Surface, Pu: float, Mux: float, Muy: float) -> tuple[float, float]:
    """D/C ของโมเมนต์ลัพธ์ที่ Pu คงที่ (หน่วย N, N·mm)
    คืนค่า (ratio, φMn ในทิศเดียวกับ Mu)"""
    if Pu > surf.phiPn_max:
        return Pu / surf.phiPn_max, 0.0
    phi_t_min = surf.phi.max()
    if Pu < phi_t_min * surf.Pnt:
        return Pu / (phi_t_min * surf.Pnt), 0.0
    cont = moment_contour(surf, Pu)
    if cont is None:
        return float("inf"), 0.0
    mx, my = cont
    Mu = math.hypot(Mux, Muy)
    th = np.arctan2(my, mx)
    rad = np.hypot(mx, my)
    order = np.argsort(th)
    th_s, r_s = th[order], rad[order]
    th_s = np.concatenate([th_s[-1:] - 2 * np.pi, th_s, th_s[:1] + 2 * np.pi])
    r_s = np.concatenate([r_s[-1:], r_s, r_s[:1]])
    if Mu < 1e-9:
        return 0.0, float(r_s.min())
    t = math.atan2(Muy, Mux)
    cap = float(np.interp(t, th_s, r_s))
    return (Mu / cap if cap > 0 else float("inf")), cap


def uniaxial_curve(surf: Surface, axis: str) -> dict[str, np.ndarray]:
    """เส้นโค้ง P–M รอบแกน x (α=90°/270°) หรือ y (α=0°/180°) สำหรับวาดกราฟ
    คืนค่าเป็น kN, kN·m"""
    def idx(target):
        return int(np.argmin(np.abs(((surf.alphas - target + np.pi) % (2 * np.pi)) - np.pi)))
    if axis == "x":
        i_pos, i_neg, key = idx(np.pi / 2), idx(3 * np.pi / 2), "Mnx"
    else:
        i_pos, i_neg, key = idx(0.0), idx(np.pi), "Mny"
    M = getattr(surf, key)
    out = {}
    for tag, i in (("pos", i_pos), ("neg", i_neg)):
        out[f"Pn_{tag}"] = surf.Pn[i] / 1e3
        out[f"Mn_{tag}"] = M[i] / 1e6
        out[f"phiPn_{tag}"] = np.minimum(surf.phi[i] * surf.Pn[i], surf.phiPn_max) / 1e3
        out[f"phiMn_{tag}"] = surf.phi[i] * M[i] / 1e6
    return out


# ---------------------------------------------------------------------------
# Slenderness — ACI 318-19 6.2.5 / 6.6.4 (ระบบไม่เซ)
# ---------------------------------------------------------------------------
@dataclass
class SlenderResult:
    axis: str
    klu_r: float
    limit: float
    slender: bool
    M1: float
    M2: float
    M2min: float
    Cm: float
    Pc: float
    delta: float
    Mc: float          # โมเมนต์ออกแบบจาก M2 จริง (ขยายแล้ว)
    Mc_min: float      # โมเมนต์ออกแบบเมื่อคิด M2,min ในแกนนี้ (ไม่ต้องพร้อมกันสองแกน)
    note: str = ""


def slenderness(sec: Section, axis: str, Pu: float, M_top: float, M_bot: float,
                lu: float, k: float, beta_dns: float, sway: bool = False,
                transverse_load: bool = False) -> SlenderResult:
    """หน่วย: N, N·mm, mm

    M_top/M_bot เป็นค่าจากแผนภาพโมเมนต์ภายใน (เช่น M3 ของ ETABS ที่ปลาย i/j):
    เครื่องหมายเดียวกัน = ดัดโค้งทางเดียว (single curvature) → M1/M2 < 0
    เครื่องหมายต่างกัน = ดัดโค้งสองทาง (double curvature) → M1/M2 > 0
    ระบบเซ: ให้ใส่โมเมนต์ปลายที่ขยายด้วย δs แล้ว (6.6.4.6) — ฟังก์ชันนี้ตรวจตลอดความยาวเสา"""
    r = sec.r(axis)
    klu_r = k * lu / r
    if abs(M_top) >= abs(M_bot):
        M2, M1 = M_top, M_bot
    else:
        M2, M1 = M_bot, M_top
    ratio = 0.0 if abs(M2) < 1e-9 else (abs(M1) / abs(M2)) * (-1 if M1 * M2 > 0 else 1)
    limit = 22.0 if sway else min(34 + 12 * ratio, 40.0)        # 6.2.5.1
    M2min = Pu * (15 + 0.03 * sec.depth(axis))                  # 6.6.4.5.4
    absM2 = abs(M2)
    Ec = ec_modulus(sec.fc)
    EI = 0.4 * Ec * sec.Ig(axis) / (1 + beta_dns)               # 6.6.4.4.4(a)
    Pc = math.pi ** 2 * EI / (k * lu) ** 2                      # 6.6.4.4.2
    Cm = 1.0 if transverse_load else 0.6 - 0.4 * ratio          # 6.6.4.5.3
    if klu_r <= limit:
        return SlenderResult(axis, klu_r, limit, False, M1, M2, M2min, Cm, Pc, 1.0,
                             absM2, absM2, "เสาสั้น — ไม่ต้องขยายโมเมนต์ (6.2.5.1)")
    note = "kℓu/r > 100 ต้องวิเคราะห์อันดับสอง (6.2.6)" if klu_r > 100 else ""
    if Pu >= 0.75 * Pc:
        inf = float("inf")
        return SlenderResult(axis, klu_r, limit, True, M1, M2, M2min, Cm, Pc, inf, inf, inf,
                             "Pu ≥ 0.75Pc — เสาไม่มีเสถียรภาพ ต้องขยายหน้าตัด")

    def mag(cm: float) -> float:
        return max(cm / (1 - Pu / (0.75 * Pc)), 1.0)           # 6.6.4.5.2

    delta = mag(Cm)
    Mc = delta * absM2
    if absM2 < M2min:
        Mc_min = mag(1.0) * M2min
        note = "; ".join(filter(None, [note, "M2 < M2,min → ตรวจแยกด้วย M2,min, Cm = 1.0"]))
    else:
        Mc_min = Mc
    return SlenderResult(axis, klu_r, limit, True, M1, M2, M2min, Cm, Pc, delta, Mc, Mc_min, note)


# ---------------------------------------------------------------------------
# Shear — ACI 318-19 22.5
# ---------------------------------------------------------------------------
@dataclass
class ShearResult:
    direction: str
    Vu: float
    bw: float
    d: float
    Vc: float
    Vs: float
    phiVn: float
    Av: float
    Av_min: float
    s_max: float
    ratio: float
    eq: str
    needs_reinf: bool  # Vu > 0.5φVc → ต้องมี Av,min และ s ตาม Table 10.7.6.5.2 (10.6.2.1)


def shear_check(sec: Section, direction: str, Vu: float, Nu: float, s: float,
                n_legs: int, phi_v: float, lam: float = 1.0) -> ShearResult:
    """direction 'x': แรงเฉือนทิศ x (bw = h, d จากด้าน b) ; 'y': bw = b
    Nu อัดเป็นบวก (N) ; s ระยะเรียงเหล็กปลอก (mm)"""
    fc = min(sec.fc, 69.0)  # √f'c ≤ 8.3 MPa (22.5.3.1)
    fyt = min(sec.fyt, 420.0)  # 20.2.2.4
    if sec.shape == "circle":
        bw, d = sec.b, 0.8 * sec.b                              # 22.5.2.2
        legs = 2
    else:
        e = sec.cover + sec.dt + sec.db / 2
        if direction == "x":
            bw, d = sec.h, sec.b - e
        else:
            bw, d = sec.b, sec.h - e
        legs = n_legs
    Av = legs * bar_area(sec.dt)
    Av_min = max(0.062 * math.sqrt(fc), 0.35) * bw * s / fyt   # 10.6.2.2
    nu_term = min(Nu / (6 * sec.Ag), 0.05 * fc)                   # 22.5.5.1.2 (ดึงเป็นลบ)
    # ρw ใช้เหล็กครึ่งหนึ่งเป็นเหล็กรับแรงดึง (ประมาณ)
    rho_w = (sec.Ast / 2) / (bw * d)
    if Av >= Av_min:
        Vc = (0.17 * lam * math.sqrt(fc) + nu_term) * bw * d
        eq = "22.5.5.1(a)"
    else:
        ls = min(math.sqrt(2 / (1 + 0.004 * d)), 1.0)
        Vc = (0.66 * ls * lam * rho_w ** (1 / 3) * math.sqrt(fc) + nu_term) * bw * d
        eq = "22.5.5.1(c) λs"
    Vc = max(min(Vc, 0.42 * lam * math.sqrt(fc) * bw * d), 0.0)
    Vs = Av * fyt * d / s                                         # 22.5.8.5.3
    Vs = min(Vs, 0.66 * math.sqrt(fc) * bw * d)                   # 22.5.1.2
    phiVn = phi_v * (Vc + Vs)
    if Vs > 0.33 * math.sqrt(fc) * bw * d:                        # Table 10.7.6.5.2
        s_max = min(d / 4, 300.0)
    else:
        s_max = min(d / 2, 600.0)
    ratio = abs(Vu) / phiVn if phiVn > 0 else float("inf")
    needs = abs(Vu) > 0.5 * phi_v * Vc
    return ShearResult(direction, abs(Vu), bw, d, Vc, Vs, phiVn, Av, Av_min, s_max, ratio, eq, needs)


# ---------------------------------------------------------------------------
# Detailing — ACI 318-19 10.6, 10.7, 25.7 + ประกาศ มท. 2567 ข้อ 29(11)
# ---------------------------------------------------------------------------
@dataclass
class Check:
    item: str
    value: str
    limit: str
    ok: bool
    ref: str


def min_tie_size(db: float) -> float:
    """ประกาศ มท. 29(11)(จ)3)ก) — เข้มกว่า ACI 25.7.2.2 สำหรับเหล็กเล็ก"""
    if db <= 12:
        return 6
    if db <= 20:
        return 9
    if db <= 28:
        return 10
    return 12


def detailing_checks(sec: Section, s_tie: float) -> list[Check]:
    out: list[Check] = []
    rho = sec.rho
    out.append(Check("อัตราส่วนเหล็กยืน ρg", f"{rho * 100:.2f}%", "1% – 8%",
                     0.01 <= rho <= 0.08, "ACI 10.6.1.1 / มท. 29(11)(จ)1)ก)"))
    if rho > 0.04:
        out.append(Check("ρg สำหรับการต่อทาบ", f"{rho * 100:.2f}%", "แนะนำ ≤ 4% เพื่อการต่อทาบ",
                         False, "ACI R10.6.1.1 (คำแนะนำ)"))
    nmin = 6 if sec.spiral else 4
    out.append(Check("จำนวนเหล็กยืน", f"{sec.n_bars}", f"≥ {nmin}", sec.n_bars >= nmin,
                     "ACI 10.7.3.1 / มท. 29(11)(จ)1)ข)"))
    dmin = min(sec.b, sec.h)
    out.append(Check("มิติเล็กสุดของเสา", f"{dmin:.0f} mm", "≥ 200 mm (นอกเขตแผ่นดินไหว)",
                     dmin >= 200, "มท. 29(11)(ข)"))
    out.append(Check("ระยะหุ้มเหล็กปลอก", f"{sec.cover:.0f} mm", "≥ 35 mm (ภายใน) / 40–50 (แดดฝน) / 75 (หล่อติดดิน)",
                     sec.cover >= 35, "มท. ตาราง 13 / ACI 20.5.1.3"))
    # ระยะช่องว่างเหล็กยืน ACI 25.2.3: ≥ max(40 mm, 1.5db, 4/3 dagg)
    if sec.n_bars >= 2:
        diff = sec.bars[:, None, :] - sec.bars[None, :, :]
        dist = np.hypot(diff[..., 0], diff[..., 1])
        np.fill_diagonal(dist, np.inf)
        clear = dist.min() - sec.db
        req = max(40.0, 1.5 * sec.db)
        out.append(Check("ระยะช่องว่างเหล็กยืน", f"{clear:.0f} mm", f"≥ {req:.0f} mm",
                         clear >= req, "ACI 25.2.3"))
    if sec.spiral:
        dch = sec.b - 2 * sec.cover
        Ach = math.pi * dch ** 2 / 4
        rho_s_req = 0.45 * (sec.Ag / Ach - 1) * sec.fc / min(sec.fyt, 690.0)  # Eq. 25.7.3.3
        rho_s = 4 * bar_area(sec.dt) / (dch * s_tie)
        out.append(Check("ρs เหล็กปลอกเกลียว", f"{rho_s:.4f}", f"≥ {rho_s_req:.4f}",
                         rho_s >= rho_s_req, "ACI 25.7.3.3"))
        clr = s_tie - sec.dt
        out.append(Check("ระยะช่องว่างปลอกเกลียว", f"{clr:.0f} mm", "25 – 75 mm",
                         25 <= clr <= 75, "ACI 25.7.3.1 / มท. 29(11)(จ)2)ค)"))
        out.append(Check("ขนาดเหล็กปลอกเกลียว", f"{sec.dt:.0f} mm", "≥ 9.5 mm (ACI) / ≥ 6 mm (มท.)",
                         sec.dt >= 9.5, "ACI 25.7.3.2 / มท. 29(11)(จ)2)ข)"))
    else:
        tmin = min_tie_size(sec.db)
        out.append(Check("ขนาดเหล็กปลอก", f"{sec.dt:.0f} mm", f"≥ {tmin:.0f} mm",
                         sec.dt >= tmin, "มท. 29(11)(จ)3)ก) / ACI 25.7.2.2"))
        smax = min(16 * sec.db, 48 * sec.dt, dmin)
        out.append(Check("ระยะเรียงเหล็กปลอก", f"{s_tie:.0f} mm",
                         f"≤ min(16db, 48dt, มิติเล็กสุด) = {smax:.0f} mm",
                         s_tie <= smax, "ACI 25.7.2.1 / มท. 29(11)(จ)3)ข)"))
    return out


def auto_spacing_tie(sec: Section) -> float:
    dmin = min(sec.b, sec.h)
    s = min(16 * sec.db, 48 * sec.dt, dmin)
    return math.floor(s / 25) * 25
