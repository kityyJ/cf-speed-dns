# cook-speed-dns

Cloudflare 三网优选 IP 聚合池。

项目从多个持续维护的公开优选源拉取 IPv4，统一完成：

- IPv4 合法性校验
- Cloudflare 官方 IPv4 网段校验
- 去重
- 电信 / 联通 / 移动 / 全部分类
- 多来源轮询合并，避免单一来源霸榜
- GitHub Actions 每 30 分钟自动刷新
- 输出 TXT / JSON / 纯 IP 接口
- Cloudflare Pages Functions 兼容 `/ct?ips=6` 这类动态接口
- Cloudflare DNS 更新继续使用同一套聚合结果

## 接口

静态接口：

```text
/api/ct.txt
/api/cu.txt
/api/cmcc.txt
/api/all.txt

/api/ct.json
/api/cu.json
/api/cmcc.json
/api/all.json

/api/ct-ips.txt
/api/cu-ips.txt
/api/cmcc-ips.txt
/api/all-ips.txt
```

部署到 Cloudflare Pages 后，还支持：

```text
/ct?ips=6
/cu?ips=6
/cmcc?ips=8
/all?ips=70

/ct?ips=20&format=json
/cu?ips=20&format=json
/cmcc?ips=20&format=json
/all?ips=50&format=json

/health
```

`ips` 范围为 1–300；不传时默认返回 70 条。

## 数据来源

数据源统一放在 `sources.json`，可以直接增删，不需要改 Python。

当前默认包含：

- CM / 090227 电信、移动及 CloudFlareYes
- ZhiXuan 优选镜像
- Mingyu BestCF
- cmliu 社区地址列表
- WeTest
- CFYes
- LZ 电信 / 联通
- MJZ 电信 / 联通
- SVIP-S 移动

第三方来源失效不会让整个任务失败。脚本会保留其他正常来源；如果某个分类全部来源同时失败，会尽量保留该分类上一次生成的数据。

## 更新机制

`.github/workflows/refresh.yml`

- 每 30 分钟执行一次
- 手动执行
- 聚合器相关代码变更后自动执行
- PR 会真实运行一次聚合器用于验证，但不会提交生成文件

## Cloudflare DNS

`.github/workflows/dns_cf.yml` 每 30 分钟检查并同步一次（GitHub Actions 计划运行可能延迟）：

1. 临时刷新最新 IP 池
2. 从最新三网 JSON 候选池中读取优选 IP
3. 电信、联通、移动优先各选取 10 个 IP；优先参考上游提供的延迟和下载吞吐量，剔除已知低速地址，再结合地区标签排序、去重和验证 Cloudflare IPv4 网段
4. GitHub Runner 负责 HTTPS + TLS SNI + HTTP Host 可用性筛选（必要时可改回 TCP 443）；**绝不把美国 Runner 的延迟当作中国大陆测速**
5. 正常每轮最多更换 6 条 A 记录（避免频繁抖动）；缺记录时直接补齐到 30 条，已有 30 条时保留其余现有记录
6. 同步 `cdn.jia.nz` 的 30 条 A 记录（DNS Only）；记录清空时可以从新的有效候选池重新建立，超过 30 条时清理多余记录

需要 Secrets：

```text
CF_API_TOKEN
CF_ZONE_ID
PUSHPLUS_TOKEN   # 可选
# 工作流固定 CF_DNS_NAME=cdn.jia.nz、CF_DNS_RECORD_COUNT=30
# CF_DNS_MAX_ROTATIONS=6：正常每轮替换最多 6 条，避免一次清空替换
```

## DNSPod

原有 DNSPod 功能保留：

```text
DOMAIN
SUB_DOMAIN
SECRETID
SECRETKEY
PUSHPLUS_TOKEN   # 可选
```

## 本地执行

```bash
python -m pip install -r requirements.txt
python aggregate_ips.py
```

生成：

```text
index.html
ipTop.html
ipTop10.html
api/
data/status.json
```

## 说明

这套机制是“聚合第三方已发布的三网优选结果”，不是用 GitHub Actions Runner 自己模拟中国电信、联通、移动测速。GitHub Runner 的网络位置无法代表中国大陆三网实际用户，因此三网分类以对应数据源为准。上游延迟和速度的测速时间、采样网络、真实性可能不同；下载速度只作为加权参考，**不保证端到端打开速度更快**。

### HTTPS 实际站点兼容性诊断

当前工作流先通过 `cook.jia.nz` 对候选 IP 进行强制 IP 的 HTTPS 访问检查：要求 TLS 证书有效、SNI 和 `Host` 正确，且目标网站返回 2xx/3xx。未通过的候选 IP 会被跳过；如果可用候选不足 30 个则**整次停止 DNS 更新，保留现有 DNS 记录**。额外从选中的 IP 抽样 3 个，输出 HTTP 状态、TCP/TLS 和响应头耗时到 Actions 日志，这些数据只代表 GitHub Runner 路线，**不会作为中国大陆速度评分**。

- `CF_DNS_SITE_VERIFY=1`：启用实站 HTTPS 兼容性过滤；关闭则回退 TCP 443 连通性检查。
- `CF_DNS_SITE_AUDIT_HOST=cook.jia.nz` / `CF_DNS_SITE_AUDIT_PATH=/` / `CF_DNS_SITE_AUDIT_COUNT=3`：待检测域名与日志抽样数量。
- `CF_DNS_MAX_ROTATIONS=6`：已有 30 个 IP 时单轮最多替换 6 个；还未建立或数量不完整时允许直接补齐。
- `cdn.jia.nz` 的 30 条 A 记录仍是通用 Cloudflare 优选入口，不是按访问者运营商动态分流的智能 DNS。
- 真正测量中国大陆用户的网站打开速度，还需要中国电信/联通/移动本地探针，并在确认 HTTP `Host`、TLS SNI 合法后按对应网站域名测试；IP 归属日本/韩国不等于中国大陆用户的访问速度。

## 域名架构与 30 条解析记录

- GitHub Pages: https://kityyj.github.io/cook-speed-dns/
- `cook.jia.nz`（DNS Only CNAME）→ `cdn.jia.nz` → 30 个官方 Cloudflare IPv4 A 记录；不再使用 `cook.cf.090227.xyz`。
- 页面“当前 DNS 解析 IP”通过公网 DoH 查询 `cdn.jia.nz`，展示实际返回的 A 记录（可能有解析缓存）。
- 页面“最新榜首”显示聚合池的三网候选 IP；它们不必与当前 DNS 完全一致。
- `dns_cf.yml` 在每次运行时以 `CF_DNS_RECORD_COUNT=30` 为目标，自动补齐缺失 A 记录或清理超额记录，不开启 Cloudflare 代理。
- DNS 记录创建和更新都依赖 GitHub Secrets 中具有 DNS 编辑权限的 Cloudflare API Token。
- **注意：** 30 条 A 记录不是速度评分或智能负载均衡；DNS 响应会变大，部分客户端或递归解析器可能截断返回，客户端也不一定选最快地址。GitHub Runner 的 TCP 测试不能代表中国三网实际速度。
