"""
ATC 分類對照表

ATC（解剖學治療學及化學分類系統）標準分類

第一層級（解剖學主群）：
- A: 消化道及代謝
- B: 血液及造血器官
- C: 心血管系統
- D: 皮膚用藥
- G: 泌尿生殖系統及性激素
- H: 系統性荷爾蒙製劑
- J: 抗感染藥物
- L: 抗腫瘤及免疫調節劑
- M: 肌肉骨骼系統
- N: 神經系統
- P: 寄生蟲防治
- R: 呼吸系統
- S: 感覺器官
- V: 其他
"""

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ATCCategory:
    """ATC 分類"""

    code: str
    name_cn: str
    name_en: str
    description: str


ATC_CLASSIFICATIONS: Dict[str, ATCCategory] = {
    # ===== 第一層級：解剖學主群 =====
    # A - 消化道及代謝
    "A": ATCCategory(
        "A", "消化道及代謝", "Alimentary tract and metabolism", "消化道、代謝、營養相關藥物"
    ),
    "A01": ATCCategory("A01", "口腔局部用藥", "Stomatological preparations", "口腔、牙齒用藥"),
    "A02": ATCCategory(
        "A02", "治療胃酸相關疾病", "Drugs for acid related disorders", "制酸劑、潰癨用藥"
    ),
    "A03": ATCCategory(
        "A03",
        "功能性胃腸疾病用藥",
        "Drugs for functional gastrointestinal disorders",
        "解痙攣、抗脹氣",
    ),
    "A04": ATCCategory("A04", "止吐劑及止暈劑", "Antiemetics and antinauseants", "嘔吐、暈眩用藥"),
    "A05": ATCCategory("A05", "膽囊及膽道疾病用藥", "Bile and liver therapy", "膽囊、膽道用藥"),
    "A06": ATCCategory("A06", "輕瀉劑", "Laxatives", "便秘用藥"),
    "A07": ATCCategory(
        "A07",
        "止瀉劑、抗腸道發炎及抗菌劑",
        "Antidiarrheals, antiinflammatory/antiinfective intestinal",
        "腹瀉、腸道發炎用藥",
    ),
    "A08": ATCCategory(
        "A08", "減肥藥（不含飲食控制）", "Antiobesity preparations, excl. diets", "減肥藥物"
    ),
    "A09": ATCCategory("A09", "消化劑，包括酵素", "Digestives, incl. enzymes", "助消化、酶製劑"),
    "A10": ATCCategory("A10", "糖尿病用藥", "Drugs used in diabetes", "胰島素、降血糖藥"),
    "A11": ATCCategory("A11", "維生素", "Vitamins", "維生素製劑"),
    "A12": ATCCategory("A12", "礦物質補充劑", "Mineral supplements", "鈣、鐵、鎂等礦物質"),
    "A13": ATCCategory("A13", "一般營養增強劑", "Tonics", "營養增強劑"),
    # B - 血液及造血器官
    "B": ATCCategory(
        "B", "血液及造血器官", "Blood and blood forming organs", "抗血栓、止血、貧血用藥"
    ),
    "B01": ATCCategory("B01", "抗血栓藥", "Antithrombotic agents", "抗凝血、抗血小板"),
    "B02": ATCCategory("B02", "抗出血劑", "Antihemorrhagics", "止血、抗纖維蛋白溶解"),
    "B03": ATCCategory("B03", "抗貧血製劑", "Antianemic preparations", "鐵劑、維生素B12、葉酸"),
    "B05": ATCCategory(
        "B05", "血液替代品及灌注液", "Blood substitutes and perfusion solutions", "點滴、生理食鹽水"
    ),
    # C - 心血管系統
    "C": ATCCategory("C", "心血管系統", "Cardiovascular system", "心臟、血壓、血管用藥"),
    "C01": ATCCategory("C01", "心臟治療用藥", "Cardiac therapy", "強心劑、抗心律不整"),
    "C02": ATCCategory("C02", "抗高血壓藥", "Antihypertensives", "血壓用藥"),
    "C03": ATCCategory("C03", "利尿劑", "Diuretics", "排水、消水腫"),
    "C04": ATCCategory("C04", "周邊血管擴張劑", "Peripheral vasodilators", "末梢血管循環"),
    "C05": ATCCategory("C05", "血管保護劑", "Vasoprotectives", "痔瘡、靜脈曲張"),
    "C07": ATCCategory("C07", "β-阻斷劑", "Beta blocking agents", "心絞痛、心律、血壓"),
    "C08": ATCCategory("C08", "鈣離子通道阻斷劑", "Calcium channel blockers", "高血壓、心絞痛"),
    "C09": ATCCategory(
        "C09",
        "作用於腎素-血管張力素系統藥物",
        "Agents acting on the renin-angiotensin system",
        "ACE抑制劑、血管張力素受體阻斷劑",
    ),
    "C10": ATCCategory("C10", "血脂調節劑", "Lipid modifying agents", "降膽固醇、三酸甘油酯"),
    # D - 皮膚用藥
    "D": ATCCategory("D", "皮膚用藥", "Dermatologicals", "皮膚、軟組織用藥"),
    "D01": ATCCategory(
        "D01", "抗黴菌劑（皮膚科用）", "Antifungals for dermatological use", "癬、黴菌感染"
    ),
    "D02": ATCCategory(
        "D02", "鎮痛及消炎劑（皮膚科用）", "Emollients and protectives", "皮膚止痛、保護"
    ),
    "D03": ATCCategory("D03", "傷口治療劑", "Wound healing agents", "傷口癒合"),
    "D04": ATCCategory(
        "D04", "止癢劑（舒緩用）", "Antipruritics, incl. antihistamines", "皮膚止癢"
    ),
    "D05": ATCCategory("D05", "抗乾癬藥", "Antipsoriatics", "乾癬用藥"),
    "D06": ATCCategory(
        "D06",
        "抗生素及化療劑（皮膚科用）",
        "Antibiotics and chemotherapeutics for dermatological use",
        "皮膚感染",
    ),
    "D07": ATCCategory(
        "D07",
        "皮質類固醇（皮膚科用）",
        "Corticosteroids, dermatological preparations",
        "皮膚類固醇",
    ),
    "D08": ATCCategory("D08", "消毒及除菌劑", "Antiseptics and disinfectants", "消毒、傷口清潔"),
    "D10": ATCCategory("D10", "抗痤瘡製劑", "Anti-acne preparations", "青春痘、面皰"),
    "D11": ATCCategory(
        "D11", "其他皮膚科製劑", "Other dermatological preparations", "脫毛、狐臭、禿頭"
    ),
    # G - 泌尿生殖系統及性激素
    "G": ATCCategory(
        "G", "泌尿生殖系統及性激素", "Genitourinary system and sex hormones", "泌尿、性激素用藥"
    ),
    "G01": ATCCategory(
        "G01",
        "婦科抗感染及消毒劑",
        "Gynecological antiinfectives and antiseptics",
        "陰道感染、發炎",
    ),
    "G02": ATCCategory("G02", "其他婦科用藥", "Other gynecologicals", "調經、避孕"),
    "G03": ATCCategory(
        "G03",
        "性激素及調制生殖系統藥物",
        "Sex hormones and modulators of the genital system",
        "荷爾蒙、避孕",
    ),
    "G04": ATCCategory("G04", "泌尿系統用藥", "Urologicals", "攝護腺、膀胱"),
    # H - 系統性荷爾蒙製劑
    "H": ATCCategory(
        "H",
        "系統性荷爾蒙製劑",
        "Systemic hormonal preparations, excl. sex hormones",
        "荷爾蒙、甲狀腺、腎上腺",
    ),
    "H01": ATCCategory(
        "H01",
        "腦下垂體及下視丘激素",
        "Pituitary and hypothalamic hormones and analogues",
        "腦下垂體激素",
    ),
    "H02": ATCCategory(
        "H02", "皮質類固醇（全身性）", "Corticosteroids for systemic use", "類固醇、免疫抑制"
    ),
    "H03": ATCCategory("H03", "甲狀腺治療劑", "Thyroid therapy", "甲狀腺"),
    "H04": ATCCategory("H04", "胰島素及昇血糖藥", "Pancreatic hormones", "昇血糖素"),
    "H05": ATCCategory("H05", "鈣離子平衡用藥", "Calcium homeostasis", "副甲狀腺"),
    # J - 抗感染藥物
    "J": ATCCategory(
        "J", "抗感染藥物", "Antiinfectives for systemic use", "抗生素、抗病毒、抗黴菌"
    ),
    "J01": ATCCategory("J01", "抗菌劑（全身性）", "Antibacterials for systemic use", "抗生素"),
    "J02": ATCCategory(
        "J02", "抗黴菌劑（全身性）", "Antimycotics for systemic use", "口服/注射抗黴菌"
    ),
    "J04": ATCCategory("J04", "抗分支桿菌藥物", "Antimycobacterials", "肺結核"),
    "J05": ATCCategory(
        "J05", "抗病毒劑（全身性）", "Antivirals for systemic use", "愛滋、B型肝炎、C型肝炎"
    ),
    "J06": ATCCategory(
        "J06", "免疫血清及免疫球蛋白", "Immune sera and immunoglobulins", "疫苗、免疫球蛋白"
    ),
    "J07": ATCCategory("J07", "疫苗", "Vaccines", "預防針"),
    # L - 抗腫瘤及免疫調節劑
    "L": ATCCategory(
        "L", "抗腫瘤及免疫調節劑", "Antineoplastic and immunomodulating agents", "化療、免疫調節"
    ),
    "L01": ATCCategory("L01", "抗腫瘤藥", "Antineoplastic agents", "化療藥物"),
    "L02": ATCCategory("L02", "內分泌治療", "Endocrine therapy", "荷爾蒙治療"),
    "L03": ATCCategory("L03", "免疫刺激劑", "Immunostimulants", "免疫增強"),
    "L04": ATCCategory("L04", "免疫抑制劑", "Immunosuppressants", "類風濕、移植"),
    # M - 肌肉骨骼系統
    "M": ATCCategory("M", "肌肉骨骼系統", "Musculo-skeletal system", "止痛、消炎、骨關節"),
    "M01": ATCCategory(
        "M01", "抗發炎及抗風濕藥", "Antiinflammatory and antirheumatic products", "止痛、退燒、消炎"
    ),
    "M02": ATCCategory(
        "M02", "局部止痛及消炎劑", "Topical products for joint and muscular pain", "酸痛藥膏、貼布"
    ),
    "M03": ATCCategory("M03", "肌肉鬆弛劑", "Muscle relaxants", "肌肉痙攣"),
    "M04": ATCCategory("M04", "抗痛風劑", "Antigout preparations", "痛風"),
    "M05": ATCCategory("M05", "骨質疏鬆治療劑", "Drugs for bone diseases", "骨質疏鬆"),
    # N - 神經系統
    "N": ATCCategory("N", "神經系統", "Nervous system", "止痛、鎮靜、精神、神經"),
    "N01": ATCCategory("N01", "麻醉劑", "Anesthetics", "全身、局部麻醉"),
    "N02": ATCCategory("N02", "止痛劑", "Analgesics", "止痛、退燒"),
    "N03": ATCCategory("N03", "抗癲癇劑", "Antiepileptics", "癲癇"),
    "N04": ATCCategory("N04", "抗帕金森氏症藥物", "Anti-Parkinson drugs", "帕金森氏症"),
    "N05": ATCCategory("N05", "精神安定劑", "Psycholeptics", "鎮靜、抗精神病"),
    "N06": ATCCategory("N06", "精神興奮劑", "Psychoanaleptics", "抗憂鬱、ADHD"),
    "N07": ATCCategory("N07", "其他神經系統用藥", "Other nervous system drugs", "成癮、眩暈"),
    # P - 寄生蟲防治
    "P": ATCCategory(
        "P", "寄生蟲防治", "Antiparasitic products, insecticides and repellents", "寄生蟲、瘧疾"
    ),
    "P01": ATCCategory("P01", "抗原蟲劑", "Antiprotozoals", "瘧疾、阿米巴"),
    "P02": ATCCategory("P02", "抗蠕蟲劑", "Anthelmintics", "蟯蟲、絛蟲"),
    "P03": ATCCategory(
        "P03",
        "殺寄生蟲劑、殺蟲劑",
        "Ectoparasiticides, incl. scabicides, insecticides",
        "頭蝨、疥瘡",
    ),
    # R - 呼吸系統
    "R": ATCCategory("R", "呼吸系統", "Respiratory system", "感冒、氣喘、過敏"),
    "R01": ATCCategory("R01", "鼻部用藥", "Nasal preparations", "鼻炎、鼻塞"),
    "R02": ATCCategory("R02", "喉部用藥", "Throat preparations", "喉嚨痛、口腔潰癨"),
    "R03": ATCCategory(
        "R03", "呼吸道阻塞治療劑", "Drugs for obstructive airway diseases", "氣喘、慢性阻塞性肺病"
    ),
    "R05": ATCCategory("R05", "咳嗽及感冒製劑", "Cough and cold preparations", "咳嗽、祛痰"),
    "R06": ATCCategory(
        "R06", "全身性抗組織胺劑", "Antihistamines for systemic use", "過敏、流鼻水"
    ),
    "R07": ATCCategory("R07", "其他呼吸系統用藥", "Other respiratory system products", "呼吸用藥"),
    # S - 感覺器官
    "S": ATCCategory("S", "感覺器官", "Sensory organs", "眼科、耳鼻喉"),
    "S01": ATCCategory("S01", "眼科用藥", "Ophthalmologicals", "眼睛用藥"),
    "S02": ATCCategory("S02", "耳科用藥", "Otologicals", "耳朵用藥"),
    "S03": ATCCategory(
        "S03", "眼科及耳科製劑", "Ophthalmological and otological preparations", "沖洗液"
    ),
    # V - 其他
    "V": ATCCategory("V", "其他", "Various", "解毒、診斷、醫療器材"),
    "V01": ATCCategory("V01", "過敏原", "Allergens", "過敏原檢測"),
    "V03": ATCCategory("V03", "所有其他治療用藥", "All other therapeutic products", "解毒劑"),
    "V06": ATCCategory("V06", "一般營養品", "General nutrients", "配方營養品"),
    "V08": ATCCategory("V08", "顯影劑", "Contrast media", "X光、MRI顯影"),
    "V09": ATCCategory("V09", "放射性藥物（診斷）", "Diagnostic radiopharmaceuticals", "核醫檢查"),
    "V10": ATCCategory(
        "V10", "放射性藥物（治療）", "Therapeutic radiopharmaceuticals", "甲狀腺、癌症放射"
    ),
}

