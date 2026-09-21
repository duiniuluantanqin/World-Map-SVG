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
| `batch.py` | 自动 propose（质心落点 → 并集 bbox IoU → 最近邻兜底）+ apply + verify + 可选 git 提交 |
| `apply.py` | 应用一份人工确认的 `old_id,new_id` 映射表（含校验 + 可选提交） |
| `batches/` | 每批的定案映射 CSV（可复现、留痕） |

## 依赖

- Python 3（`xml.etree`、`unicodedata` 标准库）
- `Pillow`（仅 `batch.py` 的 IoU 栅格化需要）：`pip install pillow`
- Natural Earth 10m admin-1 geojson（约 38.8 MB，公有领域，不入库）
  路径默认 `D:\work\other\svg-naming\data\ne_10m_admin_1_states_provinces.geojson`，
  可用环境变量 `NE_PATH` 覆盖。

  > 该数据源是「省/州」级别 admin-1；对把 SVG 画成「县/市镇」级的国家（如 KE 47 县、AZ 78 rayon、
  > SI 192 občina），NE 粒度比图更细或更粗，几何匹配会失败——这类国家需要更细的数据源（GADM /
  > geoBoundaries / OCHA COD）才能可靠命名，见 `docs/map-id-naming.md`。

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