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

## 数据源

| 数据源 | 用途 | 来源 |
| --- | --- | --- |
| `maxminddb-geolite2`（已安装） | 内置 GeoLite2-City.mmdb，反查 IP 得到 (country, subdivision, city) | pip：`pip install maxminddb-geolite2` |
| `ip2country-v4.tsv.gz` | 全球 IPv4 段→国家 映射，用于生成各国家的 IP 段作为采样池 | iptoasn.com 免费下载：`https://iptoasn.com/data/ip2country-v4.tsv.gz` |
| ip-api.com | 在线反查：给定 IP 返回 `countryCode` / `region` / `regionName` / `city`（免费版有速率限制） | https://ip-api.com |

匹配链路：

```
SVG 已命名 id (CC-XX)
   │
   ├─ 离线：用 maxmind 为该 (cc, region) 找到若干真实代表 IP
   │         （黄金比例散列遍历 iptoasn 的该国 IP 段 + 缺失省定向补采）
   │
   └─ 在线：用 ip-api 批量反查这些 IP，取 countryCode+region 拼接为 "CC-REGION"，
            与 SVG 中该 id【精确相等】则命中
```

## 用法

```bash
# 离线：检查 SVG 干净 id 能否从 maxmind 找到代表 IP（不消耗 ip-api 配额）
python tests/ip_naming_test.py --offline

# 在线：对指定国家做 ip-api 严格反向校验
python tests/ip_naming_test.py --countries cn,us,de

# 在线 + 每省多 IP 投票（提升样本可信度，有更高限流承受）
python tests/ip_naming_test.py --countries cn --vote 5

# 若你有 ip-api 付费 key，可传入以提升配额
python tests/ip_naming_test.py --countries cn --key YOUR_KEY

# 全量（71 国）分批长跑：自动按国家重点 `/ip_naming_test.py`，批次间等待避开限流，
# 结果写入 tests/results/<CC>.log，已完成国家记入 tests/results/done_ctry.csv（可续跑）。
python tests/run_all_online.py --vote 2 --inter 40 --outdir tests/results
python tests/run_all_online.py --countries br,mx --inter 40   # 只跑部分国家
```

`tests/ip_naming_test.py` 参数：
- `--countries`：逗号分隔的国家码（默认空 = 全部国家）
- `--offline`：只做离线覆盖检查，不发 ip-api 请求
- `--vote N`：每省用 N 个候选 IP 投票，得票最多的作为该省判据（N>=2 启用）
- `--key`：ip-api 付费 API key（可选）
- `--limit`：最多处理 N 条（调试用）

## 判定口径

- **干净 id**：`CC-XX`，`CC`、`XX` 均为 2 位大写字母（与 ISO 3166-2 / ip-api `region` 同构）。
  其余形式（含岛屿碎块、英文名、数字后缀、label/轮廓）**不参与**严格反查判定，
  因为它们本就不与 `CountryCode-Region` 直接一一对应。
- **命中**：ip-api 返回的 `countryCode-region` 与当前待测 id 完全相等。
- **未命中**：返回不一致，或该 IP 查询失败。

## 当前离线覆盖（基线）

- SVG 已命名 id：约 2505 个（含国家 label、轮廓、岛屿碎块等）
- 其中「干净 id」：804 个（覆盖约 71 个有省级命名的国家/地区）
- 能在 maxmind 中找到该国代表 IP 的干净 id：约 576 个（约 72%）
- 缺失的干净 id 集中在 maxmind GeoLite2 数据精度有限的 44 国（共 228 条）：
  也门、索马里、南苏丹、中非、几内亚、乍得、塞内加尔等数据稀疏地区，
  「该省在 maxmind 中没有独立 IP 段」属数据源限制，而非 SVG 命名错误。

> 注：maxmind GeoLite2（2018 版内置）对 202 个国家和地区有省（subdivision）数据；
> 约 40 个只能定位到国家，其中只有南苏丹（SS）与南极（AQ）同时出现在 SVG 的干净 id 中。

## 在线覆盖策略

- **有省样本的国家**：对 SVG 每个干净 id，用该省 maxmind 代表 IP 反查 ip-api，
  期望返回的 `countryCode-region` 精确等于该 id（支持多 IP 投票）。
- **无省样本的国家**（如 SS/AQ 或 maxmind 精度不足的 44 国）：脚本会自动追加该国的
  兜底 IP（country_ips）参与 ip-api 反查，统计 ip-api 实际返回的 `CC-REGION` 是否存在于 SVG 命名中，
  从而实现对「所有国家」的覆盖尝试。

实测命中率（在线，配额允许时）：
- CN（投票）：约 84%~89%
- CN+DE+US（投票）：约 79%
- 未命中主要来自候选 IP 被 ip-api 定位到相邻/总部省份（移动运营商、数据中心 IP），
  属数据源精度问题，而非命名错误。

## 已知限制

1. **ip-api 免费版限流**：无 key 约 15 次/分钟（单 IP 查询）；批量接口单次最多 100 个 IP，
   但对免费用户有更严格的共享配额。全量在线覆盖（数千 IP）会快速触发 `429` / `fail`,
   需分批、加长间隔，或使用付费 key（`--key`）提升配额。
2. **maxmind/IP 精度**：移动运营商、数据中心 IP 常被归到相邻省份或总部省份，
   导致「该省代表 IP 被 ip-api 定位到别的省」的假未命中。多 IP 投票可缓解。
3. **数据源稀疏国**：也门、索马里、南苏丹、中非等少数国家，GeoIP 数据本身缺失大部分省，
   无法用 IP 严谨验证，属数据源限制（脚本以国家兜底 IP 做尽力覆盖）。
4. 本测试只验证命名体系**可连通性**，不验证几何形状/是否勾选正确（那是命名项目的既定工作）。