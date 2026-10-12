# cook-speed

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

`.github/workflows/dns_cf.yml` 每 6 小时执行一次：

1. 临时刷新最新 IP 池
2. 从本地 `ipTop10.html` 读取优选 IP
3. 电信、联通、移动轮询取候选 IP，进行去重、Cloudflare 网段与 TCP 443 连通性检查
4. 更新 `CF_DNS_NAME` 对应的 A 记录，记录不足时自动补齐至 60 条（DNS Only）

需要 Secrets：

```text
CF_API_TOKEN
CF_ZONE_ID
CF_DNS_NAME
PUSHPLUS_TOKEN   # 可选
CF_DNS_RECORD_COUNT # 工作流已配置 60，可设置为 1–60（默认使用现有记录数）
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

这套机制是“聚合已经由不同网络环境持续测速维护的结果”，不是用 GitHub Actions Runner 自己模拟中国电信、联通、移动测速。GitHub Runner 的网络位置无法代表三大运营商实际用户，因此三网分类以对应数据源为准。

## 页面与 60 条解析记录

- GitHub Pages: https://kityyj.github.io/cf-speed-dns/
- 页面“当前 DNS 解析 IP”通过公网 DoH 查询 `cdn.jia.nz`，展示实际返回的 A 记录（可能有解析缓存）。
- 页面“最新榜首”显示聚合池的三网候选 IP；它们不必与当前 DNS 完全一致。
- `dns_cf.yml` 在每次运行时以 `CF_DNS_RECORD_COUNT=60` 为目标，自动增加缺失 A 记录，不自动删除超额记录或开启 Cloudflare 代理。
- DNS 记录创建和更新都依赖 GitHub Secrets 中具有 DNS 编辑权限的 Cloudflare API Token。
- **注意：** 60 条 A 记录不是速度评分或智能负载均衡；DNS 响应会变大，部分客户端或递归解析器可能截断返回，客户端也不一定选最快地址。GitHub Runner 的 TCP 测试不能代表中国三网实际速度。
