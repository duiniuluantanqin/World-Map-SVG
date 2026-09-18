# SVG 地图 ID 规范化记录

## 目标

把 `src/world-states-provinces.svg`（优先）与 `src/world-states.svg` 中形如 `pathNNNN` / `gNNNN` / `circleNNNN` 的魔数 id
补全为可读、可与数据对接的规范 id。按批次提交，每批可独立回退。

## 命名规范

沿用图上已有的 482 个已命名元素的规则，来源为 ISO 3166-2 / Natural Earth 一级行政区编码：

| 情况 | 规则 | 例子 |
| --- | --- | --- |
| ISO 3166-2 后缀是字母 | `<CC>-<后缀>` | `US-WA`、`PL-PK`、`SE-AB`、`ID-BA`、`CM-LT` |
| ISO 3166-2 后缀是数字 | `<CC>-<英文名 kebab-case>` | `AT-carinthia`、`BG-lovech`、`AL-tirana`、`EE-tartu` |
| 同一行政区在本图被拆成多块 | `<基础id>-<序号>`，必要时语义后缀 | `ID-BA-mainland`、`AT-vorarlberg-0` |
| 生成的 id 与已有 id 重名 | `<基础id>-<ISO后缀小写>` | `BG-sofia-23` |
| 国家轮廓主路径 | `<cc>` 小写 | `us`、`se`、`pl` |

- id 一律 ASCII；变音符号做转写（`EE-põlva` → `EE-polva`、`AL-vlorë` → `AL-vlore`）。
- 只修改元素的 `id` 属性，不改几何、结构、顺序。

## 方法

1. 本图是 Robinson 投影（宽高比 1.9716），中央经线相对 0° 偏移 +10.03°。用已命名元素反算验证：中位误差 0.54px，无系统性偏差。
   因此每个 path 的质心都能换算成经纬度。
2. 参考数据：Natural Earth 10m admin-1（公有领域，4596 个单元，100% 带 `iso_3166_2`）。
   位置：`D:\work\other\svg-naming\data\ne_10m_admin_1_states_provinces.geojson`
