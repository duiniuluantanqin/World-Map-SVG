# SVG 地图 id 命名 — ip-api 连通性测试说明

## 目标

验证 `src/world-states-provinces.svg` 中**已命名的行政区 id**（如 `CN-JS`、`US-VA`、`DE-BY`）
能否通过真实 IP 的 ip-api 反查得到一致的 `CountryCode-Region`，从而证明：
- SVG 命名遵循 ISO 3166-2 / ip-api 的 `region` 编码体系；
- 前端可用「用户 IP → ip-api → id」的方式在 SVG 中定位/高亮对应行政区。

跳过项：`pathNNN`/`gNNN`/`circleNNN` 等魔数 id，以及岛屿碎块（`CN-FJ-mainland`）、
英文名后缀（`AL-tirana`）等非「`CC-XX`（XX=二位字母）」形式的 id。

## 目录

- `tests/ip_naming_test.py`：主测试脚本。
- `docs/ip-naming-test.md`：本说明文档。

## 数据源与本地缓存（按国家分文件缓存）

默认测试**完全离线**，依赖仓库内已固化的本地数据（按国家分文件，随仓库管理）：

```
tests/data/
  maxmind_samples/<CC>.csv   # 每国：cc,region,ip,name（采样缓存）
  ipapi_lookup/<CC>.csv      # 每国：ip,cc,region,city（ip-api 反查缓存）
```

测试时可按国家过滤，只读写对应该国的缓存文件（例如 `--countries cn` 只取 `CN.csv`）。

| 缓存 | 内容 | 更新方式 |
| --- | --- | --- |
| `maxmind_samples/<CC>.csv` | 每国的 (cc, region) → 代表 IP + 名称 | `--refresh-maxmind` 重新采样 |
| `ipapi_lookup/<CC>.csv` | 每国 IP 的 ip-api 反查结果 | `--refresh-ipapi` 联网刷新 |

原始数据源（仅刷新时需要联网）：

| 数据源 | 用途 | 来源 |
| --- | --- | --- |
| `maxminddb-geolite2`（已安装） | 内置 GeoLite2-City.mmdb，反查 IP 得到 (country, subdivision, city) | pip：`pip install maxminddb-geolite2` |
| `ip2country-v4.tsv.gz` | 全球 IPv4 段→国家 映射，用于生成各国家的 IP 段作为采样池 | iptoasn.com 免费下载：`https://iptoasn.com/data/ip2country-v4.tsv.gz` |
| ip-api.com | 在线反查：给定 IP 返回 `countryCode` / `region` / `regionName` / `city`（免费版有速率限制） | https://ip-api.com |

匹配链路：

```
SVG 已命名 id (CC-XX)
   │
   ├─ 离线（默认）：读 maxmind_samples/<CC>.csv 为该 (cc, region) 取代表 IP，
   │                读 ipapi_lookup/<CC>.csv 取该 IP 的反查结果 → 拼接 "CC-REGION"，
   │                与 SVG 中该 id【精确相等】则命中。全程不联网。
   │
   └─ 刷新（按需）：--refresh-maxmind 重新采样；--refresh-ipapi 联网补齐缓存。
```

## 用法

```bash
# 默认离线校验（读缓存，秒级，不联网）
python tests/ip_naming_test.py --countries cn,us,de

# 离线覆盖检查：多少漂亮 id 有缓存代表 IP（不联网）
python tests/ip_naming_test.py --offline

# 每省多 IP 投票（提升可信度）
python tests/ip_naming_test.py --countries cn --vote 5

# 按需重新采样 maxmind（写 tests/data/maxmind_samples.csv）
python tests/ip_naming_test.py --refresh-maxmind

# 按需联网刷新某国 ip-api 缓存（写 tests/data/ipapi_lookup.csv；免费限流需耐心）
python tests/ip_naming_test.py --countries cn --refresh-ipapi --vote 2

# 全量分批联网刷新 ip-api 缓存（71 国，批次间等待避开限流，可续跑）
python tests/run_all_online.py --refresh-ipapi --vote 2 --inter 30 --outdir tests/results
python tests/run_all_online.py --refresh-ipapi --countries br,mx --inter 30
```

`tests/ip_naming_test.py` 参数：
- `--countries`：逗号分隔的国家码（默认空 = 全部国家）
- `--offline`：只做离线覆盖检查（是否每个省有候选 IP），不发 ip-api 请求、不联网
- `--refresh-maxmind`：重新用 maxmind 采样并写回 `maxmind_samples/<CC>.csv`
- `--refresh-ipapi`：对未缓存的候选 IP 联网反查并写回 `ipapi_lookup/<CC>.csv`
- `--key`：ip-api 付费 API key（可选，提升限流）
- `--limit`：最多处理 N 条（调试用）

