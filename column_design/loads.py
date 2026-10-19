"""น้ำหนักบรรทุกและ load combination ตามกฎกระทรวงกำหนดการออกแบบโครงสร้างอาคาร พ.ศ. 2566
และประกาศกระทรวงมหาดไทย พ.ศ. 2567 (ลูกบท)

หน่วยภายในโมดูล: น้ำหนักบรรทุกแผ่ kg/m², แรง kN, โมเมนต์ kN·m
"""
from __future__ import annotations

from dataclasses import dataclass, field

KG_TO_KN = 0.00981  # 1 kgf = 9.81 N

# ---------------------------------------------------------------------------
# กฎกระทรวง 2566 ข้อ 11 — น้ำหนักบรรทุกจรขั้นต่ำ (kg/m²)
# key: (กลุ่ม, ส่วนของอาคาร) -> LL ; ชุดที่ห้ามลด LL ตามข้อ 14(1) มี flag no_reduce
# ---------------------------------------------------------------------------
LIVE_LOADS: dict[str, dict[str, tuple[float, bool]]] = {
    "1. ชุมนุม (ห้องสมุด หอประชุม โรงมหรสพ ภัตตาคาร ศาสนสถาน)": {
        "พื้นที่ชุมนุมชน — ที่นั่งยึดติดพื้น": (300, True),
        "พื้นที่ชุมนุมชน — ที่นั่งไม่ยึดติดพื้น": (400, True),
        "ห้องโถง บันได ช่องทางเดิน": (500, True),
        "เวทีและลานแสดง": (500, True),
        "ห้องสมุด — ห้องอ่านหนังสือ": (300, True),
        "ห้องสมุด — ห้องอ่านหนังสือที่มีชั้นวางหนังสือ": (400, True),
        "ห้องสมุด — ห้องเก็บหนังสือ": (600, True),
    },
    "1. ชุมนุม (โรงกีฬา สนามกีฬา อัฒจันทร์ พิพิธภัณฑ์ หอศิลป์)": {
        "ลานที่มีที่นั่งยึดติดพื้น": (300, True),
        "แถวที่นั่งอัฒจันทร์ ที่นั่งกลางแจ้ง": (500, True),
        "โรงกีฬา สนามกีฬา พิพิธภัณฑ์": (500, True),
        "เวทีและลานแสดง": (500, True),
        "ห้องโถง บันได ช่องทางเดิน": (500, True),
    },
    "2. สำนักงาน ธนาคาร": {
        "พื้นที่สำนักงาน": (250, False),
        "ห้องโถง บันได ช่องทางเดิน": (300, False),
        "ห้องเมนเฟรมคอมพิวเตอร์": (500, False),
        "ห้องเก็บเอกสารและพัสดุ": (500, False),
    },
    "2. อาคารพาณิชย์ ตลาด ห้างสรรพสินค้า": {
        "พื้นที่ขายปลีก": (400, False),
        "พื้นที่ขายส่ง": (500, False),
        "ห้องโถง": (500, False),
        "บันได ช่องทางเดิน": (400, False),
        "พื้นที่เก็บของ": (500, False),
    },
    "2. ตึกแถว ห้องแถว": {
        "ส่วนที่ใช้เพื่อการพาณิชย์": (300, False),
        "บันได ช่องทางเดิน": (300, False),
        "ส่วนที่พักอาศัย": (200, False),
    },
    "3. การศึกษา (สถานศึกษา โรงเรียนกวดวิชา)": {
        "ห้องเรียน": (250, True),
        "ห้องเรียนรวม ห้องบรรยาย": (300, True),
        "ห้องทำงาน ห้องเจ้าหน้าที่": (250, True),
        "ห้องทดลอง ห้องครัว ห้องซักรีด": (300, True),
        "ห้องโถง บันได ช่องทางเดิน": (400, True),
        "ห้องคอมพิวเตอร์": (250, True),
        "ห้องเมนเฟรมคอมพิวเตอร์": (500, True),
        "ห้องเก็บเอกสารและพัสดุ": (500, True),
    },
    "4. สถานพยาบาล": {
        "ห้องพักคนไข้พิเศษ": (200, True),
        "ห้องทำงาน ห้องเจ้าหน้าที่": (250, True),
        "ห้องพักผู้ป่วยรวม": (300, True),
        "ห้องฉายรังสี ห้องผ่าตัด ห้องเครื่องมือ": (300, True),
        "ห้องทดลอง ห้องครัว ห้องซักรีด": (300, True),
        "ห้องโถง บันได ช่องทางเดิน": (400, True),
    },
    "5. โรงงานอุตสาหกรรม คลังสินค้า": {
        "พื้นที่เก็บของ คลังสินค้า": (500, True),
        "พื้นที่โรงงานอุตสาหกรรม": (500, True),
    },
    "6. บ้านพักอาศัย": {
        "ห้องต่าง ๆ": (200, False),
        "ระเบียง บันได": (200, False),
    },
    "6. โรงแรม อาคารชุด หอพัก อาคารอยู่อาศัยรวม": {
        "ห้องนอน ห้องนั่งเล่น ห้องน้ำ ห้องแต่งตัว": (200, False),
        "ห้องทำงาน พื้นที่สำนักงาน": (250, False),
        "พื้นที่ให้บริการ (ห้องอาหาร ครัว ซักรีด สโมสร ฯลฯ)": (400, False),
        "ห้องโถง บันได ช่องทางเดิน": (400, False),
        "พื้นที่เก็บของ": (500, False),
    },
    "7. อื่น ๆ": {
        "ลานจอดรถยนต์นั่ง ≤ 7 คน และจักรยานยนต์": (300, True),
        "ลานจอดรถยนต์โดยสารอื่น": (800, True),
        "ลานจอดรถยนต์บรรทุกเปล่า": (800, True),
        "บันไดหนีไฟ": (400, False),
        "ทางเดินเชื่อมระหว่างอาคาร": (500, False),
        "พื้นที่เต้นรำ": (500, False),
        "หลังคา": (50, False),
        "กันสาดคอนกรีต": (100, False),
        "ดาดฟ้า": (200, False),
    },
}

