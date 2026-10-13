#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import ipaddress
import json
import os
import re
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "sources.json"
API_DIR = ROOT / "api"
DATA_DIR = ROOT / "data"

IP_RE = re.compile(r"(?<![\d.])((?:\d{1,3}\.){3}\d{1,3})(?::(\d{1,5}))?(?![\d.])")

FALLBACK_CF_CIDRS = [
    "173.245.48.0/20",
    "103.21.244.0/22",
    "103.22.200.0/22",
    "103.31.4.0/22",
    "141.101.64.0/18",
    "108.162.192.0/18",
    "190.93.240.0/20",
    "188.114.96.0/20",
    "197.234.240.0/22",
    "198.41.128.0/17",
    "162.158.0.0/15",
    "104.16.0.0/13",
    "104.24.0.0/14",
    "172.64.0.0/13",
    "131.0.72.0/22",
]

INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
  <meta name="color-scheme" content="light dark">
  <meta name="description" content="Cloudflare 三网优选 IP 聚合池">
  <title>Cook优选 · 网络状态与 Cloudflare CDN 优选 IP</title>
  <style>
    :root {
      font-family: -apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",sans-serif;
      color-scheme: light dark;
      --bg:#f5f5f7;--card:rgba(255,255,255,.82);--text:#1d1d1f;--muted:#6e6e73;
      --line:rgba(0,0,0,.08);--accent:#0071e3;--good:#34c759;--warn:#ff9f0a;
      --shadow:0 12px 40px rgba(0,0,0,.06);
    }
    @media (prefers-color-scheme:dark) {
      :root {--bg:#000;--card:rgba(28,28,30,.86);--text:#f5f5f7;--muted:#a1a1a6;
        --line:rgba(255,255,255,.12);--accent:#2997ff;--shadow:0 12px 40px rgba(0,0,0,.28)}
    }
    *{box-sizing:border-box}html{-webkit-text-size-adjust:100%}body{margin:0;background:var(--bg);color:var(--text);min-height:100vh}
    button,a{font:inherit}.wrap{width:min(1080px,calc(100% - 28px));margin:auto;padding:42px 0 60px}
    h1{font-size:clamp(32px,5vw,52px);letter-spacing:-.045em;line-height:1.04;margin:0 0 10px}
    .lead{margin:0;color:var(--muted);line-height:1.65}.top{display:flex;justify-content:space-between;gap:18px;align-items:flex-end;margin-bottom:24px}
    .badge{display:inline-flex;align-items:center;gap:8px;padding:8px 11px;border:1px solid var(--line);border-radius:999px;background:var(--card);font-size:12px;color:var(--muted);white-space:nowrap}
    .dot{width:8px;height:8px;border-radius:50%;background:var(--good);box-shadow:0 0 0 4px rgba(52,199,89,.13)}
    .stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:20px 0}
    .card,.panel{background:var(--card);border:1px solid var(--line);border-radius:19px;box-shadow:var(--shadow);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px)}
    .card{padding:16px}.label{font-size:12px;color:var(--muted);margin-bottom:7px}.value{font-size:22px;font-weight:700;letter-spacing:-.02em}
    .tabs{display:flex;gap:8px;overflow:auto;padding-bottom:3px;margin:20px 0 12px}.tab{border:1px solid var(--line);background:var(--card);color:var(--text);border-radius:999px;padding:9px 14px;cursor:pointer;white-space:nowrap}
    .tab.active{background:var(--text);color:var(--bg);border-color:var(--text)}
    .panel{overflow:hidden}.panel-head{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:16px 18px;border-bottom:1px solid var(--line)}
    .actions{display:flex;gap:8px;flex-wrap:wrap}.btn{border:1px solid var(--line);background:transparent;color:var(--accent);padding:8px 11px;border-radius:10px;text-decoration:none;cursor:pointer;font-size:13px}
    .table-wrap{overflow:auto;max-height:620px}table{border-collapse:collapse;width:100%;min-width:680px}th,td{padding:13px 18px;border-bottom:1px solid var(--line);text-align:left;font-size:14px}
    th{position:sticky;top:0;background:var(--card);backdrop-filter:blur(20px);font-size:12px;color:var(--muted);z-index:1}
    tr:last-child td{border-bottom:0}code{font-family:"SFMono-Regular",Consolas,monospace;font-size:13px}.muted{color:var(--muted)}.copy{cursor:pointer;color:var(--accent)}
    .sources{margin-top:14px;padding:16px 18px}.sources summary{cursor:pointer;font-weight:650}.source-list{margin-top:12px;display:grid;gap:8px}
    .source{display:flex;justify-content:space-between;gap:16px;font-size:13px;padding:9px 0;border-bottom:1px solid var(--line)}.source:last-child{border:0}.ok{color:var(--good)}.bad{color:var(--warn)}
    footer{text-align:center;color:var(--muted);font-size:12px;margin-top:18px;line-height:1.6}
    @media(max-width:760px){.wrap{padding-top:28px}.top{align-items:flex-start;flex-direction:column}.stats{grid-template-columns:repeat(2,minmax(0,1fr))}.panel-head{align-items:flex-start;flex-direction:column}}

  .dns-panel,.top-panel{margin:16px 0}
  .dns-body{padding:16px 18px 18px}
  .dns-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
  .top-panel .dns-grid{padding:16px 18px}
  .ip-tile{min-width:0;padding:16px 15px;border:1px solid var(--line);border-radius:14px;background:var(--card)}
  .ip-label{font-size:12px;color:var(--muted);margin-bottom:9px}
  .ip-value{font-family:"SFMono-Regular",Consolas,monospace;font-size:clamp(16px,2vw,21px);font-weight:650;letter-spacing:-.04em;line-height:1.3;overflow-wrap:anywhere}
  .ip-detail,.dns-note{font-size:12px;color:var(--muted);line-height:1.65;overflow-wrap:anywhere}
  .ip-detail{margin-top:9px}
  .dns-note{margin-top:5px}
  .dns-meta{margin:0 0 13px}
  .dns-panel .btn:disabled{opacity:.45;cursor:not-allowed}
  @media(max-width:760px){.dns-grid{grid-template-columns:1fr}.ip-value{font-size:20px}.dns-body,.top-panel .dns-grid{padding:14px}.dns-panel .panel-head{flex-direction:column;align-items:flex-start}}
  
