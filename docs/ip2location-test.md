# SVG id 命名 — ip2location 连通性测试

## 目标与背景

`tests/ip_naming_test.py` 原先用 ip-api 反查验证已命名 id 的可连通性。ip-api 的问题：

- 免费版限流严（约 15 次/分钟）；
- `region` 只返回简称，且**对数字码国家（VN/KR/TR/TH/JP 等）不返回 code**，
  导致这些国家无法做「`CountryCode-Region`」精确比对（文档「已知限制」已记录）。

本目录新增 `tests/ip2loc_naming_test.py`，改用 **ip2location.io**（会员 key，限流更宽松）：

- `region.code` 返回**完整 code**：字母码国家给 `US-IL`、数字码国家给 `VN-54`/`KR-11`；
- `region.name` 返回英文名（如 `Bac Giang`），可拼数字码国家在 SVG 里的英文名 id（`VN-bac-giang`）。

即一个数据源同时覆盖「字母码」与「数字码」两类国家。

## 数据源与本地缓存

```
tests/data/ip2loc_lookup/<CC>.csv   # 每国：ip,cc,region_code,region_name,city
```

离线缓存按国家分文件，随仓库管理。候选 IP 池复用仓库内已有的
`tests/data/ipapi_lookup/<CC>.csv` 与 `tests/data/maxmind_samples/<CC>.csv` 中的真实 IP。

## 用法

```bash
# key 通过环境变量传入（不落库），或 --key
export IP2LOCATION_KEY="<你的 key>"

python tests/ip2loc_naming_test.py --countries us,vn,kr        # 默认离线读缓存（秒级）
python tests/ip2loc_naming_test.py --countries us,vn,kr --refresh   # 联网刷新该国的 ip2location 缓存
python tests/ip2loc_naming_test.py --offline                   # 只看缓存覆盖
```

参数：`--countries`（逗号分隔，默认全部）、`--refresh`（联网补查并写回缓存）、
`--key`（默认读环境变量 `IP2LOCATION_KEY`）、`--limit`（调试限量）、`--pause`（查间隔，默认 0.2s）。

## 匹配口径（正向，以 ip2location 为准）

对每个候选真实 IP，用 ip2location 得到 `(country_code, region.code, region.name)`，拼出候选 id：

1. `region.code`（字母码国家命中 `CC-XX`，如 `US-IL`）；
2. `CC-kebab(region.name)`（数字码国家命中英文名，如 `VN-54` + `Bac Giang` → `VN-bac-giang`）。

只要任一候选 id 存在于 SVG 已命名集合，即算该 id 命中。这以 ip2location 为准，不预设省份归属。

## 实测样例（数字码）

| IP | country | region.code | region.name | 命中 SVG id |
| --- | --- | --- | --- | --- |
| 103.164.244.240 | VN | `VN-54` | Bac Giang | `VN-bac-giang` |
| 104.36.218.171 | US | `US-IL` | Illinois | `US-IL` |

## 已知限制

1. 数字码国家的 SVG id 是英文名 kebab（见 `docs/map-id-naming.md` 命名规则），匹配依赖
   `region.name` 的英文拼写与 `kebab()` 转写一致；个别带变音/连字符的名称需核对。
2. 候选 IP 池来自旧有缓存，**数字码国家（VN/KR/TR/TH/JP）此前无候选 IP**，需先用
   `python tests/ip_naming_test.py --refresh-maxmind` 补采样，或用真实 IP 追加到
   `ip2loc_lookup/<CC>.csv`。
3. 数据中心/移动运营商 IP 常被归到相邻省或总部省，属数据源精度问题，多 IP 采样可缓解。