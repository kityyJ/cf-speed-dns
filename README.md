# cf-speed-dns

自动读取 Cloudflare DNS A 记录，生成 Cloudflare 优选 IP 页面与纯文本接口，并可通过 GitHub Actions 自动更新 DNS。

## 页面

默认 GitHub Pages 地址：

- 首页：https://kityyj.github.io/cf-speed-dns/
- 全部 IP：https://kityyj.github.io/cf-speed-dns/ipTop.html
- Top 10：https://kityyj.github.io/cf-speed-dns/ipTop10.html

> 原仓库中的 `CNAME` 指向 `ip.164746.xyz`，该域名属于上游项目，会导致本仓库 Pages 域名冲突。当前版本已移除该绑定，恢复使用仓库自己的 GitHub Pages 地址。

## 功能

- 从 Cloudflare DNS API 读取指定域名的 A 记录。
- 自动去重并过滤无效 IPv4。
- 生成适配手机和桌面的静态页面。
- `ipTop.html` 输出全部有效 IP。
- `ipTop10.html` 只输出前 10 个 IP。
- 支持 Cloudflare DNS 自动更新。
- 支持 DNSPod DNS 自动更新。
- 可选 PushPlus 通知。

## Cloudflare DNS 配置

在 GitHub 仓库的 Actions secrets 中配置：

- `CF_API_TOKEN`
- `CF_ZONE_ID`
- `CF_DNS_NAME`
- `PUSHPLUS_TOKEN`（可选）

工作流：`.github/workflows/dns_cf.yml`

## DNSPod 配置

配置以下 Secrets：

- `DOMAIN`
- `SUB_DOMAIN`
- `SECRETID`
- `SECRETKEY`
- `PUSHPLUS_TOKEN`（可选）

工作流：`.github/workflows/dns_pod.yml`

## 接口示例

```bash
curl -fsSL https://kityyj.github.io/cf-speed-dns/ipTop.html
```

返回格式：

```text
104.18.40.65,172.64.229.128,162.159.45.250
```

## GitHub Pages

仓库 Pages 发布源保持为 `main` 分支根目录即可。项目使用纯静态 HTML，不依赖 Jekyll。

如果以后需要绑定自己的域名，请只绑定你自己控制的域名，不要再使用上游项目的 `ip.164746.xyz`。