# ===== 常見醫療需求對應的 ATC 分類 =====

SYMPTOM_TO_ATC: Dict[str, List[str]] = {
    "頭痛": ["N02", "N02A", "N02C"],
    "發燒": ["N02", "N02B"],
    "咳嗽": ["R05", "R05D", "R05C"],
    "喉嚨痛": ["R02", "A01", "R06"],
    "鼻塞": ["R01", "R01A", "R01B"],
    "流鼻水": ["R06", "R06A"],
    "過敏": ["R06", "D04", "H02"],
    "腹痛": ["A03", "A01", "A02"],
    "腹瀉": ["A07", "A07A", "A07B"],
    "便秘": ["A06", "A06A"],
    "嘔吐": ["A04", "A04A"],
    "胃痛": ["A02", "A02A", "A02B"],
    "胃酸": ["A02", "A02A", "A02B", "A02C"],
    "氣喘": ["R03", "R03A", "R03B", "R03C"],
    "高血壓": ["C02", "C03", "C07", "C08", "C09"],
    "心絞痛": ["C01", "C07", "C08", "C09"],
    "膽固醇": ["C10", "C10A"],
    "糖尿病": ["A10", "A10A", "A10B"],
    "關節痛": ["M01", "M02", "M03"],
    "肌肉痛": ["M02", "M03", "N02"],
    "背痛": ["M03", "N02", "M01"],
    "經痛": ["N02", "G02", "H02"],
    "濕疹": ["D07", "D02", "D06"],
    "癬": ["D01", "D07"],
    "青春痘": ["D10", "D01"],
    "香港腳": ["D01", "D07"],
    "靜脈曲張": ["C05", "C04"],
    "痔瘡": ["C05", "D02"],
    "失眠": ["N05", "N06"],
    "焦慮": ["N05", "N06"],
    "憂鬱": ["N06", "N06A"],
    "癲癇": ["N03", "N03A"],
    "痛風": ["M04", "M04A"],
    "骨質疏鬆": ["M05", "H05"],
    "貧血": ["B03", "B03A"],
    "血栓": ["B01", "B01A"],
}