/* Orange network-dashboard styling, adapted for Cook and its existing IP tools. */
:root{color-scheme:light;--bg:#f8fafc;--card:#fff;--text:#202939;--muted:#798595;--line:#e3e8ee;--accent:#ff7d24;--good:#10b981;--warn:#ee9929;--shadow:0 2px 7px rgba(28,38,55,.075)}
html{scroll-behavior:smooth;min-width:320px}
html[data-theme=dark]{color-scheme:dark;--bg:#101720;--card:#1b2632;--text:#edf1f7;--muted:#a5afbe;--line:#344353;--accent:#ff9f58;--shadow:0 3px 14px rgba(0,0,0,.25)}
body{background:var(--bg);color:var(--text);font-size:14px;line-height:1.5}
#network,#latency,#pool,#dns-panel,#api,#sources-card{scroll-margin-top:78px}
.wrap{width:min(1260px,calc(100% - 40px));padding:28px 0 65px}
.site-header{position:sticky;top:0;z-index:55;background:var(--card);border-bottom:1px solid var(--line)}
.site-nav{max-width:1660px;margin:auto;padding:0 22px;min-height:55px;display:flex;align-items:center;gap:14px}
.site-brand{display:flex;align-items:center;gap:6px;white-space:nowrap;color:#fc7b21;text-decoration:none;font-size:18px;font-weight:820}
.site-cloud{font-size:25px;line-height:1}.brand-hint{border-left:1px solid var(--line);padding-left:13px;font-size:12px;color:var(--muted);font-weight:650;white-space:nowrap}
.site-links{display:flex;gap:8px;align-items:stretch;margin-left:auto}
.site-links a{display:block;white-space:nowrap;border-bottom:2px solid transparent;padding:16px 8px 13px;text-decoration:none;font-weight:650;font-size:13px;color:var(--muted)}
.site-links a:hover,.site-links .current{color:var(--accent)}.site-links .current{border-color:var(--accent)}
.theme-toggle{display:grid;place-items:center;flex:none;width:39px;height:39px;border:1px solid var(--line);border-radius:50%;background:var(--card);color:var(--accent);font-size:23px;cursor:pointer}
.promo{display:flex;align-items:center;gap:15px;border:1px solid #ff8f43;border-radius:15px;background:linear-gradient(100deg,rgba(255,128,35,.13),rgba(255,140,43,.045));padding:18px 23px;box-shadow:0 9px 23px rgba(246,135,40,.08)}
.promo-mark{display:grid;place-items:center;width:48px;height:48px;flex:none;background:rgba(255,144,43,.15);border:1px solid rgba(255,138,49,.35);border-radius:12px;font-size:24px}
.promo-copy{flex:1;min-width:0}.promo-copy b{display:block;color:var(--accent);font-size:18px}.promo-copy p{color:var(--muted);font-size:13px;margin:5px 0 0}
.promo-cta{display:block;flex:none;border-radius:50px;padding:12px 20px;color:#fff!important;text-decoration:none;font-weight:750;white-space:nowrap;background:linear-gradient(110deg,#ff7b25,#ff9e38);box-shadow:0 6px 15px rgba(243,123,30,.22)}
.net-panel{margin:48px 0 0;border-radius:16px;padding:24px 25px;box-shadow:var(--shadow);backdrop-filter:none}
.net-title{display:flex;justify-content:space-between;align-items:center;gap:10px}.net-title h1{font-size:21px;letter-spacing:-.025em;line-height:1.4;margin:0;display:flex;gap:7px;align-items:center}.net-title h1 span{font-size:21px}
.title-line{height:2px;background:var(--line);margin:14px 0 12px}.title-line span{display:block;width:65px;height:2px;background:var(--accent)}
.net-description{font-size:13px;color:var(--muted);margin:0 0 29px;line-height:1.75}
.mini-button{border:1px solid var(--line);background:var(--card);color:var(--accent);font-size:12px;padding:7px 10px;border-radius:9px;cursor:pointer}.mini-button:hover{border-color:var(--accent)}.mini-button:disabled{opacity:.5;cursor:wait}
.net-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:15px}
.net-stat{min-width:0;border:1px solid var(--line);border-radius:13px;padding:13px 14px 14px;background:var(--card);min-height:155px;overflow:hidden}
.stat-head{display:flex;align-items:center;gap:7px;border-bottom:1px solid var(--line);padding-bottom:12px;min-width:0}
.stat-head i{width:9px;height:9px;border-radius:50%;background:var(--good);flex:none}.stat-head b{font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.stat-head small{font-size:10px;color:var(--muted);white-space:nowrap}
.net-stat>strong{display:block;font-size:23px;font-weight:780;line-height:1.3;letter-spacing:-.035em;margin:14px 0 6px;overflow-wrap:anywhere}
.net-stat>p{font-size:12px;color:var(--muted);margin:0 0 5px;overflow-wrap:anywhere}.net-stat>small{font-size:11px;color:var(--muted)}
.ping-head{display:flex;justify-content:space-between;align-items:center;gap:10px;margin:20px 0 11px}.ping-head strong{font-size:14px}.ping-head small{font-size:11px;color:var(--muted)}
.ping-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:15px}
.ping-card{min-width:0;display:flex;gap:9px;align-items:center;padding:13px 12px;min-height:79px;border:1px solid var(--line);border-radius:13px;box-shadow:0 2px 2px rgba(26,38,55,.04);background:var(--card)}
.ping-icon{height:33px;width:33px;flex:none;border:1px solid var(--line);border-radius:9px;display:grid;place-items:center;font-weight:850;font-size:14px}.ping-blue{color:#297bff}.ping-pink{color:#ef70a6}.ping-green{color:#16b959}.ping-orange{color:#fa781a}.ping-dark{color:var(--text)}.ping-yellow{color:#e6b224}.ping-red{color:#f23232}
.ping-name{min-width:0;display:flex;flex-direction:column;font-size:13px;font-weight:750;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ping-name small{font-size:10px;color:var(--good);font-weight:500}
.ping-card:nth-child(n+5) .ping-name small{color:#459df1}
.ping-time{font-size:18px;margin-left:auto;white-space:nowrap;font-weight:850;font-style:italic;color:#fa891d;font-variant-numeric:tabular-nums}
.ping-time.pending{font-style:normal;font-size:11px;font-weight:650;color:var(--muted)}.ping-time.fail{font-size:11px;letter-spacing:0;font-weight:750;font-style:normal;color:#e73d53}
.ping-foot{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:12px 0 0;font-size:11px;line-height:1.6;color:var(--muted)}
.data-head{margin-top:42px;display:flex;align-items:center;justify-content:space-between;gap:16px}
.data-head h2{font-size:23px;margin:4px 0 2px}.data-head p{font-size:13px;margin:0;color:var(--muted)}.eyebrow{font-size:10px;letter-spacing:.15em;font-weight:850;color:var(--accent)}
.stats{margin:16px 0}.card,.panel{border-radius:14px;background:var(--card);backdrop-filter:none}.card .value{font-size:27px}
.tab.active{background:var(--accent);border-color:var(--accent);color:#fff}.tab:hover,.btn:hover{border-color:var(--accent)}.copy,.btn{color:var(--accent)}
.dns-panel,.top-panel{margin:17px 0}footer{padding-top:16px}
@media(max-width:1100px){.brand-hint{display:none}.site-links{gap:0}.site-links a{padding-left:6px;padding-right:6px}.net-stats,.ping-grid{gap:10px}.net-stat>strong{font-size:20px}.ping-name{font-size:12px}.ping-time{font-size:16px}}
@media(max-width:820px){.site-nav{padding:0 13px}.site-links a span{display:none}.net-stats,.ping-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.net-panel{margin-top:23px}.site-links a{font-size:16px}.data-head{align-items:flex-start}}
@media(max-width:580px){
.wrap{width:calc(100% - 24px);padding-top:16px}.site-nav{gap:8px;min-height:53px}.site-brand{font-size:15px}.site-cloud{font-size:20px}.site-links a{font-size:13px;padding-left:4px;padding-right:4px}.theme-toggle{width:34px;height:34px;font-size:18px}
.promo{padding:13px;gap:10px;flex-wrap:wrap}.promo-mark{height:41px;width:41px}.promo-copy{flex-basis:calc(100% - 54px)}.promo-copy b{font-size:15px}.promo-copy p{font-size:11px}.promo-cta{margin-left:51px;padding:8px 14px;font-size:12px}
.net-panel{padding:15px;margin-top:20px}.net-title h1{font-size:18px}.net-description{font-size:12px;margin-bottom:17px}
.net-stats,.ping-grid{gap:9px}.net-stat{min-height:133px;padding:11px 10px}.stat-head b{font-size:11px}.stat-head small{display:none}.net-stat>strong{font-size:17px}.net-stat>p{font-size:11px}.net-stat>small{font-size:10px}
.ping-card{gap:6px;padding:11px 8px;min-height:68px}.ping-icon{width:27px;height:27px;font-size:12px}.ping-name{font-size:11px}.ping-time{font-size:13px}.ping-time.fail{font-size:10px}.ping-head{align-items:flex-start}.ping-head small{font-size:10px}
.data-head{margin-top:30px;flex-direction:column}.stats{grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.card .value{font-size:22px}
}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}

  </style>
<link rel="stylesheet" href="./assets/network.css?v=2">
</head>
<body>
<header class="site-header">
  <div class="site-nav">
    <a class="site-brand" href="#/network"><span class="site-cloud">☁</span> Cook优选</a>
    <span class="brand-hint">Cloudflare CDN 节点优选</span>
    <nav class="site-links" aria-label="主导航">
      <a href="#/network" class="current">◉ <span>网络状态</span></a>
      <a href="#/ip">☆ <span>优选 IP</span></a>
      <a href="#/speed">⌁ <span>分流测试</span></a>
      <a href="#/api">⌘ <span>API</span></a>
      <a href="#/resources">▦ <span>更多资源</span></a>
    </nav>
    <button id="theme-toggle" class="theme-toggle" type="button" aria-label="切换深色模式"><span id="theme-icon">☾</span></button>
  </div>
</header>
<main class="wrap">
  <section class="promo">
    <span class="promo-mark">⚡</span>
    <div class="promo-copy"><b>在线优选 Cloudflare 节点</b><p>聚合中国电信、联通、移动三网优选 IP，自动更新 DNS，开放 TXT / JSON API。</p></div>
    <a class="promo-cta" href="#pool">查看优选 IP ↗</a>
  </section>
  <section class="panel net-panel" id="network">
    <div class="net-title"><h1><span>🌐</span> 当前网络信息</h1><button class="mini-button" type="button" id="network-recheck">↻ 重新检测</button></div>
    <div class="title-line"><span></span></div>
    <p class="net-description">分别从国内、国际及 Cloudflare 服务观察浏览器的网络出口，并检测常用网站的 HTTPS 图标资源加载时间。IP 默认脱敏；不同服务不一定走不同线路，测速不等于 TCP Ping，也不代表中国三网探针。</p>
    <div class="net-stats" id="network-routes">
      <article class="net-stat">
        <div class="stat-head"><i></i><b>国内网络检测</b><small>IPIP</small></div>
        <div class="stat-ip-row"><strong id="net-domestic" aria-live="polite">检测中…</strong><button class="ip-toggle" type="button" data-view-ip="domestic" hidden aria-label="显示国内出口完整IP">显示</button></div>
        <p id="net-domestic-region">正在请求国内 IP 服务</p>
        <small id="net-domestic-source">来源：myip.ipip.net（可能受 CORS 限制）</small>
      </article>
      <article class="net-stat">
        <div class="stat-head"><i></i><b>国外网络检测</b><small>ipwho.is</small></div>
        <div class="stat-ip-row"><strong id="net-foreign" aria-live="polite">检测中…</strong><button class="ip-toggle" type="button" data-view-ip="foreign" hidden aria-label="显示国外出口完整IP">显示</button></div>
        <p id="net-foreign-region">正在请求国际 IP 服务</p>
        <small id="net-foreign-source">来源：ipwho.is，显示该服务看到的出口</small>
      </article>
      <article class="net-stat">
        <div class="stat-head"><i></i><b>Cloudflare 接入</b><small>ProxyIPv4 / Colo</small></div>
        <div class="stat-ip-row"><strong id="net-cloudflare" aria-live="polite">检测中…</strong><button class="ip-toggle" type="button" data-view-ip="cloudflare" hidden aria-label="显示Cloudflare检测的完整IP">显示</button></div>
        <p id="net-cloudflare-region">正在检测 Cloudflare Edge</p>
        <small id="net-cloudflare-source">来源：speed.cloudflare.com/meta</small>
      </article>
      <article class="net-stat">
        <div class="stat-head"><i></i><b>墙外连通检测</b><small>Google</small></div>
        <div class="stat-ip-row"><strong id="net-google" aria-live="polite">检测中…</strong></div>
        <p id="net-google-region">正在加载 Google HTTPS 资源</p>
        <small id="net-google-source">仅测连通性；浏览器不能直接读取 Google 出口 IP</small>
      </article>
    </div>
    <div class="cdn-strip">
      <div class="cdn-strip-copy"><span class="cdn-pill">DNS Only</span><span><b>cdn.yigeyao.com</b><small>中国大陆三网优选 IP 池 · 只读 DNS 查询</small></span></div>
      <div class="cdn-strip-actions"><strong id="net-dns">正在查询…</strong><a href="#dns-panel">查看全部 IP ↗</a></div>
    </div>
    <div class="ping-head"><strong>常用站点连通性</strong><small>浏览器资源加载时间 · 不是 ICMP Ping</small></div>
    <div class="ping-grid" id="latency">
      <div class="ping-card"><span class="ping-icon ping-blue">♪</span><span class="ping-name">字节跳动<small>国内</small></span><b class="ping-time pending" id="ping-douyin">待检测</b></div>
      <div class="ping-card"><span class="ping-icon ping-pink">B</span><span class="ping-name">Bilibili<small>国内</small></span><b class="ping-time pending" id="ping-bilibili">待检测</b></div>
      <div class="ping-card"><span class="ping-icon ping-green">微</span><span class="ping-name">微信<small>国内</small></span><b class="ping-time pending" id="ping-wechat">待检测</b></div>
      <div class="ping-card"><span class="ping-icon ping-orange">淘</span><span class="ping-name">淘宝<small>国内</small></span><b class="ping-time pending" id="ping-taobao">待检测</b></div>
      <div class="ping-card"><span class="ping-icon ping-dark">G</span><span class="ping-name">GitHub<small>国际</small></span><b class="ping-time pending" id="ping-github">待检测</b></div>
      <div class="ping-card"><span class="ping-icon ping-yellow">JS</span><span class="ping-name">jsDelivr<small>国际</small></span><b class="ping-time pending" id="ping-jsdelivr">待检测</b></div>
      <div class="ping-card"><span class="ping-icon ping-orange">☁</span><span class="ping-name">Cloudflare<small>国际</small></span><b class="ping-time pending" id="ping-cloudflare">待检测</b></div>
      <div class="ping-card"><span class="ping-icon ping-red">▶</span><span class="ping-name">YouTube<small>国际</small></span><b class="ping-time pending" id="ping-youtube">待检测</b></div>
    </div>
    <div class="ping-foot"><span id="ping-status" role="status">正在检测公开图标资源，部分站点可能阻止访问。</span><button class="mini-button" id="ping-retry" type="button">↻ 重新测速</button></div>
    <p class="privacy-caption">检测由浏览器直接向第三方服务发起请求，服务提供方可能看到你的出口 IP；本站不保存检测数据。HTTPS 图标加载的耗时不能代表完整网站首屏速度。</p>
  </section>
  <details class="panel port-panel" id="ports">
    <summary><span class="ports-icon">⇄</span><span><b>Cloudflare 支持端口</b><small>官方标准 HTTP / HTTPS 代理端口（点击展开）</small></span><span class="port-caret" aria-hidden="true">⌄</span></summary>
    <div class="port-body">
      <div><b>HTTP</b><div class="port-chips"><code>80</code><code>8080</code><code>8880</code><code>2052</code><code>2082</code><code>2086</code><code>2095</code></div></div>
      <div><b>HTTPS</b><div class="port-chips"><code>443</code><code>2053</code><code>2083</code><code>2087</code><code>2096</code><code>8443</code></div></div>
      <p>这些是 Cloudflare 代理可支持的端口，<b>不意味着你的灰云 DNS 或源站已开放全部端口</b>。非标准端口的缓存支持也有限制。<a href="https://developers.cloudflare.com/fundamentals/reference/network-ports/" target="_blank" rel="noopener noreferrer">查看官方文档 ↗</a></p>
    </div>
  </details>
  <section class="data-head" id="pool">
    <div><span class="eyebrow">OPTIMIZED IP POOL</span><h2>三网优选 IP</h2><p>多来源数据自动聚合，并筛选网站 HTTPS 兼容的 CDN IP。</p></div>
    <div class="badge"><span class="dot"></span><span id="updated">读取状态…</span></div>
  </section>
  <section class="stats">
    <div class="card"><div class="label">中国电信 · Telecom</div><div class="value" id="count-ct">—</div></div>
    <div class="card"><div class="label">中国联通 · Unicom</div><div class="value" id="count-cu">—</div></div>
    <div class="card"><div class="label">中国移动 · Mobile</div><div class="value" id="count-cmcc">—</div></div>
    <div class="card"><div class="label">全部候选 · Total</div><div class="value" id="count-all">—</div></div>
  </section>

  <section class="panel dns-panel" id="dns-panel" aria-labelledby="dns-title">
    <div class="panel-head">
      <div>
        <strong id="dns-title">cdn.yigeyao.com · 当前 DNS 解析 IP</strong>
        <div class="dns-note">只读查询公网 A 记录，不修改 Cloudflare 后台 DNS。IP 使用固定排序；不同公共 DNS 的缓存可能存在差异。</div>
      </div>
      <div class="actions">
        <button class="btn" id="dns-refresh" type="button">重新查询（只读）</button>
        <button class="btn" id="dns-copy" type="button" disabled>复制全部 IP</button>
      </div>
    </div>
    <div class="dns-body">
      <div class="dns-meta dns-note" id="dns-meta" role="status">正在读取当前 DNS …</div>
      <div class="dns-grid" id="dns-grid"></div>
    </div>
  </section>

  <section class="panel top-panel" aria-labelledby="top-title">
    <div class="panel-head">
      <div>
        <strong id="top-title">三网优选候选 · 最新榜首</strong>
        <div class="dns-note">来自项目聚合池的各运营商首位候选；DNS 更新时还会检查 IP 连通性，最终结果以当前 DNS 解析为准。</div>
      </div>
    </div>
    <div class="dns-grid" id="top-grid"><div class="dns-note">正在读取电信、联通、移动优选列表 …</div></div>
  </section>

  <div class="tabs">
    <button class="tab active" data-group="all">全部</button>
    <button class="tab" data-group="ct">电信</button>
    <button class="tab" data-group="cu">联通</button>
    <button class="tab" data-group="cmcc">移动</button>
  </div>

  <section class="panel">
    <div class="panel-head">
      <div><strong id="group-title">全部优选</strong> <span class="muted" id="group-count"></span></div>
      <div class="actions">
        <a class="btn" id="txt-link" href="./api/all.txt">TXT API</a>
        <a class="btn" id="json-link" href="./api/all.json">JSON API</a>
        <button class="btn" id="copy-list">复制当前列表</button>
      </div>
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>#</th><th>IP</th><th>端口</th><th>来源</th><th>标签</th><th></th></tr></thead>
        <tbody id="rows"><tr><td colspan="6" class="muted">正在载入…</td></tr></tbody>
      </table>
    </div>
  </section>

  <details class="card sources" id="sources-card">
    <summary>数据源状态</summary>
    <div id="sources" class="source-list"></div>
  </details>

  <footer id="api">
    静态接口：<code>./api/ct.txt</code> · <code>./api/cu.txt</code> · <code>./api/cmcc.txt</code> · <code>./api/all.txt</code><br>
    部署到 Cloudflare Pages 后支持兼容接口：<code>/ct?ips=6</code>、<code>/cu?ips=6</code>、<code>/cmcc?ips=8</code>、<code>/all?ips=70</code>
  </footer>
</main>
<script>
const titles={all:"全部优选",ct:"中国电信",cu:"中国联通",cmcc:"中国移动"};

let current="all", currentItems=[];
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
async function loadStatus(){
  try{
    const s=await fetch("./data/status.json",{cache:"no-store"}).then(r=>r.json());
    document.querySelector("#updated").textContent="更新："+s.generated_at;
    for(const g of ["ct","cu","cmcc","all"]) document.querySelector("#count-"+g).textContent=s.counts?.[g]??0;
    document.querySelector("#sources").innerHTML=(s.sources||[]).map(x=>`<div class="source"><span>${esc(x.group_title)} · ${esc(x.name)}</span><span class="${x.ok?"ok":"bad"}">${x.ok?("成功 "+x.count+" 条"):("失败")}</span></div>`).join("")||'<div class="muted">暂无状态</div>';
  }catch(e){document.querySelector("#updated").textContent="状态读取失败"}
}
async function loadGroup(group){
  current=group;
  document.querySelectorAll(".tab").forEach(x=>x.classList.toggle("active",x.dataset.group===group));
  document.querySelector("#group-title").textContent=titles[group];
  document.querySelector("#txt-link").href=`./api/${group}.txt`;
  document.querySelector("#json-link").href=`./api/${group}.json`;
  document.querySelector("#rows").innerHTML='<tr><td colspan="6" class="muted">正在载入…</td></tr>';
  try{
    const d=await fetch(`./api/${group}.json`,{cache:"no-store"}).then(r=>r.json());
    currentItems=d.items||[];
    document.querySelector("#group-count").textContent=`· ${currentItems.length} 条`;
    document.querySelector("#rows").innerHTML=currentItems.map((x,i)=>`<tr>
      <td class="muted">${i+1}</td><td><code>${esc(x.ip)}</code></td><td>${esc(x.port)}</td>
      <td>${esc(x.source)}</td><td class="muted">${esc(x.tag)}</td>
      <td class="copy" data-copy="${esc(x.ip)}:${esc(x.port)}">复制</td></tr>`).join("")||'<tr><td colspan="6" class="muted">暂无可用 IP</td></tr>';
  }catch(e){currentItems=[];document.querySelector("#rows").innerHTML='<tr><td colspan="6" class="muted">读取失败</td></tr>'}
}
document.querySelectorAll(".tab").forEach(x=>x.onclick=()=>loadGroup(x.dataset.group));
document.querySelector("#rows").onclick=e=>{const v=e.target.dataset.copy;if(v)navigator.clipboard.writeText(v)};
document.querySelector("#copy-list").onclick=()=>navigator.clipboard.writeText(currentItems.map(x=>`${x.ip}:${x.port}#${x.tag}`).join("\n"));

const dnsHostname="cdn.yigeyao.com";
let activeDnsIps=[];

function compareIpv4(a,b){
  const x=a.split(".").map(Number), y=b.split(".").map(Number);
  for(let i=0;i<4;i++) if(x[i]!==y[i]) return x[i]-y[i];
  return 0;
}

function looksLikeIpv4(ip) {
  if(typeof ip!=="string") return false;
  const parts=ip.split(".");
  return parts.length===4 && parts.every(p=>/^\d{1,3}$/.test(p) && Number(p)>=0 && Number(p)<=255);
}

function renderIpTiles(target,items){
  target.innerHTML=items.map(item=>'<div class="ip-tile">'
    +'<div class="ip-label">'+esc(item.label)+'</div>'
    +'<div class="ip-value">'+esc(item.ip)+'</div>'
    +'<div class="ip-detail">'+esc(item.detail||"")+'</div>'
    +'</div>').join("");
}

async function refreshDns(){
  const meta=document.querySelector("#dns-meta");
  const grid=document.querySelector("#dns-grid");
  const refresh=document.querySelector("#dns-refresh");
  const copy=document.querySelector("#dns-copy");
  refresh.disabled=true;
  copy.disabled=true;
  meta.textContent="正在查询公网 DNS …";
  const providers=[
    {name:"Cloudflare 1.1.1.1",url:"https://cloudflare-dns.com/dns-query?name="+encodeURIComponent(dnsHostname)+"&type=A",headers:{"Accept":"application/dns-json"}},
    {name:"Google Public DNS",url:"https://dns.google/resolve?name="+encodeURIComponent(dnsHostname)+"&type=A",headers:{}}
  ];
  try{
    for(const provider of providers){
      const controller=new AbortController();
      const timer=setTimeout(()=>controller.abort(),8000);
      try{
        const response=await fetch(provider.url,{headers:provider.headers,cache:"no-store",signal:controller.signal});
        if(!response.ok) throw new Error("HTTP "+response.status);
        const result=await response.json();
        if(result.Status!==0) throw new Error("DNS Status "+result.Status);
        const addresses=[...new Set((result.Answer||[]).filter(a=>a.type===1 && looksLikeIpv4(a.data)).map(a=>a.data))].sort(compareIpv4);
        if(!addresses.length) throw new Error("No A records");
        const lastIps=activeDnsIps;
        const additions=addresses.filter(ip=>!lastIps.includes(ip));
        const removals=lastIps.filter(ip=>!addresses.includes(ip));
        activeDnsIps=addresses;
        document.getElementById("net-dns").textContent=addresses.length+" 条 A 记录";
        renderIpTiles(grid,addresses.map((ip,i)=>({label:"当前 A 记录 "+(i+1),ip,detail:"DNS Only / 443 候选入口"})));
        const changeNote=!lastIps.length
          ?"首次查询"
          :additions.length||removals.length
            ?"与上次查询不同（新增 "+additions.length+"、减少 "+removals.length+"；可能是后台自动更新或 DNS 缓存差异）"
            :"IP 集合未变化";
        meta.textContent="查询来源："+provider.name+" · "+new Date().toLocaleString("zh-CN",{hour12:false})+" · 共 "+addresses.length+" 条 A 记录 · 只读查询 · "+changeNote;
        copy.disabled=false;
        return;
      }catch(error){
        // Some networks block individual DNS-over-HTTPS providers. Try the next one.
      }finally{
        clearTimeout(timer);
      }
    }
    activeDnsIps=[];
    document.getElementById("net-dns").textContent="查询失败";
    grid.innerHTML='<div class="dns-note">无法取得公网 DNS 结果。可能是当前网络阻止了 DNS-over-HTTPS 请求，可稍后点「重新查询」重试。</div>';
    meta.textContent="DNS 查询暂不可用，下面仍可查看最新聚合优选 IP。";
  }finally{
    refresh.disabled=false;
  }
}

async function loadCarrierLeaders(){
  const groups=[["ct","中国电信"],["cu","中国联通"],["cmcc","中国移动"]];
  const cards=await Promise.all(groups.map(async pair=>{
    try{
      const response=await fetch("./api/"+pair[0]+".json",{cache:"no-store"});
      if(!response.ok) throw new Error("HTTP "+response.status);
      const data=await response.json();
      const item=(data.items||[]).find(x=>looksLikeIpv4(x.ip));
      return {label:pair[1],ip:item?item.ip:"暂无可用候选",detail:item?("来源："+(item.source||"未知")):"数据尚未生成或无有效 IP"};
    }catch(error){
      return {label:pair[1],ip:"读取失败",detail:"暂时无法加载该运营商的 IP 池"};
    }
  }));
  renderIpTiles(document.querySelector("#top-grid"),cards);
}

document.querySelector("#dns-refresh").addEventListener("click",refreshDns);
document.querySelector("#dns-copy").addEventListener("click",async ()=>{
  if(!activeDnsIps.length) return;
  try{
    await navigator.clipboard.writeText(activeDnsIps.join(String.fromCharCode(10)));
    document.querySelector("#dns-copy").textContent="已复制";
    setTimeout(()=>document.querySelector("#dns-copy").textContent="复制全部 IP",1800);
  }catch(error){
    document.querySelector("#dns-meta").textContent="复制失败，请手动选中 IP 复制。";
  }
});
refreshDns();
loadCarrierLeaders();
setInterval(refreshDns,300000);

loadStatus();loadGroup("all");
</script>
<script defer src="./assets/network.js?v=2"></script>
</body>
</html>
"""


def load_config():
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def utc_now():
    return time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())


def fetch_cf_networks(session, timeout):
    try:
        response = session.get("https://www.cloudflare.com/ips-v4", timeout=timeout)
        response.raise_for_status()
        cidrs = [line.strip() for line in response.text.splitlines() if line.strip()]
        networks = [ipaddress.ip_network(cidr) for cidr in cidrs]
        if networks:
            return networks, "live"
    except Exception as exc:
        print(f"Cloudflare IPv4 range fetch failed, using fallback: {exc}")

    return [ipaddress.ip_network(cidr) for cidr in FALLBACK_CF_CIDRS], "fallback"


def is_cf_ip(ip, networks):
    address = ipaddress.ip_address(ip)
    return any(address in network for network in networks)


def extract_entries(text, source_name, default_port, cf_networks, cloudflare_only):
    entries = []
    seen = set()

    for raw_line in text.splitlines() or [text]:
        line = raw_line.strip()
        if not line or line.startswith("//"):
            continue

        tag = ""
        if "#" in line:
            tag = line.split("#", 1)[1].strip()

        for match in IP_RE.finditer(line):
            ip = match.group(1)
            port_raw = match.group(2)

            try:
                addr = ipaddress.ip_address(ip)
            except ValueError:
                continue

            if addr.version != 4 or not addr.is_global:
                continue

            if cloudflare_only and not is_cf_ip(ip, cf_networks):
                continue

            port = int(port_raw) if port_raw else default_port
            if not 1 <= port <= 65535:
                port = default_port

            key = (ip, port)
            if key in seen:
                continue
            seen.add(key)

            entries.append({
                "ip": ip,
                "port": port,
                "tag": tag or source_name,
                "source": source_name,
            })

    return entries


def classify_carrier(item):
    """根据来源标签把全量池结果补充回三网分类。"""
    text = f"{item.get('tag', '')} {item.get('source', '')}".upper()

    if "电信" in text or "CTCC" in text or re.search(r"\bCT\b", text):
        return "ct"
    if "联通" in text or "CUCC" in text or "UNICOM" in text or re.search(r"\bCU\b", text):
        return "cu"
    if "移动" in text or "CMCC" in text or "MOBILE" in text:
        return "cmcc"
    return None


def has_slow_reported_speed(item):
    match = re.search(r"(\d+(?:\.\d+)?)\s*mb/s\b", item.get("tag", ""), re.IGNORECASE)
    return bool(match and float(match.group(1)) < 1.0)


def round_robin_merge(pools, limit):
    merged = []
    seen = set()
    indexes = [0] * len(pools)

    while len(merged) < limit:
        progressed = False
        for pool_index, pool in enumerate(pools):
            while indexes[pool_index] < len(pool):
                item = pool[indexes[pool_index]]
                indexes[pool_index] += 1
                key = (item["ip"], item["port"])
                if key in seen:
                    continue
                seen.add(key)
                merged.append(item)
                progressed = True
                break

            if len(merged) >= limit:
                break

        if not progressed:
            break

    return merged


def load_previous(group):
    path = API_DIR / f"{group}.json"
    if not path.exists():
        return []

    try:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload.get("items", [])
    except Exception:
        return []


def fetch_source(session, source, group_key, group_title, settings, cf_networks):
    timeout = settings.get("timeout_seconds", 20)
    default_port = int(settings.get("default_port", 443))
    cloudflare_only = bool(settings.get("cloudflare_only", True))

    result = {
        "group": group_key,
        "group_title": group_title,
        "name": source["name"],
        "url": source["url"],
        "ok": False,
        "count": 0,
        "error": "",
    }

    try:
        response = session.get(source["url"], timeout=timeout)
        response.raise_for_status()
        items = extract_entries(
            response.text,
            source["name"],
            default_port,
            cf_networks,
            cloudflare_only,
        )
        result["ok"] = True
        result["count"] = len(items)
        return items, result
    except Exception as exc:
        result["error"] = str(exc)[:180]
        print(f"[{group_key}] {source['name']} failed: {exc}")
        return [], result


def write_outputs(results, status):
    API_DIR.mkdir(exist_ok=True)
    DATA_DIR.mkdir(exist_ok=True)

    generated_at = status["generated_at"]

    for group, items in results.items():
        payload = {
            "generated_at": generated_at,
            "group": group,
            "count": len(items),
            "items": items,
        }

        with (API_DIR / f"{group}.json").open("w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")

        with (API_DIR / f"{group}.txt").open("w", encoding="utf-8", newline="\n") as f:
            for item in items:
                f.write(f"{item['ip']}:{item['port']}#{item['tag']}\n")

        pure_ips = []
        seen_ips = set()
        for item in items:
            if item["ip"] not in seen_ips:
                pure_ips.append(item["ip"])
                seen_ips.add(item["ip"])

        with (API_DIR / f"{group}-ips.txt").open("w", encoding="utf-8", newline="\n") as f:
            f.write(",".join(pure_ips) + "\n")

    with (DATA_DIR / "status.json").open("w", encoding="utf-8", newline="\n") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)
        f.write("\n")

    legacy = []
    seen_legacy = set()
    for item in results["all"]:
        if item["ip"] not in seen_legacy:
            legacy.append(item["ip"])
            seen_legacy.add(item["ip"])
        if len(legacy) >= 50:
            break

    (ROOT / "ipTop.html").write_text(",".join(legacy) + "\n", encoding="utf-8")
    (ROOT / "ipTop10.html").write_text(",".join(legacy[:10]) + "\n", encoding="utf-8")
    (ROOT / "index.html").write_text(INDEX_HTML, encoding="utf-8")


def main():
    config = load_config()
    settings = config.get("settings", {})
    groups = config.get("groups", {})
    limits = settings.get("max_per_group", {})

    session = requests.Session()
    session.headers.update({
        "User-Agent": "cook-speed-dns/2.0 (+https://github.com/kityyJ/cook-speed-dns)",
        "Accept": "text/plain,application/json;q=0.9,*/*;q=0.8",
    })

    cf_networks, cf_range_source = fetch_cf_networks(
        session,
        settings.get("timeout_seconds", 20),
    )

    results = {}
    source_status = []

    # Carrier pools first.
    for group_key in ("ct", "cu", "cmcc"):
        group = groups[group_key]
        pools = []

        for source in group.get("sources", []):
            items, state = fetch_source(
                session,
                source,
                group_key,
                group["title"],
                settings,
                cf_networks,
            )
            pools.append(items)
            source_status.append(state)

        limit = int(limits.get(group_key, 120))
        merged = round_robin_merge(pools, limit)

        if not merged:
            merged = load_previous(group_key)
            print(f"[{group_key}] all sources failed; kept {len(merged)} previous item(s)")

        results[group_key] = merged

    # Global sources. If an entry carries an operator label, feed it back into
    # that carrier pool as a supplemental source. This mirrors the common
    # public BestCF/CFYes format where one list contains tagged CT/CU/CMCC rows.
    all_group = groups["all"]
    global_pools = []
    classified_pools = {"ct": [], "cu": [], "cmcc": []}

    for source in all_group.get("sources", []):
        items, state = fetch_source(
            session,
            source,
            "all",
            all_group["title"],
            settings,
            cf_networks,
        )
        global_pools.append(items)
        source_status.append(state)

        for item in items:
            carrier = classify_carrier(item)
            if carrier:
                classified_pools[carrier].append(item)

    for group_key in ("ct", "cu", "cmcc"):
        if classified_pools[group_key]:
            results[group_key] = round_robin_merge(
                [results[group_key], classified_pools[group_key]],
                int(limits.get(group_key, 120)),
            )

    all_pools = [results["ct"], results["cu"], results["cmcc"]] + global_pools
    results["all"] = round_robin_merge(all_pools, int(limits.get("all", 300)))
    if not results["all"]:
        results["all"] = load_previous("all")
        print(f"[all] all sources failed; kept {len(results['all'])} previous item(s)")

    quality_items = [item for item in results["all"] if not has_slow_reported_speed(item)]
    filtered_slow = len(results["all"]) - len(quality_items) if len(quality_items) >= 70 else 0
    if filtered_slow:
        results["all"] = quality_items
        print(f"[all] filtered {filtered_slow} IP(s) with reported speed below 1 MB/s")

    status = {
        "generated_at": utc_now(),
        "cloudflare_range_source": cf_range_source,
        "cloudflare_only": bool(settings.get("cloudflare_only", True)),
        "counts": {group: len(items) for group, items in results.items()},
        "healthy_sources": sum(1 for item in source_status if item["ok"]),
        "failed_sources": sum(1 for item in source_status if not item["ok"]),
        "filtered_slow": filtered_slow,
        "sources": source_status,
    }

    write_outputs(results, status)

    print(
        "Generated pools:",
        ", ".join(f"{name}={len(items)}" for name, items in results.items()),
    )


if __name__ == "__main__":
    main()