> 注：正向口径下，校验会把每个地区的**全部候选 IP**（`maxmind_samples/<CC>.csv` 中的每一行）
> 都交给 ip-api 反查，只要任一候选 IP 解析出的 `CC-REGION` 命中 SVG 即算该省命中——
> 不再只用单个「代表 IP」，也因此没有投票（`--vote`）概念，该参数已废弃、保留仅为兼容。

## 判定口径（正向：以 ip-api 为准）

- **干净 id**：`CC-XX`，`CC`、`XX` 均为 2 位大写字母（与 ISO 3166-2 / ip-api `region` 同构）。
  其余形式（含岛屿碎块、英文名、数字后缀、label/轮廓）**不参与**判定，
  因为它们本就不与 `CountryCode-Region` 直接一一对应。
- **正向命中**：对每个候选 IP，用 ip-api 反查得到 `countryCode-region` 拼成 id，
  若**该 id 存在于 SVG 已命名集合**，则该 id 记一次命中。
  这以 ip-api 为准；候选 IP 的省份归属不预先用 maxmind 假设，因此
  同一 IP 在 maxmind/IP 库的省份归属差异不会造成误判。
- **未命中**：某 SVG 干净 id 没有任何候选 IP 能被 ip-api 解析成它（需真实 IP，或数据源无该省）。
- **命名缺口**：ip-api 能拼出、但 SVG 中不存在的 id，才是真正的命名缺口。

## 当前离线覆盖（基线）

- SVG 已命名 id：约 2505 个（含国家 label、轮廓、岛屿碎块等）
- 其中「干净 id」：804 个（覆盖约 71 个有省级命名的国家/地区）
- 能在 maxmind 中找到该国代表 IP 的干净 id：约 576 个（约 72%）
- 缺失的干净 id 集中在 maxmind GeoLite2 数据精度有限的 44 国（共 228 条）：
  也门、索马里、南苏丹、中非、几内亚、乍得、塞内加尔等数据稀疏地区，
  「该省在 maxmind 中没有独立 IP 段」属数据源限制，而非 SVG 命名错误。

> 注：maxmind GeoLite2（2018 版内置）对 202 个国家和地区有省（subdivision）数据；
> 约 40 个只能定位到国家，其中只有南苏丹（SS）与南极（AQ）同时出现在 SVG 的干净 id 中。

## 在线覆盖策略（刷新缓存时）

- 对 SVG 每个干净 id，采样若干真实候选 IP（maxmind 仅用于生成候选 IP 池，不假设省份归属），
  用 ip-api 反查，拼 `countryCode-region` 检查是否存在于 SVG 已命名集合。
- 无省样本的国家（如 SS/AQ 或 maxmind 精度不足的 44 国）：脚本会自动追加该国的兜底 IP 参与反查。
- 刷新后的结果固化为缓存（`ipapi_lookup/<CC>.csv`），**此后默认离线复用**，无需重复联网。

实测结果（正向口径，可用缓存复现）：
- CN：约 23/31（可被 ip-api 解析出在 SVG 中命中的省份占比）
- 未命中的省多为候选 IP 被 ip-api 归到相邻省（移动运营商/数据中心 IP 归属跨省），
  或数据源本身无该省独立 IP；这些是数据源精度问题，而非命名错误。

## 已知限制

1. **ip-api 免费版限流**：无 key 约 15 次/分钟（单 IP 查询）；批量接口单次最多 100 个 IP，
   但对免费用户有更严格的共享配额。全量在线覆盖（数千 IP）会快速触发 `429` / `fail`,
   需分批、加长间隔，或使用付费 key（`--key`）提升配额。
2. **maxmind/IP 精度**：移动运营商、数据中心 IP 常被归到相邻省份或总部省份，
   导致「该省代表 IP 被 ip-api 定位到别的省」的假未命中。多 IP 投票可缓解。
3. **数据源稀疏国**：也门、索马里、南苏丹、中非等少数国家，GeoIP 数据本身缺失大部分省，
   无法用 IP 严谨验证，属数据源限制（脚本以国家兜底 IP 做尽力覆盖）。
4. 本测试只验证命名体系**可连通性**，不验证几何形状/是否勾选正确（那是命名项目的既定工作）。