# ประกาศ มท. 2567 ตาราง 2 — หน่วยน้ำหนักรวม (kg/m³)
UNIT_WEIGHTS: dict[str, float] = {
    "คอนกรีตเสริมเหล็ก": 2400,
    "ปูนทราย ปูนก่อ": 2200,
    "อิฐมอญ": 1400,
    "กระจก แก้ว": 2500,
    "เหล็กกล้า": 7850,
    "หินอ่อน": 2640,
    "หินอัคนี": 2640,
    "ทรายชื้น": 2100,
    "ดินเหนียว": 1900,
    "กรวด": 1700,
    "ไม้เนื้อแข็ง": 950,
}

# กฎกระทรวง ข้อ 13 / ประกาศ มท. ตาราง 4 — % ลด LL ตามลำดับชั้นถัดจากหลังคา
LL_REDUCTION_PCT = [0, 0, 0, 10, 20, 30, 40, 50]


def ll_reduction_pct(level_below_roof: int) -> float:
    """level_below_roof: 0 = หลังคา/ดาดฟ้า, 1 = ชั้นที่หนึ่งถัดจากหลังคา, ..."""
    if level_below_roof < 0:
        raise ValueError("level_below_roof must be >= 0")
    return float(LL_REDUCTION_PCT[min(level_below_roof, len(LL_REDUCTION_PCT) - 1)])


def ll_reducible(ll_kg_m2: float, no_reduce_occupancy: bool) -> bool:
    """ข้อ 14: ห้ามลดสำหรับอาคารตาม (1) หรือ LL > 500 kg/m² (2)"""
    return not no_reduce_occupancy and ll_kg_m2 <= 500


@dataclass
class Floor:
    """น้ำหนักบนพื้นหนึ่งชั้นที่ถ่ายลงเสาต้นที่พิจารณา"""
    name: str
    trib_area: float            # m²
    slab_t: float               # m
    sdl: float                  # kg/m² (finishing + งานระบบ + ผนังกระจายเทียบเท่า)
    ll: float                   # kg/m² (ข้อ 11)
    no_reduce: bool = False     # occupancy ตามข้อ 14(1)
    beam_len: float = 0.0       # m ความยาวคานที่ถ่ายลงเสา
    beam_b: float = 0.0         # m
    beam_h: float = 0.0         # m (ความลึกใต้พื้น)
    wall_len: float = 0.0       # m ผนังบนคาน
    wall_w: float = 0.0         # kg/m² ของผนัง (เช่นอิฐมอญครึ่งแผ่นฉาบสองหน้า ~180)
    wall_h: float = 0.0         # m
    col_self: float = 0.0       # kN น้ำหนักเสาชั้นนั้น (คำนวณภายนอก)

    def dead_kn(self, gamma_c: float = 2400) -> float:
        slab = self.trib_area * self.slab_t * gamma_c
        sdl = self.trib_area * self.sdl
        beam = self.beam_len * self.beam_b * self.beam_h * gamma_c
        wall = self.wall_len * self.wall_h * self.wall_w
        return (slab + sdl + beam + wall) * KG_TO_KN + self.col_self

    def live_kn(self) -> float:
        return self.trib_area * self.ll * KG_TO_KN


