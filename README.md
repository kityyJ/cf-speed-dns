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
6. 同步 `cdn.yigeyao.com` 的 30 条 A 记录（DNS Only）；记录清空时可以从新的有效候选池重新建立，超过 30 条时清理多余记录

需要 Secrets：

```text
CF_API_TOKEN
# CF_ZONE_ID 在 GitHub Actions 工作流中已固定为 yigeyao.com 的 Zone ID（公开标识符，非密钥）
PUSHPLUS_TOKEN   # 可选
# 工作流固定 CF_DNS_NAME=cdn.yigeyao.com、CF_DNS_RECORD_COUNT=30
# CF_DNS_MAX_ROTATIONS=6：正常每轮替换最多 6 条，避免一次清空替换
```

## 当前维护的组件

- `aggregate_ips.py`、`sources.json`：拉取并聚合电信、联通、移动候选 IP。
- `dnscf.py`、`.github/workflows/dns_cf.yml`：筛选并维护 `cdn.yigeyao.com` 的 30 条 DNS-only A 记录。
- `audit_websites.py`、`.github/workflows/audit_websites.yml`：只读检查 `www.jia.nz` 和 `cook.jia.nz` 的 HTTPS 兼容性。
- `index.html`、`api/`、`data/`：GitHub Pages 展示和对外 IP 数据接口，由刷新任务生成。
- `ipTop.html`、`ipTop10.html`：为旧版接口兼容保留的自动生成数据，不是网页。
- `functions/`：部署到 Cloudflare Pages 时可选用的动态接口。
- `.github/workflows/refresh.yml`：每 30 分钟更新数据并部署 GitHub Pages。
- `.github/workflows/pages.yml`：GitHub `main` 分支有变更时进行 Pages 部署。
- `.github/workflows/test_dns.yml`：对 DNS 同步逻辑执行测试。

旧版 DNSPod 脚本（未配置密钥且未生效）、检查 `best.jia.nz` 的过时脚本、无效的 Fork 上游同步任务和旧版页面生成兼容入口已清理，避免误导及额外空跑。

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

`www.jia.nz`、`cook.jia.nz`、`paycn.jia.nz`、`status.jia.nz` 都 CNAME 到 `cdn.yigeyao.com`，共用 30 条 A 记录。**候选 IP 必须同时兼容两个网站**，不能仅通过一个站点的测试。

- `.github/workflows/audit_websites.yml`：每小时以 GitHub Runner 独立检查目前已发布的 30 个 IP，在两个站点分别验证 TLS 证书、SNI、Host、HTTP 状态与响应头耗时。出现失败只报告，不擅自更改 DNS。
- 运行日志：https://github.com/kityyJ/cook-speed-dns/actions/workflows/audit_websites.yml
- 2026-10-12 首次检查为两个网站均 30/30 通过，但这是海外 Runner 的可用性验证，**不等于中国大陆加载速度测试**。

当前工作流先通过 `cook.jia.nz` 和 `www.jia.nz` **两个网站**对候选 IP 进行强制 IP 的 HTTPS 访问检查：要求 TLS 证书有效、SNI 和 `Host` 正确，且两个目标网站均返回 2xx/3xx。未通过的候选 IP 会被跳过；如果可用候选不足 30 个则**整次停止 DNS 更新，保留现有 DNS 记录**。额外从选中的 IP 抽样 3 个，输出 HTTP 状态、TCP/TLS 和响应头耗时到 Actions 日志，这些数据只代表 GitHub Runner 路线，**不会作为中国大陆速度评分**。

- `CF_DNS_SITE_VERIFY=1`、`CF_DNS_SITE_VERIFY_EXTRA_HOSTS=www.jia.nz`：要求同时通过 `cook.jia.nz` 和 `www.jia.nz` 的实站 HTTPS 兼容性检查；关闭验证则回退 TCP 443 连通性检查。
- `CF_DNS_SITE_AUDIT_HOST=cook.jia.nz` / `CF_DNS_SITE_AUDIT_PATH=/` / `CF_DNS_SITE_AUDIT_COUNT=3`：待检测域名与日志抽样数量。
- `CF_DNS_MAX_ROTATIONS=6`：已有 30 个 IP 时单轮最多替换 6 个；还未建立或数量不完整时允许直接补齐。
- `cdn.yigeyao.com` 的 30 条 A 记录仍是通用 Cloudflare 优选入口，不是按访问者运营商动态分流的智能 DNS。
- 真正测量中国大陆用户的网站打开速度，还需要中国电信/联通/移动本地探针，并在确认 HTTP `Host`、TLS SNI 合法后按对应网站域名测试；IP 归属日本/韩国不等于中国大陆用户的访问速度。

## 跨域名迁移与 30 条解析记录