def get_atc_info(atc_code: str) -> Optional[ATCCategory]:
    """取得 ATC 分類資訊"""
    if atc_code in ATC_CLASSIFICATIONS:
        return ATC_CLASSIFICATIONS[atc_code]

    # 嘗試取得第一層級
    if len(atc_code) >= 1:
        first_level = atc_code[0]
        if first_level in ATC_CLASSIFICATIONS:
            return ATC_CLASSIFICATIONS[first_level]

    return None


def get_atc_by_symptom(symptom: str) -> List[str]:
    """根據症狀取得可能的 ATC 分類"""
    return SYMPTOM_TO_ATC.get(symptom, [])


def get_all_categories() -> List[ATCCategory]:
    """取得所有 ATC 分類"""
    return list(ATC_CLASSIFICATIONS.values())


def format_atc_tree() -> str:
    """格式化 ATC 分類樹"""
    output = []
    output.append("=" * 60)
    output.append("ATC 分類系統（解剖學治療學及化學分類系統）")
    output.append("=" * 60)

    for code, cat in sorted(ATC_CLASSIFICATIONS.items()):
        output.append(f"\n{cat.code} - {cat.name_cn}")
        output.append(f"    {cat.name_en}")
        output.append(f"    {cat.description}")

    return "\n".join(output)


def demo():
    """示範"""
    print("=" * 60)
    print("ATC 分類系統示範")
    print("=" * 60)

    # 查詢特定 ATC
    print("\n1. 查詢 ATC N02 (止痛劑):")
    atc = get_atc_info("N02")
    if atc:
        print(f"   {atc.code} - {atc.name_cn}")
        print(f"   {atc.name_en}")
        print(f"   {atc.description}")

    # 根據症狀查詢
    print("\n2. 根據症狀查詢可能的 ATC 分類:")
    for symptom in ["咳嗽", "頭痛", "過敏"]:
        atc_codes = get_atc_by_symptom(symptom)
        print(f"   {symptom}: {', '.join(atc_codes)}")

    # 列出所有分類
    print("\n3. 所有 ATC 第一層級分類:")
    for code, cat in sorted(ATC_CLASSIFICATIONS.items()):
        if len(code) == 1:
            print(f"   {code} - {cat.name_cn}")


if __name__ == "__main__":
    demo()