@dataclass
class TakedownRow:
    name: str
    dl: float
    ll: float
    reduction_pct: float
    ll_reduced: float
    sum_dl: float
    sum_ll: float
    sum_ll_reduced: float


def column_takedown(floors_top_down: list[Floor], gamma_c: float = 2400,
                    apply_reduction: bool = True) -> list[TakedownRow]:
    """สะสมน้ำหนักจากหลังคาลงมา (รายการแรก = หลังคา/ดาดฟ้า)

    การลด LL ตามข้อ 13 นับลำดับชั้นจากหลังคา และยกเว้นตามข้อ 14
    """
    rows: list[TakedownRow] = []
    s_dl = s_ll = s_llr = 0.0
    for i, f in enumerate(floors_top_down):
        dl = f.dead_kn(gamma_c)
        ll = f.live_kn()
        pct = ll_reduction_pct(i) if (apply_reduction and ll_reducible(f.ll, f.no_reduce)) else 0.0
        llr = ll * (1 - pct / 100)
        s_dl += dl
        s_ll += ll
        s_llr += llr
        rows.append(TakedownRow(f.name, dl, ll, pct, llr, s_dl, s_ll, s_llr))
    return rows


# ---------------------------------------------------------------------------
# Load combinations
# ---------------------------------------------------------------------------
@dataclass
class Combo:
    name: str
    factors: dict[str, float] = field(default_factory=dict)  # {"D":1.4,"L":1.7,...}
    ref: str = ""

    def label(self) -> str:
        parts = []
        for k, v in self.factors.items():
            if v == 0:
                continue
            sign = "-" if v < 0 else "+"
            parts.append(f"{sign} {abs(v):g}{k}")
        s = " ".join(parts)
        return s[2:] if s.startswith("+ ") else s


def _sym(base: dict[str, float], key: str, val: float) -> list[dict[str, float]]:
    return [{**base, key: val}, {**base, key: -val}]


def combos_thai_usd(wind: bool = True, seismic: bool = True) -> list[Combo]:
    """กฎกระทรวง 2566 ข้อ 7 (วิธีกำลัง) — W, E ในรูป ± สองทิศ (x, y)"""
    out = [Combo("U1", {"D": 1.4, "L": 1.7}, "ข้อ 7(1)")]
    if wind:
        i = 0
        for d in ("Wx", "Wy"):
            for f in _sym({"D": 1.05, "L": 1.275}, d, 1.6):
                i += 1
                out.append(Combo(f"U2-{i}", f, "ข้อ 7(2)"))
        i = 0
        for d in ("Wx", "Wy"):
            for f in _sym({"D": 0.9}, d, 1.6):
                i += 1
                out.append(Combo(f"U3-{i}", f, "ข้อ 7(2)"))
    if seismic:
        i = 0
        for d in ("Ex", "Ey"):
            for f in _sym({"D": 1.05, "L": 1.275}, d, 1.0):
                i += 1
                out.append(Combo(f"U4-{i}", f, "ข้อ 7(3)"))
        i = 0
        for d in ("Ex", "Ey"):
            for f in _sym({"D": 0.9}, d, 1.0):
                i += 1
                out.append(Combo(f"U5-{i}", f, "ข้อ 7(3)"))
    return out


