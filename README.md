# Cloudflare IP 优选

自动聚合 Cloudflare IPv4 优选候选，支持中国电信、联通、移动分类展示、API 接口与 DNS 自动维护。

[在线预览](https://kityyj.github.io/cook-speed-dns/) · [IP 数据](https://kityyj.github.io/cook-speed-dns/api/all.json)

## 功能

- 多来源聚合、官方 IP 网段校验、去重
- GitHub Actions 定时更新（约每 30 分钟）
- TXT / JSON API、DNS 只读查询
- 网站 HTTPS 可用性检查与浏览器网络检测

## API

`/api/ct.txt` · `/api/cu.txt` · `/api/cmcc.txt` · `/api/all.txt`

JSON 接口：`/api/{ct|cu|cmcc|all}.json`

## 本地运行

```bash
pip install -r requirements.txt
python aggregate_ips.py
```

> 数据来自第三方公开来源，不代表中国大陆三网实时测速；启用 DNS 自动维护需自行配置 Cloudflare 授权。

## 自主扫描（实验）

从 [Cloudflare 官方网段](https://www.cloudflare.com/ips-v4) 自行抽样，使用 TLS/SNI 和真实 HTTPS 请求检测网站兼容性及响应时间；每日自动执行，输出 `api/self_scan.json` 和 `api/self_scan.txt`。

**注意：** 当前检测来自 GitHub 托管 Runner（非中国大陆三网）。在配齐电信、联通、移动各自的测速节点之前，自主结果**不会自动覆盖正在运行的 DNS**；现有第三方数据聚合暂时保留。
