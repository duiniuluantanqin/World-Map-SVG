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

- id 一律 ASCII；变音符号做转写（`EE-põlva` → `EE-polva`、`AL-vlorë` → `AL-vlore`、`TR-agrı` → `TR-agri`）。
  注意土耳其无点 i（`ı`，U+0131）不会被 NFKD 分解，需显式转写成 `i`（批次 12 已修 `batchfast.py` 的 `deacc`）。
- 只修改元素的 `id` 属性，不改几何、结构、顺序。

## 方法

1. 本图是 Robinson 投影（宽高比 1.9716），中央经线相对 0° 偏移 +10.03°。用已命名元素反算验证：中位误差 0.54px，无系统性偏差。
   因此每个 path 的质心都能换算成经纬度。
2. 参考数据：Natural Earth 10m admin-1（公有领域，4596 个单元，100% 带 `iso_3166_2`）。
   位置：`D:\work\other\svg-naming\data\ne_10m_admin_1_states_provinces.geojson`
3. 匹配顺序：质心经纬度落点（点在面内）→ IoU（≥0.55 且与次优差 ≥0.12）→ 最近邻兜底；三者都不满足则跳过。
4. 工具：`D:\work\other\svg-naming\tools\`（`svgname.py` 投影/解析/索引，`batch_naming.py`/`batch_naming3.py` 批量提议（后者为质心优先+面积+距离匹配），`apply_batch.py` 第一批脚本，`report_countries.py` 逐国可行性报告）。
   产出物：`D:\work\other\svg-naming\out\`。
5. 每批校验：`git diff` 逐行比对（除 id 外必须完全一致）、XML 可解析、id 全局唯一、新增 id 全 ASCII。

## 批次记录

| 批次 | 范围 | 结果 | 跳过 |
| --- | --- | --- | --- |
| 1 | SE, PL, BG, CM, EE, AL | 98 个 id：SE 19、PL 14、BG 28、CM 10、EE 15、AL 12 | PL `path11041` |
| 2 | ZW, ZM, TJ, TG, SZ, SS, RW, NA, LS, LR, KM, KG, GY, GQ, GM, GH, GA, CR, CI, CG, CD, CF, TD, SN, TM | 239 个 id：ZW 10、ZM 10、TJ 4、TG 5、SZ 4、SS 10、RW 5、NA 13、LS 10、LR 15、KM 3、KG 7、GY 10、GQ 6、GM 5、GH 9、GA 9、CR 7、CI 19、CG 10、CD 11、CF 16、TD 22、SN 14、TM 5 | 无 |
| 3 | BN, BZ, DJ, ER, IL, BY, QA, IS, NE, PK, ML, BO, LT, OM, AM, BJ, ET, KP, JO, NL, HT, MZ | 196 个 id：BN 5、BZ 6、DJ 6、ER 6、IL 6、BY 7、QA 7、IS 8、NE 8、PK 7、ML 9、BO 10、LT 10、OM 10、AM 11、BJ 11、ET 11、KP 11、JO 12、NL 11、HT 13、MZ 12 | PK `path10354`、MZ `path3384`；另 `path10369` 命名后回滚 |
| 4 | JM, MR, PA, SV, SY, TL, UZ, CL, BI, LA, PY | 162 个 id：JM 14、MR 13、PA 12、SV 14、SY 14、TL 14、UZ 14、CL 16、BI 17、LA 17、PY 17 | MR `path3878`、PA `path7512`/`path4792`、UZ `path9423` |
| 5 | FI, IQ, UY, HN, NI, AO, SD, GE, SO | 158 个 id：FI 17、IQ 18、UY 19、HN 19、NI 17、AO 19、SD 18、GE 13、SO 18 | FI `FI-uusimaa`（已是规范名，非魔数）、NI `path6697`（湖泊）、GE 6 条嵌套多边形 |
| 6 | GT, LY, CH, PT, NO, YE | 134 个 id：GT 22、LY 22、CH 23、PT 26、NO 19、YE 22 | 无 |
| 7 | DZ, AF, BR, CO, UA, EC, NG | 212 个 id：DZ 48、AF 34、BR 26、CO 32、UA 26、EC 33、NG 13 | CO `path30715`；NG 24 条超大异常多边形（见下） |
| 8 | TN, EG, PE, SA, LB, MN | 114 个 id：TN 23、EG 26、PE 24、SA 13、LB 6、MN 22 | TN `path9180`/`path8175`/`path9012`、EG `path10625`、PE `path23983`、SA `path3234`/`path5488`/`path5482`/`path5480`、MN `path6312`/`path6373` |
| 9 | RO, VE, MD, IR, DO | 156 个 id：RO 41、VE 24、MD 33、IR 27、DO 31 | VE 13 条三角洲碎块、MD 3 条（含德左）、IR 7 条、DO 3 条 |
| 10 | IE, TZ, CU, NZ, RS | 99 个 id：IE 20、TZ 24、CU 15、NZ 15、RS 25 | IE 8、TZ 2、CU 8、NZ 7、RS 5（共 30 条追记于跳过表） |
| 11 | US, RU | 124 个 id：US 43、RU 81 | US 18（重名拆分 8 + 岛屿 10）、RU 5（新地岛、印古什/阿迪格、莫斯科/圣彼得堡已命名） |
| 12 | TR | 81 个 id：TR 81 | TR `path3456`（东色雷斯聚合单元） |
| 13 | TH | 75 个 id：TH 75 | TH 8 条离岛碎块（苏梅/帕岸/象岛/达鲁岛等） |

批次 13 说明：泰国（TH）为数字码国家（ISO 3166-2:TH 用 TH-10…TH-96），id 全部退化为英文名 kebab-case，不做 ip-api 反向校验（同批次 12）。75 条命名（72 自动 + 3 复核采纳）。修正 `deacc` 后本批无非 ASCII id。3 条 flag 复核：`path73039`（IoU 0.67、面积比 1.02）＝夜丰颂 Mae Hong Son → `TH-mae-hong-son`；`path75660`（面积比 1.11、质心距 NE 标签 11 km）＝沙没巴干 Samut Prakan → `TH-samut-prakan`；`path74354`（面积比 0.87、质心距 12 km）＝信武里 Sing Buri → `TH-sing-buri`。三者质心落点判 False 均系微省尺度下 Robinson 投影 ±10 km 边界误差，以 IoU/质心距离/面积比一致定案。`TH-bangkok`（曼谷）已是规范 id，未动。8 条离岛（苏梅、帕岸、象岛、达鲁岛等，49–213 km²）无 NE admin-1 对应，保持魔数。

批次 12 说明：土耳其（TR）为数字码国家（ISO 3166-2:TR 用 TR-01…TR-81），id 全部退化为英文名 kebab-case；因 ip-api `region` 不返回英文名，不做 ip-api 反向校验，以 NE 几何 IoU + 质心落点 + 面积比为准（同批次 8 的数字码国家）。81 条全部命名（IoU 0.57–0.99、面积比 0.80–1.23）。唯一入 flag 的 `path8635`（IoU 0.83、面积比 1.05、质心距 NE 标签 33 km）＝安塔利亚（Antalya）→ `TR-antalya`（质心落点判 False 系沿海多边形质心微落近岸缺口，IoU/面积比足以定案）。`path3456`（23949 km²）＝土耳其欧洲部分（东色雷斯）整体单元，横跨 Edirne/Kırklareli/Tekirdağ/İstanbul 等省（这些省图中已单独绘制并命名），无单一 NE admin-1 对应 → 保持魔数。

批次 11 说明：美国（US）与俄罗斯（RU）字母码；US 里 8 条「重名」是已命名州（如 US-TX/US-MA）的 island/mainland 拆分块，需按拆分规则补后缀（后续单独处理），另有 10 条离岛；RU 的哈巴罗夫斯克/堪察加（IoU 0.86/0.84，质心 d300 因边疆区狭长）已采纳，新地岛（path6451）、印古什/阿迪格（IoU≤0.26）、莫斯科/圣彼得堡（已是规范名）跳过。US/RU 经 ip-api 正向校验命中 120/132（**90.9%**，这两个大国 IP 归属精度高，明显优于小国）。

批次 10 说明：爱尔兰（IE）的图单元与 NE 郡边界几何差异较大，仅 20 个质心落点干净的命名可用，其余 8 条（含都柏林/科克/戈尔韦等市郡混排、IoU 0.03–0.41）跳过；新西兰（NZ）、古巴（CU）的离岛、塞尔维亚（RS）的科索沃地区（42.xN/20.xE）多为无 NE 对应或争议，保持魔数。字母码国家（IE/CU/NZ/RS）经 ip-api 正向校验命中 13/34（38%，这些国家 IP 归属精度差、离岛多）；TZ 数字码转英文名不适用。

批次 9 说明：字母码国家（RO/VE/MD）经 ip-api 正向校验命中 55/98（56%），未命中集中在「小国/小州 IP 归属不精确」——尤其摩尔多瓦（MD）各 rayon 极小、maxmind 无独立 IP 段或 ip-api 把 IP 归到相邻 rayon；委内瑞拉（VE）与罗马尼亚（RO）未命中多为「候选 IP 被 ip-api 归到相邻省」。ip-api「缺口」里 `MD-SN`（德左，争议地区）、`RO-B`（布加勒斯特，图上并入 Ilfov）、`VE-X`（加拉加斯，ip-api/FIPS 用 `VE-X`，本图用 ISO `VE-A`）均为图上未单独绘制单元或编码差异，非命名错误。数字后缀转英文名的 IR/DO 不适用 ip-api 反向验证（同批次 8）。

批次 8 说明：本批起在几何命名之外，新增「ip-api 真实 IP 反查」正向校验（脚本 `tests/ip_naming_test.py`）：把每个地区的候选 IP 交给 ip-api 反查，拼 `CountryCode-Region` 与 SVG 已命名 id 比对，以 ip-api 为准、不预设省份归属。字母后缀国家（EG/PE/LB）可实测（命中 29/56，未命中多为「候选 IP 被 ip-api 归到相邻/总部省份」或「沙漠区无独立 IP 如 EG-WAD」）；数字后缀转英文名的国家（TN/SA/MN）因 ip-api `region` 不返回英文名而不适用该测试，其命名仍以 NE 几何 IoU + 面积比为准。测试报告 3 个「ip-api 能拼出但 SVG 缺」的缺口，其中 EG-LX（卢克索）、PE-CAL（卡亚俄）经质心核验属「图上未单独绘制该行政区」，PE-LMA 是 ip-api 用 FIPS 码 vs ISO 的 `PE-LIM`，均非命名错误。本批跳过项补充：

批次 2 说明：TJ/KG/GQ/GM/GH/CG/CF 的本图单元数略少于 NE（如 TJ 4 vs 5），差值是 NE 多出的 X01~ 类单元或独立市（如 TJ-DU 杜尚别），不是年代差异；CD 的 11 个单元与 NE 的 2015 年前省制（Équateur、Bandundu、Orientale、Katanga）一致，与本图年代相符，故沿用。

批次 3 说明：先用质心法出提议，再用「面积比 + 质心距离」二次校验，修正 4 处误判（`IL-TA`→`IL-M`、`IL-TA-1`→`IL-TA`、`ML-koulikoro-1`→`ML-BKO`、`ET-OR-1`→`ET-HA`），并回滚 1 处无法确认的命名（`PK-PB-1`→`path10369`）。本图会把小行政区放大绘制（Harari 2.8 倍、Bamako 10 倍），质心容易被相邻大区吸入，面积+距离双指标更可靠。

批次 4 说明：改用「质心是否落在 NE 面内」优先、再按标签点距离与面积比的匹配（工具 `batch_naming3.py`），本批 40 个需要人工判断的单元里绝大多数为「同区域相邻小单元面积相近」造成的歧义，均按质心落点定案。逐国特殊情况：
- `SY` `path12136`（2733 km²）＝库奈特拉省（`SY-QU`）。图上是整个库奈特拉省含戈兰高地；NE 的 `SY-QU` 仅 512 km²（叙利亚实际控制部分），故面积比 5.34。按中国口径（戈兰为叙利亚被占领土）沿用图的归属 ✔
- `CL` 为 2018 年前版本：`path19988`（37417 km²）＝旧比奥比奥 `CL-BI`（非 Ñuble，NE `CL-NB` 未使用）；`path6472`（27844 km²）＝麦哲伦大区的火地岛部分 → `CL-MA-1`
- `LA`：`path80641`（4095 km²，万象）＝万象直辖市；NE 缺 `LA-VT`，按 ISO 3166-2 补
- `PY`：图无亚松森单元（NE `PY-ASU` 未使用），首都并入 `PY-central`
- `UZ`：图无塔什干市单元（NE `UZ-TK` 未使用）；`path9394`＝`UZ-SI`（锡尔河州，面积比 1.00）、`path9396`（41 km² 碎块）＝`UZ-SI-1`；`path9423` 无归属，跳过
- `TL`：`path27342` 与 `path2788` 几何完全相同（欧库西重复），命名 `TL-OE-1`
- `PA`：图 14 单元 / NE 12。`path7512`（3130 km²，紧邻巴拿马城）疑为 2014 年新设的 Panamá Oeste（NE 未收录）；`path4792`（68 km²）为奇里基湾科伊瓦岛。两者均保持魔数待确认

批次 5 说明：本批新增两种校验手段——「lat/lon bbox 与 NE 要素 bbox 对照 + 顶点落入率」、按国渲染 PNG 逐块核对（工具 `%TEMP%\inspect_country.py`、`%TEMP%\render_country.py`）。9 国中有 5 国与 NE 数据不一致：
- `FI`：图 18 单元 / NE 18。NE 这一版把奥兰群岛归到别的 adm0，`path14878`（729 km²，60.05–60.42N / 19.65–20.24E＝奥兰主岛）无候选 → 按 ISO 3166-2:FI 命名 `FI-aland`（已核对 Wikipedia：现行码 FI-01…FI-19）。`path14553`（19180 km²，61.99–64.11N）＝南博滕+中博滕合并（NE FI-03 14574 + FI-07 5702），按主体命名 `FI-southern-ostrobothnia`，NE `FI-07` 因此未用。`FI-uusimaa` 已是规范 id，未动。
- `IQ`、`UY`：18/18、19/19 全部干净匹配（面积比 0.87–1.22），无需人工干预。
- `HN`：图 19 单元 / NE 18。`path7593` 与 `path6082` 几何完全相同（181 km²，16.39N/86.52W＝罗阿坦岛），属重复绘制 → `HN-IB` / `HN-IB-1`（NE `HN-IB` 含全部海湾群岛 439 km²，图上只画了主岛）。
- `NI`：17 个省级单元全部匹配；第 18 条 `path6697`（1306 km²，12.16–12.52N / 86.63–86.14W）＝马那瓜湖，是水体不是行政区 → 跳过。旁证：图上 Granada、Rivas 面积只有 NE 的 0.41 倍，正因 NE 的省域包含湖面。
- `AO`：19 条 path 中 18 条是省。`<g id="ao">` 轮廓组里有两条：`path3888`＝真正国界、`path3890`＝卡宾达游离副本（与 `path9185` 几何完全相同）→ 后者命名 `AO-CAB-1`。
- `SD`：图＝2013 年后 18 州制，NE 有 3 处出入：`SD-DS` 被用了两次（南达尔富尔被后一条东达尔富尔覆盖）、中达尔富尔被标成 `SD-DE`、缺西科尔多凡。按 Wikipedia ISO 3166-2:SD 改用真实码：`path9009`→`SD-DC`、`path9007`→`SD-DE`、`path8995`→`SD-DS`、`path8984`→`SD-GK`。面积佐证：西科尔多凡 111575（实际 111373）、北科尔多凡 185254（185302）、南科尔多凡 79499（79470）。
- `GE`：图 19 单元 / NE 12。阿布哈兹一带叠了 8 条 path：`path36614` 与 `path15677` 几何完全相同（9621 km²，NE `GE-AB` 9279）→ `GE-AB` / `GE-AB-1`；其余 6 条（8799、8397、6784、4789、3316、1940 km²）是自西北角 39.99E/43.60N 向东南递增的嵌套多边形，互相遮挡、不构成独立行政单元 → 全部跳过。`GE-SK` 在图上与 NE 都含南奥塞梯，符合中国口径 ✔
- `SO`：图 18 单元＝索马里 18 州。NE 把索马里兰并成单个要素（`-99-X11~`，adm0=-1），5 个州没有候选，按位置配 ISO 3166-2:SO（已核对 Wikipedia）：`path7912`→`SO-AW`、`path8985`→`SO-WO`、`path8968`→`SO-TO`、`path8987`→`SO-SO`、`path8953`→`SO-SA`。中国口径下索马里兰属索马里，这 5 条本来就在 `<g id="SO">` 组内 ✔

批次 6 说明：
- `GT`、`LY`、`CH`：与 NE 一一对应，面积比 0.78–1.27，直接采用（`CH` 的 BE/VD/GE 三条本来就是规范名，未动）。
- `PT`：18 个本土区全部匹配；NE 的 `PT-20`「Azores」是整体一个要素，图上按岛拆成 6 条 → 按拆分规则处理：最大岛圣米格尔＝`PT-azores`，其余按面积递减 `PT-azores-1…5`（皮库、特塞拉、圣若热、法亚尔、圣玛丽亚）；马德拉岛（path3628）＝`PT-madeira`；`path8376`（17 km²，38.69N / 9.21W，特茹河口小岛）＝里斯本区碎块 → `PT-lisbon-1`。
- `NO`：20 个郡（`NO-hordaland`、`NO-oslo` 已是规范名）+ 斯瓦尔巴（`NO-svalbard`）+ 扬马延 `path10963`（456 km²，70.85–71.21N / 8.07–9.10W，NE 未收录）→ `NO-jan-mayen`。NE 的 `NO-X01~`（布韦岛）图上没有对应单元。
- `YE`：19 个省 + 亚丁 `path13650`（面积比 1.83，图上把亚丁省画大了）+ 2 个岛屿碎块：`path2190`（154 km²，14.0N/42.75E＝祖卡尔岛，哈尼什群岛，属荷台达省）→ `YE-HU-1`；`path2192`（116 km²，12.2N/52.26E＝阿卜杜勒库里岛，属哈德拉毛）→ `YE-HD-1`。NE 的 `YE-SA`（萨那市）在图上并入 `YE-SN`，未用。`path2592` 是国界轮廓（见文末第 1 条）。

批次 7 说明：本批先修掉一个校验工具缺陷，再处理 3 处 NE 数据错误与 3 类几何异常。
- 工具缺陷：`batchfast.py` 的 IoU 只在两要素 bbox 的**交集**范围内统计，当一方 bbox 完整套住另一方时会严重虚高（NG 里 45 万 km² 的异常块对 1 万 km² 的州也能算出 0.7）。本批改为**并集**范围统计（`%TEMP%\ious.py`，用 PIL 逻辑运算，等价于真值），所有结论均以精确 IoU 复核。
- `AF`（34 省全解）：NE 只有 32 个唯一码，`AF-PAR` 与 `AF-URU` 各重码一次，恰好对应 2004 年新设的 Panjshir、Daykundi。精确 IoU 定案：`path10523`（3305 km²，35.42N/69.70E）对 NE 第一条 `AF-PAR` I0.56 → `AF-PAN`（Panjshir）；`path10548`（18391 km²，33.75N/66.14E）对 NE 第二条 `AF-URU` I0.68 → `AF-DAY`（Daykundi）；`path10472`（11645 km²，32.87N/66.02E）对 NE 第一条 `AF-URU` I0.65 → `AF-URU`（Urozgan，此前被跳过，本批解决）。另 NE 把 Paktia/Paktika 的码写反（NE 的 `AF-PIA` 名叫 Paktika、`AF-PKA` 名叫 Paktia），按官方码改正：`path10573`→`AF-PIA`（Paktia）、`path10533`→`AF-PKA`（Paktika）。`AF-DAY`/`AF-PAN` 已核对 Wikipedia ISO 3166-2:AF 为现行码。
- `CO`：图 33 单元 / NE 34 条（33 唯一码），NE 用 `CO-CUN` 同时表示波哥大与昆迪纳马卡。按官方码 `CO-DC` 命名波哥大 `path30723`（2699 km²，4.22N/74.30W；对 NE 那条「Bogotá」I0.36，对昆迪纳马卡 I0.07，已核对 Wikipedia）。`path30715`（88 km²，1.27N/66.92W）与全部 NE 要素精确 IoU=0，跳过。NE 的 `CO-SAP`/`CO-X01~`（圣安德烈斯）图上无对应单元。
- `UA`：26 单元。24 条与 NE 一一对应（I0.85–0.92）。敖德萨州在图上被拆成两块：`path37177`（19117 km²，北部含敖德萨市）→`UA-odessa-1`、`path37156`（13332 km²，南部布贾克）→`UA-odessa-2`（对 `UA-51` 的 I 为 0.54/0.35，合计 32449 km² ≈ 州面积 35207 的 92%）。基辅州与基辅市同名 → 按重名规则加 ISO 后缀：`path37236`→`UA-kyiv-32`（州）、`path37245`→`UA-kyiv-30`（市，图上放大 15.6 倍）。Luhansk（卢甘斯克）、Donetsk（顿涅茨克）**按中国口径**命名为乌克兰的州（`UA-09`/`UA-14`）。
- `EC`：33 单元。23 个本土省与 NE 一一对应（I0.58–0.87、面积比 0.86–1.13）。加拉帕戈斯被画了两层：`path31054` 一条 path 内含 7 个子路径＝整个群岛，另有 7 条单岛 path 叠在其上 → `EC-W` + `EC-W-1…7`（按面积递减：伊莎贝拉 4525、圣克鲁斯 808、圣克里斯托瓦尔 468、费尔南迪纳 435、圣地亚哥 417、弗洛雷娜 114、马切纳 68 km²）。瓜亚斯湾另有 2 岛：`path6602`（普纳岛 760 km²）→`EC-G-1`、`path4798`（河口小岛 70 km²）→`EC-G-2`。
- `NG`：图 38 单元 / NE 37 州+FCT。北部 13 州干净匹配（I0.70–0.90、面积比 0.84–1.15）已命名；其余 24 条是 4.7 万–45.1 万 km² 的超大异常多边形（`path5382-1` 45.1 万 km² ≈ 全国一半），彼此重叠并覆盖南部各州，与任何 NE 州的精确 IoU 仅 0.05–0.47，也不是任何州的缩放/平移副本（bbox 归一化相似度 0.35–0.59）→ 全部跳过待确认，见「跳过/待确认」表。
- `DZ`、`BR`：与 NE 一一对应（I0.67–0.96、面积比 0.87–1.23）。`DZ-algiers`（1310 km²）是阿尔及尔省被放大 4.4 倍绘制（图上小省普遍放大），48 个 NE 码用尽后唯一剩余且落点在省界内。BR 跳过 2 条圣卡塔琳娜海岸碎块。

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
| world-states-provinces.svg | `MR` `path3878` | 264 km²，努瓦克肖特以北沿海（19.75N,16.42W），NE 13 个要素均已占用 | 保持 `path3878`（疑为海岸/岛屿碎块） |
| world-states-provinces.svg | `PA` `path7512` | 3130 km²，紧邻巴拿马城；疑为 2014 年设立的 Panamá Oeste，NE 未收录 | **待你确认**：建议 `PA-panama-oeste`（或 ISO `PA-10`） |
| world-states-provinces.svg | `PA` `path4792` | 68 km² 海岛（8.26N,82.41W，奇里基湾科伊瓦岛） | **待你确认**：归入 `PA-chiriqui` 的碎块 `PA-chiriqui-1`，或保持原样 |
| world-states-provinces.svg | `UZ` `path9423` | 8502 km²（40.93N,62.42E，布哈拉以北），NE 无对应要素，且 14 个要素已全部占用 | 保持 `path9423`（疑为图上多余/重叠多边形） |
| world-states-provinces.svg | `SY` `SY-QU` | 已命名，含戈兰高地（争议地区） | 按中国口径（戈兰为叙利亚被占领土）沿用图上归属；如需加注请告知 |
| world-states-provinces.svg | `NI` `path6697` | 1306 km²，12.16–12.52N / 86.63–86.14W，形状与马那瓜湖一致；与所有省级候选 IoU ≤ 0.16 | 非行政区（湖泊），暂不命名；若要命名可加 `NI-lake-managua` |
| world-states-provinces.svg | `GE` `path15679` `path15675` `path15673` `path15671` `path15669` `path15667` | 8799/8397/6784/4789/3316/1940 km²，6 条自西北角向东南递增的嵌套多边形，被 `GE-AB` 完全遮挡 | 跳过（疑为原作者图层缺陷，建议后续删除） |
| world-states-provinces.svg | `TL` `path27340` | 覆盖全境（124.97–127.28E / 8.32–9.38S）＝东帝汶国界轮廓，但在 `<g id="tl">` 内、id 不是 `tl` | 暂不改（属文末第 1 条轮廓 id 问题） |
| world-states-provinces.svg | `AO` `path3888` | 安哥拉国界轮廓（在 `<g id="ao">` 内、与 `path3890` 同组），id 不是 `ao` | 暂不改（同上） |
| world-states-provinces.svg | `CO` `path30715` | 88 km²（1.27N, 66.92W），瓜伊尼亚/内格罗河边界小岛，与 NE 全部 34 条要素精确 IoU = 0 | 保持 `path30715` |
| world-states-provinces.svg | `NG` 24 条：`path28144` `path28146` `path28148` `path8877` `path8880` `path8883` `path8885` `path8888` `path8894` `path8909` `path8912` `path8914` `path8916` `path8918` `path9073` `path9086` `path9088` `path9096` `path9103` `path9111` `path9145` `path9149` `path9155` `path9157` | 4.7 万–45.1 万 km² 的超大异常多边形，互相重叠、覆盖南部各州；与任何 NE 州精确 IoU ≤ 0.47，亦非任何州的缩放副本 | **待你确认**：南部各州无法定名，24 条保持魔数（另非魔数的 `path5382-1` 同属此异常） |
| world-states-provinces.svg | `UA` `Luhansk` `Donetsk` | `fill="none"` 仅描边、被两州填充路径完全遮挡；形状是其对应州的畸变复制（bbox 归一化相似度 0.75/0.67） | 已命名、非魔数，本次不动（疑为高亮/争议区叠加层，待确认） |
| world-states-provinces.svg | `EC` `path31054`＋7 条单岛 path | 加拉帕戈斯画了两层：一条 path 含全群岛 7 个子路径，另有 7 条单岛 path 叠在其上 | 按拆分规则命名（`EC-W` + `EC-W-1…7`），冗余几何记入文末第 6 条 |
| world-states-provinces.svg | `TN` `path9180`（742 km²）/`path8175`（647 km²）/`path9012`（223 km²） | 突尼斯沿海碎块/岛屿（克肯纳群岛一带），与所有 NE 候选 IoU 低 | 保持魔数 |
| world-states-provinces.svg | `EG` `path10625` | 61 km²，质心 31.39N/32.08E（尼罗河三角洲）＝塞得港/达米埃塔一带碎块；propose 误配 `EG-LX`（卢克索，25.7N 处，距离 634 km）| 保持魔数（非卢克索） |
| world-states-provinces.svg | `PE` `path23983` | 35549 km²，质心 -11.72S/-76.58W（利马大区东北、近 Junín 界）；既非 NE `PE-CAL`（卡亚俄，沿海小直辖市）也非 `PE-LIM` 主体，35549 km² 的归属在 NE 中无唯一候选 | 保持魔数（利马大区/卡亚俄歧义，待确认） |
| world-states-provinces.svg | `SA` `path3234`/`path5488`/`path5482`/`path5480` | 353/126/124/67 km²，红海 Farasan 群岛（16.7N/42.0E、27.3N/49.6E、16.9N/41.9E、17.0N/41.9E），与内陆 NE 省无重叠 | 保持魔数（岛屿） |
| world-states-provinces.svg | `MN` `path6312`（6801 km²）/`path6373`（627 km²） | 与 NE 省份精确 IoU 均极低，无唯一归属 | 保持魔数 |
| world-states-provinces.svg | `VE` 13 条：`path3414` `path3412` `path3416` `path3426` `path3422` `path3418` `path32682` `path3424` `path3602` `path32684` `path3420` `path32686` `path3428` | 58–263 km²，奥里诺科三角洲（8.5–10.4N / -60.8–-62.7W）沼泽/河岛，NE 仅 `VE-X`（Amacuro Delta 三角洲）无细分 | 保持魔数（三角洲地形体） |
| world-states-provinces.svg | `MD` `path10502`（3633 km²）/`path10616`（294 km²）/`path10618`（286 km²） | 德涅斯特河左岸（德左/外涅斯特）及其 Grigoriopol/Ialoveni 一带；NE 用 `MD-SN` 表德左，图上拆分多块、边界争议 | 保持魔数（争议地区） |
| world-states-provinces.svg | `IR` `path9906`/`path9833`/`path9826`/`path9828` | Yazd（x0.36 面积不符）、Zanjan/Qazvin 歧义（IoU 0.31/0.30）、Alborz（IoU 0.17）、德黑兰附近无归属（12238 km²） | 保持魔数（面积/IoU/歧义） |
| world-states-provinces.svg | `IR` `path4564`/`path4560`/`path4562` | 1577/109/73 km²，霍尔木兹海峡岛屿（格什姆/霍尔木兹一带） | 保持魔数（岛屿） |
| world-states-provinces.svg | `DO` `path8850`（795 km²）/`path8641`（142 km²）/`path8650`（38 km²） | La Romana（IoU 0.34 偏低）及 2 条沿海碎块 | 保持魔数 |
| world-states-provinces.svg | `IE` `path8622`/`path8532`/`path8590`/`path8634`/`path8585`/`path8669` | Cork/Galway/Limerick/Waterford/Tipperary/都柏林等市郡混排，IoU 0.03–0.41，图与 NE 郡边界差异大 | 保持魔数 |
| world-states-provinces.svg | `IE` `path5348`（122 km²）/`path5352`（36 km²） | 爱尔兰西海岸离岛 | 保持魔数 |
| world-states-provinces.svg | `TZ` `path8668`（49506 km²）/`path8837`（323 km²） | Shinyanga/Geita 歧义（IoU 0.38/0.37）、桑给巴尔 Mjini Magharibi 城镇 | 保持魔数 |
| world-states-provinces.svg | `CU` `path8272`+7 条：`path8274` `path9730` `path3590` `path3594` `path3592` `path3586` `path3588` | 古巴离岛/近岸碎块 | 保持魔数 |
| world-states-provinces.svg | `NZ` 7 条：`path63557` `path58931` `path58943` `path58941` `path58935` `path58939` `path58945` | 新西兰离岛（225/96/72 km² 等），与 NE 无对应 | 保持魔数 |
| world-states-provinces.svg | `RS` `path27452`/`path27408`/`path27233`/`path27406`/`path27410` | 42.xN/20.xE 科索沃地区，NE 无对应（争议地区） | 保持魔数 |
| world-states-provinces.svg | `US` 州拆分块（`US-TX`/`US-OR`/`US-WA`/`US-NY`/`US-VA`/`US-NJ`/`US-MA-mainland`/`US-MA-chappaquiddick`） | 已命名州的 mainland/island 拆分块，base_id 与已有 id 重名 | 待按拆分规则补 `-1`/语义后缀 |
| world-states-provinces.svg | `US` `path10154` `path10152` `path10162` `path10160` `path10166` `path10164` `path10781` `path10158` `path10156`、`US-DC`（792 km²） | 洛杉矶外岛（Santa Catalina）、密西西比/Washington 湾飞地、得州海岛、华盛顿特区放大块 | 保持魔数 |
| world-states-provinces.svg | `RU` `path6451`（129515 km²） | 新地岛（75.27N/57.56E），NE `RU-X01~` 无对应 | 保持魔数 |
| world-states-provinces.svg | `RU` `path6633`（印古什）/`path6655`（阿迪格） | 北高加索小共和国，IoU≤0.26 | 保持魔数 |
| world-states-provinces.svg | `RU` `RU-SPE`/`RU-MOS` | 圣彼得堡、莫斯科，已是规范 id（城市放大），非魔数 | 不动 |
| world-states-provinces.svg | `TR` `path3456` | 23949 km²，质心 41.31N/27.32E＝土耳其欧洲部分（东色雷斯）整体单元，横跨 Edirne/Kırklareli/Tekirdağ/İstanbul 等省（这些省图中已单独绘制并命名），无单一 NE admin-1 对应 | 保持魔数 |
| world-states-provinces.svg | `TH` 8 条：`path68124`（213 km²，12.08N/102.34E，象岛）、`path68118`（176，6.63N/99.66E，达鲁岛）、`path68120`（175，9.52N/100.00E，苏梅岛）、`path68126`（126，11.69N/102.59E，象岛）、`path68116`（117，7.57N/99.07E）、`path68122`（88，9.76N/100.02E，帕岸岛）、`path68114`（78，8.05N/98.59E）、`path72590`（49，7.14N/99.65E） | 泰国离岛/近岸碎块（苏梅、帕岸、象岛、达鲁岛等），与 NE admin-1 无对应（NE 泰国无离岛单元），归属省为 Trat/Surat Thani/Satun/Krabi/Trang 等 | 保持魔数 |

## 已知问题（本次任务之外，待决定是否修）

1. **国家轮廓路径 id 不规范**：191 个国家组的轮廓路径 id 是 `<cc>` 小写，但另有 21 个不是。
   库依赖 `src/svg-world-map.js:256` 的 `child.id == country.id.toLowerCase()` 识别主路径，这 21 国目前是错位的。
   典型：`TW` 的 `TW-TAO` 实际是台湾整岛轮廓；`YE` 轮廓叫 `path2592`；`EH` 轮廓叫 `path12345`；`AO` 轮廓在 `<g id="ao">` 里但叫 `path3888`；`TL` 轮廓叫 `path27340`。
2. **命名体系与本图不一致的国家**（共 62 个）：如 IT（图上用大区名 `IT-lombardy`，NE 是省）、
   ES、FR、CN、AU、MY、PH、GB、UG、JP（NE 名称带长音符）等。这些需要逐国决定口径，未在本批处理。
3. **NE 非标准 ISO 码（`X01~`/`X1~`/`X2~`）**：这些单元 NE 没有标准 ISO 码，本方案按规则退化为英文名 kebab。已遇到的建议改用真实 ISO 码，待确认：
   - `TJ` NE `TJ-X01~` = Districts of Republican Subordination → `TJ-RA`（现名 `TJ-districts-of-republican-subordination`）
   - `LR` NE `LR-X1~` = Gbarpolu → `LR-GP`（现名 `LR-gbarpolu`）；NE `LR-X2~` = River Gee → `LR-RG`（现名 `LR-river-gee`）
   - `TD` NE `TD-X01~` = Ennedi → `TD-EN`（2012 年前旧区，已拆分；现名 `TD-ennedi`）
4. **UN 数据同步**：`src/country-data.csv` 只有 6 列（code/name/longname/sovereignty/region/population），
   不含省份数据；省份只存在于 `src/country-data.json`，且目前只有 CA/CN/AU 三国。
   因此重命名魔数 id 暂时无需同步这两个文件；等到修改 CA/CN/AU 等国已有省份 id 时，必须同时改 `country-data.json` 的省份 key。
5. **NE 的 `iso_3166_2` 偶有错误**：`SD` 的 `SD-DS` 出现两次（分别记为南达尔富尔与东达尔富尔），中达尔富尔被标成 `SD-DE`（正确是 `SD-DC`）。
   批次 5 已按官方码修正；后续若遇到「候选取不到 / 候选冲突」，先用 ISO 3166-2 官方列表核实 NE 的码再定名。
6. **NE 的阿富汗码有 3 处错误**：`AF-PIA`/`AF-PKA`（Paktia/Paktika）互换；`AF-PAR`、`AF-URU` 各重码一次，实为 Panjshir（`AF-PAN`）与 Daykundi（`AF-DAY`）。
   批次 7 已按 Wikipedia ISO 3166-2:AF 校正，故图上 4 条 id（`AF-PIA`/`AF-PKA`/`AF-PAN`/`AF-DAY`）与 NE 的码不同名，
   对数据时需注意。同类问题还有 `CO-CUN`（波哥大与昆迪纳马卡重码，已用 `CO-DC`）。
7. **重复/多余几何**（本图自带，未删改，仅命名）：
   - `EC` 加拉帕戈斯：`path31054`（含 7 个子路径）与 7 条单岛 path 描述同一批岛 → `EC-W` / `EC-W-1…7`。
   - `UA` `Luhansk`/`Donetsk`：仅描边、被填充路径遮挡的畸变副本。
   - `NG` 24 条超大重叠多边形（见「跳过/待确认」表），是整个南部无法定名的根因。
   - `GE` 6 条嵌套多边形、`AF` 的 NE 重码要素同属此类。
8. **校验工具注意**：`%TEMP%\batchfast.py` 的 IoU 按 bbox **交集**统计，套嵌时虚高（会把 45 万 km² 的块判成 1 万 km² 州的 0.7 IoU）。
   后续批量一律用 `%TEMP%\ious.py`（并集范围 + PIL 逻辑运算，等价真值）复核，再用 `%TEMP%\vb2.py` 做「除 id 外字节全同」校验。