def combos_aci_318_25(wind: bool = True, seismic: bool = True) -> list[Combo]:
    """ACI 318-25 Table 5.3.1 (ASCE 7 strength) — ใช้เปรียบเทียบ/เมื่อมีเอกสารรับรองตามข้อ 5"""
    out = [Combo("A1", {"D": 1.4}, "5.3.1a"), Combo("A2", {"D": 1.2, "L": 1.6}, "5.3.1b")]
    if wind:
        i = 0
        for d in ("Wx", "Wy"):
            for f in _sym({"D": 1.2, "L": 1.0}, d, 1.0):
                i += 1
                out.append(Combo(f"A4-{i}", f, "5.3.1d"))
        i = 0
        for d in ("Wx", "Wy"):
            for f in _sym({"D": 0.9}, d, 1.0):
                i += 1
                out.append(Combo(f"A6-{i}", f, "5.3.1f"))
    if seismic:
        i = 0
        for d in ("Ex", "Ey"):
            for f in _sym({"D": 1.2, "L": 1.0}, d, 1.0):
                i += 1
                out.append(Combo(f"A5-{i}", f, "5.3.1e"))
        i = 0
        for d in ("Ex", "Ey"):
            for f in _sym({"D": 0.9}, d, 1.0):
                i += 1
                out.append(Combo(f"A7-{i}", f, "5.3.1g"))
    return out


def combos_thai_asd(wind: bool = True, seismic: bool = True) -> list[Combo]:
    """กฎกระทรวง 2566 ข้อ 6 (service) — ใช้ตรวจฐานราก/เสาเข็ม"""
    out = [Combo("S1", {"D": 1.0, "L": 1.0}, "ข้อ 6(1)")]
    if wind:
        i = 0
        for d in ("Wx", "Wy"):
            for f in _sym({"D": 1.0, "L": 0.75}, d, 0.75):
                i += 1
                out.append(Combo(f"S2-{i}", f, "ข้อ 6(2)"))
            for f in _sym({"D": 0.6}, d, 1.0):
                i += 1
                out.append(Combo(f"S2-{i}", f, "ข้อ 6(2)"))
    if seismic:
        i = 0
        for d in ("Ex", "Ey"):
            for f in _sym({"D": 1.0}, d, 0.7):
                i += 1
                out.append(Combo(f"S3-{i}", f, "ข้อ 6(3)"))
            for f in _sym({"D": 1.0, "L": 0.75}, d, 0.525):
                i += 1
                out.append(Combo(f"S3-{i}", f, "ข้อ 6(3)"))
            for f in _sym({"D": 0.6}, d, 0.7):
                i += 1
                out.append(Combo(f"S3-{i}", f, "ข้อ 6(3)"))
    return out


@dataclass
class LoadCase:
    """แรงในเสาจากแต่ละ load case (P อัดเป็นบวก, kN / kN·m)
    M_top/M_bot ใช้สำหรับหา M1, M2 ในการขยายโมเมนต์ (ACI 318-25 6.6.4)"""
    P: float = 0.0
    Mx_top: float = 0.0
    Mx_bot: float = 0.0
    My_top: float = 0.0
    My_bot: float = 0.0
    V2: float = 0.0   # แรงเฉือนทิศ y (ตั้งฉากกับแกน x)
    V3: float = 0.0   # แรงเฉือนทิศ x


@dataclass
class FactoredForce:
    combo: str
    label: str
    Pu: float
    Mx_top: float
    Mx_bot: float
    My_top: float
    My_bot: float
    Vux: float
    Vuy: float
    sustained_ratio: float  # βdns = factored sustained axial / total factored axial


def factor_loads(cases: dict[str, LoadCase], combos: list[Combo]) -> list[FactoredForce]:
    out = []
    for c in combos:
        acc = LoadCase()
        for key, f in c.factors.items():
            lc = cases.get(key)
            if lc is None:
                continue
            acc.P += f * lc.P
            acc.Mx_top += f * lc.Mx_top
            acc.Mx_bot += f * lc.Mx_bot
            acc.My_top += f * lc.My_top
            acc.My_bot += f * lc.My_bot
            acc.V2 += f * lc.V2
            acc.V3 += f * lc.V3
        pd = c.factors.get("D", 0.0) * cases.get("D", LoadCase()).P
        beta = pd / acc.P if acc.P > 0 else 0.0
        out.append(FactoredForce(c.name, c.label(), acc.P, acc.Mx_top, acc.Mx_bot,
                                 acc.My_top, acc.My_bot, acc.V3, acc.V2,
                                 min(max(beta, 0.0), 1.0)))
    return out
