/* 录制桌宠演示 GIF：CDP 驱动 Edge headless，逐帧截图
 * 用法: node tools/record_gif.js
 * 输出: _gif_frames/f000.png ...
 */
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const PORT = 9223;
const ROOT = 'C:/Users/XIAOMI/WorkBuddy/2026-10-18-14-45-54';
const HTML = 'file:///' + ROOT + '/pet-assets/pet-demo-skins.html';
const OUT = ROOT + '/_gif_frames';
const W = 640, H = 700, FPS = 10, DUR = 10;

const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  fs.rmSync(OUT, { recursive: true, force: true });
  fs.mkdirSync(OUT, { recursive: true });

  const edge = spawn(EDGE, [
    '--headless=new', '--disable-gpu', '--no-first-run', '--hide-scrollbars',
    '--disable-background-timer-throttling', '--disable-renderer-backgrounding',
    `--remote-debugging-port=${PORT}`,
    '--user-data-dir=' + ROOT + '/_edgeprofile',
    `--window-size=${W},${H}`, HTML
  ], { stdio: 'ignore' });

  let page = null;
  for (let i = 0; i < 60 && !page; i++) {
    await sleep(300);
    try {
      const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
      page = l.find(t => t.type === 'page' && t.webSocketDebuggerUrl);
    } catch (e) { /* port not ready */ }
  }
  if (!page) { console.error('CDP not ready'); edge.kill(); process.exit(1); }

  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });

  let id = 0; const pend = new Map();
  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
  };
  const send = (method, params = {}) => new Promise(res => {
    const i = ++id; pend.set(i, res);
    ws.send(JSON.stringify({ id: i, method, params }));
  });

  await send('Page.enable');
  await send('Runtime.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 1, mobile: false });
  await sleep(2200); // 等图片资源与首帧动画就绪

  // 隐藏顶部提示条，画面更干净
  await send('Runtime.evaluate', { expression: "document.getElementById('hint').style.display='none'" });

  const cx = await send('Runtime.evaluate', {
    expression: "JSON.stringify((()=>{const b=document.getElementById('pet').getBoundingClientRect();return{x:Math.round(b.x+b.width/2),y:Math.round(b.y+b.height/2)}})())",
    returnByValue: true
  });
  const P = JSON.parse(cx.result.result.value);
  console.log('pet center:', P);

  const mouse = (type, x, y) => send('Input.dispatchMouseEvent', {
    type, x: Math.round(x), y: Math.round(y), button: 'left',
    buttons: type === 'mouseReleased' ? 0 : 1,
    clickCount: type === 'mouseMoved' ? 0 : 1
  });
  const ev = expr => send('Runtime.evaluate', { expression: expr });

  // ---- 时间轴（秒）----
  const T = [];
  // poke：单击角色
  T.push({ t: 2.0, fn: async () => {
    await mouse('mousePressed', P.x, P.y); await sleep(90);
    await mouse('mouseReleased', P.x, P.y);
  }});
  // 拖拽：按住向上提起，再松手坠落（落差更大）
  const dx = 150, dy = -230, steps = 16;
  T.push({ t: 3.6, fn: () => mouse('mousePressed', P.x, P.y) });
  for (let i = 1; i <= steps; i++) {
    const t = 3.6 + 1.9 * i / steps;
    T.push({ t, fn: () => mouse('mouseMoved', P.x + dx * i / steps, P.y + dy * i / steps) });
  }
  T.push({ t: 5.6, fn: () => mouse('mouseReleased', P.x + dx, P.y + dy) }); // 松手坠落
  // 换肤：蓝贝雷帽 → 一公火焰
  T.push({ t: 7.2, fn: () => ev('applySkin(SKINS[1])') });
  T.push({ t: 8.6, fn: () => ev('applySkin(SKINS[10])') });

  let ei = 0;
  const t0 = Date.now();
  let f = 0;
  while (true) {
    const t = (Date.now() - t0) / 1000;
    while (ei < T.length && T[ei].t <= t) {
      try { await T[ei].fn(); } catch (e) { console.error('event err:', e.message); }
      ei++;
    }
    const r = await send('Page.captureScreenshot', { format: 'jpeg', quality: 85 });
    if (r.result && r.result.data) {
      fs.writeFileSync(path.join(OUT, 'f' + String(f).padStart(3, '0') + '.jpg'),
        Buffer.from(r.result.data, 'base64'));
      f++;
    }
    if (t >= DUR) break;
    await sleep(1000 / FPS);
  }

  ws.close();
  edge.kill();
  console.log('frames:', f);
  process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
