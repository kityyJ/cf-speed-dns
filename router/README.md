# 华硕原厂固件自主优选 IP

适用于 ARMv7、BusyBox、curl。只使用 Cloudflare 官方 IPv4 网段，自主测量 HTTPS TCP、TLS、TTFB；不依赖第三方优选 IP，不需要 GitHub Token，不写入 DNS。

## 路由器 SSH 首次试运行

在 SSH 终端执行以下命令，将域名替换为自己的 HTTPS 网站：

    mkdir -p /jffs/cf-selfscan
    curl -q -fLsS --connect-timeout 8 --max-time 35 \
      https://raw.githubusercontent.com/kityyJ/cook-speed-dns/main/router/asuswrt-unicom.sh \
      -o /jffs/cf-selfscan/scan.sh
    chmod 700 /jffs/cf-selfscan/scan.sh
    sh -n /jffs/cf-selfscan/scan.sh

    HOST_A=www.example.com HOST_B=example.com \
      PER_PREFIX=2 LIMIT=10 MIN_PASS=1 \
      /bin/sh /jffs/cf-selfscan/scan.sh

    cat /jffs/cf-selfscan/self_scan_cu.txt
    cat /jffs/cf-selfscan/self_scan_cu.json

## 配置

- HOST_A 必填、HOST_B 可选；均为有效 HTTPS 主机名，需要实际支持待测 Cloudflare IP 的 TLS SNI 和 HTTP 2xx。
- PER_PREFIX 每个官方网段抽样数（1-32，默认 8）。首次推荐 2。
- LIMIT 最多输出几个合格地址（默认 30）；不足不虚构；MIN_PASS 决定未达到几条通过时保留旧结果（默认 1）。
- CONNECT_TIMEOUT 默认 3 秒，MAX_TIME 单次 HTTPS 最大 7 秒。
- OUT_DIR 默认 /jffs/cf-selfscan，输出 self_scan_cu.json 和 self_scan_cu.txt。

本地实测只代表当前路由器的实际网络出口；中国联通标识由用户配置，不能代表中国所有地区的联通。curl --noproxy 禁止应用层代理，但若使用 VPN 或策略路由，仍需确认实际出口。

## 持久化与发布

华硕原厂固件虽然存在 crond，不代表自行添加的 cron 任务在重启后仍会自动恢复。当前版本仅提供安全的手动测速，不尝试修改原厂计划任务或 NVRAM。后续在明确固件自启方式后再启用每 6 小时扫描和安全上报 GitHub。
