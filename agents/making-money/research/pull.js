#!/usr/bin/env node
// Sequential transcript extractor via CDP — controls existing browser, reuses tab
const http = require('http');
const fs = require('fs');
const path = require('path');
const WebSocket = require('ws');

const TARGETS_FILE = process.argv[2] || 'research/queue.txt';
const OUT_DIR = process.argv[3] || 'research/raw';
const CDP_HOST = process.env.CDP_HOST || '127.0.0.1';
const CDP_PORT = parseInt(process.env.CDP_PORT || '18800', 10);

fs.mkdirSync(OUT_DIR, { recursive: true });

const targets = fs.readFileSync(TARGETS_FILE, 'utf8')
  .split('\n')
  .map(l => l.trim())
  .filter(l => l && !l.startsWith('#'))
  .map(l => {
    const [creator, vid, ...rest] = l.split('|');
    return { creator, vid, title: rest.join('|') };
  });

function httpJson(pathname) {
  return new Promise((resolve, reject) => {
    http.get({ host: CDP_HOST, port: CDP_PORT, path: pathname }, res => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => { try { resolve(JSON.parse(data)); } catch (e) { reject(e); } });
    }).on('error', reject);
  });
}

async function findOrOpenTab(targetUrl) {
  // find existing transcript.io tab if any
  const tabs = await httpJson('/json/list');
  let tab = tabs.find(t => t.type === 'page' && t.url && t.url.includes('youtube-transcript.io'));
  if (tab) return tab;
  // open new
  tab = await httpJson('/json/new?' + encodeURIComponent(targetUrl));
  return tab;
}

let msgId = 1;
function ws(url) {
  return new Promise((resolve, reject) => {
    const w = new WebSocket(url);
    const pending = new Map();
    w.on('open', () => resolve({
      send(method, params = {}) {
        const id = msgId++;
        return new Promise((res, rej) => {
          pending.set(id, { res, rej });
          w.send(JSON.stringify({ id, method, params }));
        });
      },
      close: () => w.close()
    }));
    w.on('message', d => {
      const m = JSON.parse(d);
      if (m.id && pending.has(m.id)) {
        const { res, rej } = pending.get(m.id);
        pending.delete(m.id);
        if (m.error) rej(new Error(m.error.message));
        else res(m.result);
      }
    });
    w.on('error', reject);
  });
}

async function evalInTab(conn, expression, awaitPromise = true) {
  const r = await conn.send('Runtime.evaluate', {
    expression,
    awaitPromise,
    returnByValue: true,
    timeout: 60000,
  });
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.text);
  return r.result.value;
}

async function navigate(conn, url) {
  await conn.send('Page.enable');
  await conn.send('Page.navigate', { url });
  // wait for load
  await new Promise(r => setTimeout(r, 4000));
}

async function pullTranscript(conn) {
  // Click login anonymously if present, wait, then scrape
  const script = `(async () => {
    const wait = ms => new Promise(r => setTimeout(r, ms));
    const btns = [...document.querySelectorAll('button')];
    const b = btns.find(x => /Login Anonymously/i.test(x.textContent || ''));
    if (b) b.click();
    await wait(10000);
    let t = document.body.innerText;
    let i = t.indexOf('00:00');
    if (i < 0) i = t.indexOf('Copy Transcript');
    const j = t.lastIndexOf('Word Count');
    if (i >= 0 && j > i) return t.slice(i, j);
    // possibly need another wait
    await wait(8000);
    t = document.body.innerText;
    i = t.indexOf('00:00');
    if (i < 0) i = t.indexOf('Copy Transcript');
    const j2 = t.lastIndexOf('Word Count');
    if (i >= 0 && j2 > i) return t.slice(i, j2);
    return 'FAIL_STATE:' + t.slice(0, 600);
  })()`;
  return await evalInTab(conn, script, true);
}

(async () => {
  console.log(`Extracting ${targets.length} transcripts`);
  for (const t of targets) {
    const outFile = path.join(OUT_DIR, `${t.creator}_${t.vid}.txt`);
    if (fs.existsSync(outFile) && fs.statSync(outFile).size > 1000) {
      console.log(`SKIP ${t.creator}/${t.vid} (exists)`);
      continue;
    }
    const url = `https://www.youtube-transcript.io/videos?id=${t.vid}`;
    try {
      const tab = await findOrOpenTab(url);
      const conn = await ws(tab.webSocketDebuggerUrl);
      await navigate(conn, url);
      const text = await pullTranscript(conn);
      fs.writeFileSync(outFile, `[${t.creator} - ${t.title} - id ${t.vid}]\n\n${text}\n`);
      const size = Buffer.byteLength(text);
      console.log(`OK ${t.creator}/${t.vid} (${size} bytes)`);
      conn.close();
      if (text.startsWith('FAIL_STATE')) {
        console.log(`  warn: fail state, may be credit-limited`);
      }
    } catch (e) {
      console.error(`ERR ${t.creator}/${t.vid}: ${e.message}`);
      fs.writeFileSync(outFile + '.err', e.message + '\n');
    }
    // throttle so site doesn't rate-limit and credits aren't burned for failed tries
    await new Promise(r => setTimeout(r, 5000));
  }
  console.log('DONE');
  process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
