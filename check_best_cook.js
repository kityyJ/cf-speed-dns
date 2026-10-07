const fs = require('node:fs');
const https = require('node:https');

const zoneId = process.env.CF_ZONE_ID;
const token = process.env.CF_API_TOKEN;
const bestName = 'best.jia.nz';
const cookName = 'cook.jia.nz';

if (!zoneId || !token) {
  console.error('Missing CF_ZONE_ID or CF_API_TOKEN');
  process.exit(1);
}

async function dnsRecords(name) {
  const url = `https://api.cloudflare.com/client/v4/zones/${zoneId}/dns_records?name=${encodeURIComponent(name)}&per_page=100`;
  const response = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  const body = await response.json();
  if (!response.ok || !body.success) throw new Error(`Cloudflare DNS read failed for ${name}`);
  return body.result.filter(record => record.name === name);
}

function probe(ip) {
  return new Promise(resolve => {
    const started = performance.now();
    let body = '';
    const request = https.get(`https://${cookName}/`, {
      agent: false,
      lookup: (_host, options, callback) => options.all
        ? callback(null, [{ address: ip, family: 4 }])
        : callback(null, ip, 4),
      timeout: 8000,
    }, response => {
      response.setEncoding('utf8');
      response.on('data', chunk => { if (body.length < 32768) body += chunk; });
      response.on('end', () => resolve({
        ok: response.statusCode === 200 && body.includes('<title>自助上传'),
        status: response.statusCode,
        ms: Math.round(performance.now() - started),
        colo: (response.headers['cf-ray'] || '').split('-').pop(),
      }));
    });
    request.on('timeout', () => request.destroy(new Error('timeout')));
    request.on('error', error => resolve({ ok: false, error: error.code || error.message }));
  });
}

async function main() {
  const [bestRecords, cookRecords] = await Promise.all([
    dnsRecords(bestName),
    dnsRecords(cookName),
  ]);
  if (cookRecords.length !== 1 || cookRecords[0].type !== 'CNAME' ||
      cookRecords[0].proxied || cookRecords[0].content.replace(/\.$/, '') !== bestName) {
    throw new Error('Cook DNS no longer points to the expected DNS-only best.jia.nz CNAME');
  }
  const ips = bestRecords.filter(record => record.type === 'A' && !record.proxied)
    .map(record => record.content);
  if (ips.length < 2 || ips.length !== bestRecords.length) {
    throw new Error('best.jia.nz must have at least two DNS-only A records and no other records');
  }

  const pool = new Set(JSON.parse(fs.readFileSync('api/all.json', 'utf8')).items.map(item => item.ip));
  const results = await Promise.all(ips.map(async ip => {
    const attempts = [];
    for (let i = 0; i < 3; i++) attempts.push(await probe(ip));
    return { ip, in_pool: pool.has(ip), healthy: attempts.every(item => item.ok), attempts };
  }));
  console.log(JSON.stringify({ checked_at: new Date().toISOString(), source: 'GitHub Actions runner', results }, null, 2));
  if (results.some(item => !item.healthy)) process.exitCode = 1;
}

main().catch(error => { console.error(error.message); process.exitCode = 1; });
