#!/usr/bin/env python3
"""越南省份 ISO 3166-2 代码映射。

越南有 58 省 + 5 直辖市：
- 省份：VN-01 到 VN-73（数字码）
- 直辖市：VN-HN, VN-SG, VN-HP, VN-DN, VN-CT（字母码）

参考：https://en.wikipedia.org/wiki/ISO_3166-2:VN
"""

# 英文名 kebab -> 数字码映射
VN_CODE_MAP = {
    "lai-chau": "03",
    "dien-bien": "04",
    "son-la": "05",
    "yen-bai": "06",
    "tuyen-quang": "07",
    "ha-giang": "02",
    "cao-bang": "11",
    "bac-kan": "09",
    "thai-nguyen": "08",
    "lang-son": "12",
    "quang-ninh": "13",
    "bac-giang": "54",
    "bac-ninh": "56",
    "hai-duong": "61",
    "hung-yen": "66",
    "vinh-phuc": "70",
    "ha-nam": "63",
    "thai-binh": "62",
    "nam-dinh": "64",
    "ninh-binh": "65",
    "phu-tho": "68",
    "hoa-binh": "14",
    "ha-tinh": "23",
    "nghe-an": "22",
    "thanh-hoa": "21",
    "quang-tri": "25",
    "thua-thien-hue": "26",
    "quang-binh": "24",
    "quang-nam": "27",
    "da-nang": "DN",  # 直辖市，字母码
    "quang-ngai": "29",
    "binh-dinh": "31",
    "phu-yen": "32",
    "khanh-hoa": "34",
    "ninh-thuan": "36",
    "binh-thuan": "37",
    "kon-tum": "28",
    "gia-lai": "30",
    "dak-lak": "33",
    "dak-nong": "35",
    "lam-dong": "38",
    "binh-phuoc": "39",
    "binh-duong": "40",
    "dong-nai": "41",
    "ba-ria-vung-tau": "43",
    "tay-ninh": "42",
    "long-an": "46",
    "tien-giang": "47",
    "ben-tre": "50",
    "tra-vinh": "51",
    "vinh-long": "52",
    "dong-thap": "45",
    "an-giang": "44",
    "kien-giang": "48",
    "can-tho": "CT",  # 直辖市，字母码
    "hau-giang": "53",
    "soc-trang": "60",
    "bac-lieu": "67",
    "ca-mau": "59",
    "ho-chi-minh": "SG",  # 直辖市，字母码
    "ha-noi": "HN",  # 直辖市，字母码
    "hai-phong": "HP",  # 直辖市，字母码
}


def vn_code_to_id(code):
    """转换代码到标准 id"""
    if code in ("HN", "SG", "HP", "DN", "CT"):
        return f"VN-{code}"
    else:
        return f"VN-{code}"


def vn_name_to_code(name_kebab):
    """英文名 kebab 转数字码"""
    return VN_CODE_MAP.get(name_kebab)


def build_rename_map():
    """构建重命名映射"""
    import re
    import os
    
    # 读取 SVG
    svg_path = os.path.join(os.path.dirname(__file__), "..", "src", "world-states-provinces.svg")
    with open(svg_path, encoding="utf-8") as f:
        content = f.read()
    
    # 找出所有 VN-* id
    pattern = r'id="(VN-([a-z-]+))"'
    matches = re.findall(pattern, content)
    
    rename_map = {}
    for full_id, name_part in matches:
        # 跳过已经是字母码的直辖市
        if name_part in ("HN", "SG", "HP", "DN", "CT", "label"):
            continue
        # 跳过已经是数字码的
        if name_part.isdigit():
            continue
        # 跳过带后缀的（如 HN-1, SG-1）
        if "-" in name_part and name_part.split("-")[-1].isdigit():
            base = "-".join(name_part.split("-")[:-1])
            code = VN_CODE_MAP.get(base)
            if code:
                suffix = name_part.split("-")[-1]
                new_id = f"VN-{code}-{suffix}"
                rename_map[full_id] = new_id
            continue
        
        # 正常省份名
        code = VN_CODE_MAP.get(name_part)
        if code:
            new_id = f"VN-{code}"
            rename_map[full_id] = new_id
            print(f"{full_id} -> {new_id}")
        else:
            print(f"[skip] {full_id} (no code found)")
    
    return rename_map


if __name__ == "__main__":
    import sys
    import os
    
    if "--apply" in sys.argv:
        # 应用重命名
        svg_path = os.path.join(os.path.dirname(__file__), "..", "src", "world-states-provinces.svg")
        rename_map = build_rename_map()
        
        with open(svg_path, encoding="utf-8") as f:
            content = f.read()
        
        for old_id, new_id in rename_map.items():
            content = content.replace(f'id="{old_id}"', f'id="{new_id}"')
        
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        print(f"\n已更新 SVG 文件，共 {len(rename_map)} 处更改")
    else:
        build_rename_map()
