/* 无头验证：桌宠拖拽 / 点击 / 换皮肤 是否真的可用（捕捉运行时异常） */
const fs = require("fs");
const path = require("path");
const { JSDOM } = require("jsdom");

const HTML = path.resolve(__dirname, "..", "pet-demo-skins.html");
const html = fs.readFileSync(HTML, "utf8");

const errors = [];
const dom = new JSDOM(html, {
  runScripts: "dangerously",
  pretendToBeVisual: true,
  url: "http://localhost/",
  beforeParse(window) {
    window.Element.prototype.setPointerCapture = function () {};
    window.Element.prototype.releasePointerCapture = function () {};
    window.HTMLCanvasElement.prototype.getContext = () => null;
    window.addEventListener("error", e => errors.push("window.onerror: " + e.message));
    const origError = console.error;
    window.console.error = (...a) => { errors.push("console.error: " + a.join(" ")); origError(...a); };
  },
});

const { window } = dom;
const doc = window.document;
const pet = doc.getElementById("pet");

function pointer(type, x, y) {
  const ev = new window.MouseEvent(type, { clientX: x, clientY: y, bubbles: true, cancelable: true, button: 0 });
  ev.pointerId = 1;
  pet.dispatchEvent(ev);
}

const wait = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  await wait(80);
  const layers = pet.querySelectorAll("img").length;
  console.log("图层数:", layers);
  console.log("气泡存在:", !!doc.getElementById("bubble"), " Zzz 存在:", !!doc.getElementById("zzz"));

  const before = { left: pet.style.left, top: pet.style.top };
  pointer("pointerdown", 500, 400);
  await wait(20);
  pointer("pointermove", 520, 420);
  await wait(30);
  pointer("pointermove", 620, 480);
  await wait(120);
  const during = { left: pet.style.left, top: pet.style.top };
  pointer("pointerup", 620, 480);
  await wait(200);

  const movedLeft = parseFloat(during.left) - parseFloat(before.left);
  const movedTop = parseFloat(during.top) - parseFloat(before.top);
  console.log("拖拽位移 dx:", movedLeft.toFixed(1), "dy:", movedTop.toFixed(1));
  console.log("拖拽生效:", movedLeft > 20 && movedTop > 20 ? "YES" : "NO");
  console.log("落地后仍在视口内:", parseFloat(pet.style.top) < window.innerHeight);

  // 换皮肤（模拟点击皮肤柜里的第二张卡）
  const cards = doc.querySelectorAll(".skinCard");
  console.log("皮肤卡数量:", cards.length);
  if (cards[1]) {
    cards[1].dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    await wait(260);
    const roles = [...pet.querySelectorAll("img")].map(i => i.dataset.role);
    console.log("换皮后图层:", roles.join(","));
    console.log("换皮后皮肤名:", doc.getElementById("skinLabel").textContent);
    const sway = [...pet.querySelectorAll("img")].filter(i => i.dataset.sway).length;
    const head = [...pet.querySelectorAll("img")].filter(i => i.dataset.head).length;
    console.log("自摆层数:", sway, " 头部组层数:", head);
  }

  // 逐套切换，检查每套的图层/动画配置/提示文案
  const cardsAll = [...doc.querySelectorAll(".skinCard")];
  for (let i = 0; i < cardsAll.length; i++) {
    cardsAll[i].dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    await wait(200);
    const imgs = [...pet.querySelectorAll("img")];
    const sway = imgs.filter(x => x.dataset.sway).length;
    const head = imgs.filter(x => x.dataset.head).length;
    const breathe = imgs.filter(x => x.dataset.breathe).length;
    const label = doc.getElementById("skinLabel").textContent.replace("当前皮肤：", "");
    console.log(`${String(i + 1).padStart(2)}. ${label} | 层 ${imgs.length} 自摆 ${sway} 头组 ${head} 呼吸 ${breathe}`);
  }

  console.log("运行时错误:", errors.length ? errors : "无");
  dom.window.close();
})();