- GitHub Pages: https://kityyj.github.io/cook-speed-dns/
- `www.jia.nz`、`cook.jia.nz`、`paycn.jia.nz`、`status.jia.nz` → `cdn.yigeyao.com`（DNS Only CNAME）→ 30 个官方 Cloudflare IPv4 A 记录。
- 新 CDN 在 Cloudflare `yigeyao.com` 区域管理，所有新建的 30 条 A 记录均带 `[CF-IP]` 中文用途备注。**目前旧 `cdn.jia.nz` 的 30 条 A 记录暂时保留，作为回退**；待确认新区域自动更新正常后，再决定是否将旧域名改为兼容 CNAME。
- 页面“当前 DNS 解析 IP”通过公网 DoH 查询 `cdn.yigeyao.com`，展示实际返回的 A 记录（可能有解析缓存）。
- 页面“最新榜首”显示聚合池的三网候选 IP；它们不必与当前 DNS 完全一致。
- `dns_cf.yml` 在每次运行时以 `CF_DNS_RECORD_COUNT=30` 为目标，自动补齐缺失 A 记录或清理超额记录，不开启 Cloudflare 代理。
- DNS 记录创建和更新都依赖 GitHub Secrets 中具有 DNS 编辑权限的 Cloudflare API Token。
- **注意：** 30 条 A 记录不是速度评分或智能负载均衡；DNS 响应会变大，部分客户端或递归解析器可能截断返回，客户端也不一定选最快地址。GitHub Runner 的 TCP 测试不能代表中国三网实际速度。

> 跨区部署注意：GitHub Secret `CF_API_TOKEN` 必须具有 **yigeyao.com 区域 DNS 编辑权限**（Zone → DNS → Edit）；区域 ID 不是密钥，已配置在两个工作流中。旧 Token 只允许访问 jia.nz，新区域首次运行返回 HTTP 403，自动维护和审计会失败，直到更新 Secret。

### 一次性修复 GitHub Token 权限

1. [Cloudflare API Tokens](https://dash.cloudflare.com/profile/api-tokens)：创建 **Edit zone DNS** Token，将资源范围仅限 `yigeyao.com`（不需要把 Token 发到聊天或提交到仓库）。
2. [GitHub Actions Secrets](https://github.com/kityyJ/cook-speed-dns/settings/secrets/actions)：更新仓库 Secret `CF_API_TOKEN` 的值。
3. 重新运行 [DNS 自动维护](https://github.com/kityyJ/cook-speed-dns/actions/workflows/dns_cf.yml) 和 [HTTPS 全池审计](https://github.com/kityyJ/cook-speed-dns/actions/workflows/audit_websites.yml)，均成功后才能确认已完全自动化。

迁移期间：`www.jia.nz`、`cook.jia.nz`、`paycn.jia.nz`、`status.jia.nz` 已直接指向 `cdn.yigeyao.com`，使用现有 30 个优选 IP；旧 `cdn.jia.nz` 暂不删除。

## 首页网络状态（参考 cf.090227.xyz 的信息架构）

首页采用浅色橙色仪表板，支持 `#/network`、`#/ip`、`#/speed`、`#/api`、`#/resources` 路由导航及深浅主题。

- 国内服务观测：浏览器请求 `myip.ipip.net/json` 获取该接口看到的公网出口 IP；若被 CORS 或网络策略拦截则显示不可用。
- 国外服务观测：浏览器请求 `ipwho.is` 返回出口 IP、地区和网络信息。
- Cloudflare 接入：浏览器调用 `speed.cloudflare.com/meta` 返回 IP 与接入机房 Colo。
- Google 测试：只尝试加载 Google HTTPS 静态图标并报告请求耗时或不可用，**不会虚构 Google 出口 IP**。
- 上述服务看到的 IP 可能相同；地区和运营商标签由各家服务提供，不代表已经确认各运营商独立路由。
- 常用网站测速：浏览器加载 8 个站点公开图标，显示真实加载耗时或失败，不是 ICMP/TCP Ping，也不能代表完整网页打开速度。
- 访问者 IP 默认脱敏，用户可以点击显示完整 IP。前端直接访问第三方检测 API，第三方可能看到访客 IP；本站不保存网络检测结果。
- 支持端口展示引用 [Cloudflare 官方文档](https://developers.cloudflare.com/fundamentals/reference/network-ports/)，仅说明其代理默认支持的端口，不代表自建 DNS/源站已全部开放。

前端检测代码放在 `assets/network.js`，样式在 `assets/network.css`。主页 `index.html` 仍由 `aggregate_ips.py` 的 `INDEX_HTML` 生成，两处必须保持一致；更新 DNS 的 GitHub Actions 未修改。
