# SVG 地图 id 命名工具链

本目录提供把 `src/world-states-provinces.svg`（优先）与 `src/world-states.svg` 中魔数 id
（`pathNNNN`/`gNNNN`/`circleNNNN` 等）补全为规范 id 的自包含工具链，供持续分批自动化使用。

与旧版工具（`D:\work\other\svg-naming\tools`）相比，本目录是**自包含**的：不依赖 `%TEMP%`，
投影/解析/NE 索引全部收在 `svgname.py`，可直接入库、可复现。

## 文件

| 文件 | 作用 |
| --- | --- |
| `svgname.py` | 核心库：SVG path 解析、叶区域提取、Robinson 投影互转、Natural Earth admin-1 索引、id 生成（ASCII 转写 / kebab / 字母后缀大写·数字后缀英文名） |
| `enumerate.py` | 枚举剩余魔数 id，按父国家组分组统计 |
| `analyze.py` | 对比每个剩余组「SVG 魔数叶单元数 vs NE admin-1 要素数」，辅助判断是否可自动命名 |
| `batch.py` | 自动 propose（质心落点 → 并集 bbox IoU → 最近邻兜底）+ apply + verify + 可选 git 提交（依赖 NE 多边形） |
| `fetch_admin.py` | 从 openadmindata.org 拉取某国行政区**质心+英文名+ISO 码** → `data/admin1/<CC>.csv`（无 NE 多边形可用时） |
| `extract_ne.py` | 从 NE 10m 拉某国 label point（质心）+名称 → `data/admin1/<CC>.csv`（openadmindata 质心缺/错位时，如 MG） |
| `fetch_geoboundaries.py` | 从 geoBoundaries（GitHub LFS 媒体源）拉某国 admin 边界多边形算质心 → `data/admin1/<CC>.csv`（「图比 NE 粗/细」的层级错配时） |
| `batch_centroid.py` | 用 `data/admin1/<CC>.csv` 的质心做**最近邻命名**（数字码国家 → 英文名）+ apply + verify + 可选 git 提交 |
| `apply.py` | 应用一份人工确认的 `old_id,new_id` 映射表（含校验 + 可选提交） |
| `auto_batch.py` | **自动化批量处理**：整合 NE 匹配 + 质心近邻 + 测试验证 + IP 数据更新 |
| `fetch_test_ips.py` | 从 ip2location API 获取 IP 测试数据，保存到 `tests/data/ip2loc_lookup/<CC>.csv` |
| `batches/` | 每批的定案映射 CSV（可复现、留痕） |
| `data/admin1/` | 逐国行政区质心参考数据（小体积，随仓库管理；见下方「数据源」） |

## 依赖

- Python 3（`xml.etree`、`unicodedata` 标准库）
- `Pillow`（仅 `batch.py` 的 IoU 栅格化需要）：`pip install pillow`
- Natural Earth 10m admin-1 geojson（约 38.8 MB，公有领域，不入库）
  路径默认 `D:\work\other\svg-naming\data\ne_10m_admin_1_states_provinces.geojson`，
  可用环境变量 `NE_PATH` 覆盖。

  > 该数据源是「省/州」级别 admin-1；对把 SVG 画成「县/市镇」级的国家（如 KE 47 县、AZ 78 rayon、
  > SI 192 občina），NE 粒度比图更细或更粗，几何匹配会失败——这类国家用下面的**质心数据**兜底命名。

- 质心参考数据 `data/admin1/<CC>.csv`（`iso,name_en,lat,lon`，小体积、随仓库管理）
  来源 [openadmindata.org](https://openadmindata.org)（OCHA COD-AB + geoBoundaries，CC BY-IGO）、
  由 `fetch_admin.py` 生成；`batch_centroid.py` 用「投影质心 → 经纬度 → 最近邻(每单元配一次)」匹配命名。
  对「NE 粒度错配」的国家（图是县/市镇级），这一质心法比 NE 多边形更贴合图的尺度。

## 用法

```bash
# 1) 看总体剩余情况
python tools/enumerate.py

# 2) 看哪些剩余组可与 NE 自动匹配（svg 单元数 ≈ NE 要素数才算 OK）
python tools/analyze.py

# 3) 对某国试算提议（不改文件）
python tools/batch.py ST KW

# 4) 应用提议（仅改 id 属性）
python tools/batch.py ST --apply

# 5) 应用后 git 提交（不 push）
python tools/batch.py ST --apply --commit "batch 26: ST"

# 6) 人工定案映射表（跨核对/修正后逐条应用）
python tools/apply.py tools/batches/batch26.csv --commit "batch 26: ST KW"

# 7) 粒度错配国（NE 多边形对不上图的尺度）改用"质心近邻"命名：
python tools/fetch_admin.py KE            # 拉取肯尼亚 47 县质心 -> data/admin1/KE.csv
python tools/batch_centroid.py KE          # 试算最近邻匹配
python tools/batch_centroid.py KE --apply --commit "batch 27: KE"

# 8) 自动化批量处理（推荐）：
python tools/auto_batch.py --dry-run       # 预览所有待处理国家
python tools/auto_batch.py --countries KW,KI  # 处理指定国家（试算）
python tools/auto_batch.py --all --apply   # 处理所有可自动处理的国家

# 9) 补充 IP 测试数据：
python tools/fetch_test_ips.py --missing --limit 5  # 为缺失的国家补充 IP 数据
python tests/ip2loc_naming_test.py --countries VN   # 运行测试验证
```

## 命名规则（详见 `docs/map-id-naming.md`）

| 情况 | 规则 | 例子 |
| --- | --- | --- |
| ISO 3166-2 后缀是字母 | `<CC>-<后缀>` | `US-WA`、`ST-S` |
| ISO 3166-2 后缀是数字 / 无 ISO 码 | `<CC>-<英文名 kebab-case>` | `VN-bac-giang`、`AT-carinthia` |
| 同一行政区分多块 | `<基础id>-<序号>` | `ID-MA-1` |
| 与已有 id 重名 | `<基础id>-<后缀>` | `BG-sofia-23` |

## 安全约束（apply 阶段强制）

- 只替换 `id="..."` 属性，不改几何/结构/顺序；
- 每个旧 id 在文件里必须恰好出现一次，否则不写回；
- 新 id 必须全 ASCII、全局唯一；
- 写回前做 XML 解析检查。

## 数据契约

- `tools/batches/*.csv`：`old_id,new_id`，即每批实际落库的改动（留痕）。
- 跳过/歧义条目与逐国粒度说明记在 `docs/map-id-naming.md` 的「跳过 / 待确认」与批次记录表。