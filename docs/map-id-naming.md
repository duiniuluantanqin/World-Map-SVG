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

批次 2 说明：TJ/KG/GQ/GM/GH/CG/CF 的本图单元数略少于 NE（如 TJ 4 vs 5），差值是 NE 多出的 X01~ 类单元或独立市（如 TJ-DU 杜尚别），不是年代差异；CD 的 11 个单元与 NE 的 2015 年前省制（Équateur、Bandundu、Orientale、Katanga）一致，与本图年代相符，故沿用。

## 跳过 / 待确认

| 文件 | 元素 | 情况 | 处理 |
| --- | --- | --- | --- |
| world-states-provinces.svg | `PL` `path11041` | 0.4×0.2px 的碎岛，质心不在任何 NE 面内，最近邻不唯一 | 待确认：按 `PL-PM-1` 兜底命名，或保持原样 |

## 已知问题（本次任务之外，待决定是否修）

1. **国家轮廓路径 id 不规范**：191 个国家组的轮廓路径 id 是 `<cc>` 小写，但另有 21 个不是。
   库依赖 `src/svg-world-map.js:256` 的 `child.id == country.id.toLowerCase()` 识别主路径，这 21 国目前是错位的。
   典型：`TW` 的 `TW-TAO` 实际是台湾整岛轮廓；`YE` 轮廓叫 `path2592`；`EH` 轮廓叫 `path12345`。
2. **命名体系与本图不一致的国家**（共 62 个）：如 IT（图上用大区名 `IT-lombardy`，NE 是省）、
   ES、FR、CN、AU、MY、PH、GB、UG、JP（NE 名称带长音符）等。这些需要逐国决定口径，未在本批处理。
3. **UN 数据同步**：`src/country-data.csv` 只有 6 列（code/name/longname/sovereignty/region/population），
   不含省份数据；省份只存在于 `src/country-data.json`，且目前只有 CA/CN/AU 三国。
   因此重命名魔数 id 暂时无需同步这两个文件；等到修改 CA/CN/AU 等国已有省份 id 时，必须同时改 `country-data.json` 的省份 key。