3. 匹配顺序：质心经纬度落点（点在面内）→ IoU（≥0.55 且与次优差 ≥0.12）→ 最近邻兜底；三者都不满足则跳过。
4. 工具：`D:\work\other\svg-naming\tools\`（`svgname.py` 投影/解析/索引，`batch_naming.py` 批量提议/改写/安全门，`apply_batch.py` 第一批脚本，`report_countries.py` 逐国可行性报告）。
   产出物：`D:\work\other\svg-naming\out\`。
5. 每批校验：`git diff` 逐行比对（除 id 外必须完全一致）、XML 可解析、id 全局唯一、新增 id 全 ASCII。

## 批次记录

| 批次 | 范围 | 结果 | 跳过 |
| --- | --- | --- | --- |
| 1 | SE, PL, BG, CM, EE, AL | 98 个 id：SE 19、PL 14、BG 28、CM 10、EE 15、AL 12 | PL `path11041` |
| 2 | ZW, ZM, TJ, TG, SZ, SS, RW, NA, LS, LR, KM, KG, GY, GQ, GM, GH, GA, CR, CI, CG, CD, CF, TD, SN, TM | 239 个 id：ZW 10、ZM 10、TJ 4、TG 5、SZ 4、SS 10、RW 5、NA 13、LS 10、LR 15、KM 3、KG 7、GY 10、GQ 6、GM 5、GH 9、GA 9、CR 7、CI 19、CG 10、CD 11、CF 16、TD 22、SN 14、TM 5 | 无 |
| 3 | BN, BZ, DJ, ER, IL, BY, QA, IS, NE, PK, ML, BO, LT, OM, AM, BJ, ET, KP, JO, NL, HT, MZ | 196 个 id：BN 5、BZ 6、DJ 6、ER 6、IL 6、BY 7、QA 7、IS 8、NE 8、PK 7、ML 9、BO 10、LT 10、OM 10、AM 11、BJ 11、ET 11、KP 11、JO 12、NL 11、HT 13、MZ 12 | PK `path10354`、MZ `path3384`；另 `path10369` 命名后回滚 |

批次 2 说明：TJ/KG/GQ/GM/GH/CG/CF 的本图单元数略少于 NE（如 TJ 4 vs 5），差值是 NE 多出的 X01~ 类单元或独立市（如 TJ-DU 杜尚别），不是年代差异；CD 的 11 个单元与 NE 的 2015 年前省制（Équateur、Bandundu、Orientale、Katanga）一致，与本图年代相符，故沿用。

批次 3 说明：先用质心法出提议，再用「面积比 + 质心距离」二次校验，修正 4 处误判（`IL-TA`→`IL-M`、`IL-TA-1`→`IL-TA`、`ML-koulikoro-1`→`ML-BKO`、`ET-OR-1`→`ET-HA`），并回滚 1 处无法确认的命名（`PK-PB-1`→`path10369`）。本图会把小行政区放大绘制（Harari 2.8 倍、Bamako 10 倍），质心容易被相邻大区吸入，面积+距离双指标更可靠。

## 批次 1-3 复核修正

对批次 1-3 的全部单元做了「面积比 + 质心距离」最优匹配复核（面积取球面面积，质心与 NE label point 距离），
确认并修正 5 处（其余候选为贪婪匹配假阳性，已逐条核对后维持原名）：

| 文件 | 原 id | 改为 | 依据 |
| --- | --- | --- | --- |
| world-states-provinces.svg | `BG-sofia` | `BG-sofia-22` | 该单元 1827 km²、位于索菲亚市，对应 ISO `BG-22`（索菲亚市）；`BG-sofia-23`（7981 km²）对应 `BG-23`（索菲亚州），两者补齐 ISO 后缀更清晰 |
| world-states-provinces.svg | `TD-CB-1` | `TD-ND` | 677 km²，距 NE `TD-ND`（恩贾梅纳）质心 12 km，且 `TD-ND` 是唯一未被占用的 NE 要素（与 `ML-BKO` 同类：被包围的首都区） |
| world-states-provinces.svg | `SN-KL` | `SN-FK` | 该单元 7338 km²，与 NE `SN-FK`（法蒂克，8098）面积比 0.91、质心 39 km；与 `SN-KL`（考拉克，5332）比 1.38 |
| world-states-provinces.svg | `SN-KL-1` | `SN-KL` | 该单元 5197 km²，与 NE `SN-KL`（考拉克，5332）面积比 0.97、质心 12 km |
| world-states-provinces.svg | `OM-SS` | `OM-SH` | 本图阿曼是 2011 年前版本（单一「Ash Sharqiyah」39478 km² ≈ 实际 36800），`OM-SH` 正是该旧区 ISO 码；NE 的 `OM-SS`（16384）只是北部 |

说明：`HT-*-1`/`MZ-*-1`/`OM-MU-1`/`BN-TE-1` 等为岛屿或重复多边形，`LS-B/D`、`LR-gbarpolu/LR-BG`、`QA-DA/US`、`JO-BA/MD`、`HT-GA/NI`、`ET-DD/HA`、`GQ`、`NL` 等候选交换经核对后维持原名（质心距离 2-17 km 明显优于备选 27-85 km）。

## 跳过 / 待确认

| 文件 | 元素 | 情况 | 处理 |
| --- | --- | --- | --- |
| world-states-provinces.svg | `PL` `path11041` | 0.4×0.2px 的碎岛，质心不在任何 NE 面内，最近邻不唯一 | 待确认：按 `PL-PM-1` 兜底命名，或保持原样 |
| world-states-provinces.svg | `PK` `path10354` | 30960 km²，克什米尔形状；NE `PK-JK`（Azad Kashmir，13044 km²）质心相距 47 km、面积比 2.35，其余 NE 要素已被占用 | **争议地区，待你确认**：建议 `PK-JK`（按图归入 PK 组） |
| world-states-provinces.svg | `PK` `path10369` | 5096 km²，跨 KP/旁遮普边界（占旁遮普 60%、KP 48%），与 NE 伊斯兰堡 `PK-IS`（1079 km²）零重叠；NE 的 `PK-IS` 在本图无对应单元 | 无法确认归属，保持 `path10369` |
| world-states-provinces.svg | `MZ` `path3384` | 0.04 px² 沿海碎块，与所有 NE 候选 IoU 均为 0 | 保持 `path3384` |
| world-states-provinces.svg | `OM` `path4786` | 307538 km² ≈ 全国面积，是 `<g id="om">` 内嵌的轮廓副本，非行政单元 | 暂不命名（轮廓类） |
| world-states-provinces.svg | `IS` `IS-reykjavik` | 1298 km²，实为 NE `IS-1`（Capital，832）+`IS-0`（Reykjavík，504）合并（合计 1336，比 0.97） | 暂用 `IS-reykjavik`；如需按 IS-1 命名请告知 |

## 已知问题（本次任务之外，待决定是否修）

1. **国家轮廓路径 id 不规范**：191 个国家组的轮廓路径 id 是 `<cc>` 小写，但另有 21 个不是。
   库依赖 `src/svg-world-map.js:256` 的 `child.id == country.id.toLowerCase()` 识别主路径，这 21 国目前是错位的。
   典型：`TW` 的 `TW-TAO` 实际是台湾整岛轮廓；`YE` 轮廓叫 `path2592`；`EH` 轮廓叫 `path12345`。
2. **命名体系与本图不一致的国家**（共 62 个）：如 IT（图上用大区名 `IT-lombardy`，NE 是省）、
   ES、FR、CN、AU、MY、PH、GB、UG、JP（NE 名称带长音符）等。这些需要逐国决定口径，未在本批处理。
3. **NE 非标准 ISO 码（`X01~`/`X1~`/`X2~`）**：这些单元 NE 没有标准 ISO 码，本方案按规则退化为英文名 kebab。已遇到的建议改用真实 ISO 码，待确认：
   - `TJ` NE `TJ-X01~` = Districts of Republican Subordination → `TJ-RA`（现名 `TJ-districts-of-republican-subordination`）
   - `LR` NE `LR-X1~` = Gbarpolu → `LR-GP`（现名 `LR-gbarpolu`）；NE `LR-X2~` = River Gee → `LR-RG`（现名 `LR-river-gee`）
   - `TD` NE `TD-X01~` = Ennedi → `TD-EN`（2012 年前旧区，已拆分；现名 `TD-ennedi`）
4. **UN 数据同步**：`src/country-data.csv` 只有 6 列（code/name/longname/sovereignty/region/population），
   不含省份数据；省份只存在于 `src/country-data.json`，且目前只有 CA/CN/AU 三国。
   因此重命名魔数 id 暂时无需同步这两个文件；等到修改 CA/CN/AU 等国已有省份 id 时，必须同时改 `country-data.json` 的省份 key。
