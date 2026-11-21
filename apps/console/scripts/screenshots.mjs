/* global console, document, process, URL, window */
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright";

const WIDTH = 1440;
const HEIGHT = 900;
const MIN_NODES = 10;
const MARK = "\u00d72";

// A 4× replay keeps a node in "running" for about 60ms. Hold the next event
// until the screenshot is taken so that frame is still on screen.
const HOLD_SOURCE = `
(() => {
  const flag = "__governorHoldLive";
  const ready = "__governorLiveFrame";
  let current = window.EventSource;
  const wrap = (Native) => {
    function Held(url, init) {
      const inner = new Native(url, init);
      if (!globalThis[flag]) return inner;
      const queue = [];
      const wrapped = new Map();
      let pumping = false;
      let held = false;
      const origAdd = inner.addEventListener.bind(inner);
      const origRemove = inner.removeEventListener.bind(inner);
      const marked = () => Array.from(document.querySelectorAll(".canvas-wrap .node-badge"))
        .some((el) => (el.textContent || "").includes(${JSON.stringify(MARK)}));
      const look = () => Boolean(document.querySelector(".canvas-wrap .node-running")) && marked();
      const pump = () => {
        if (pumping || held || queue.length === 0) return;
        pumping = true;
        const job = queue.shift();
        job();
        setTimeout(() => {
          requestAnimationFrame(() => {
            pumping = false;
            if (look()) {
              held = true;
              globalThis[ready] = true;
              return;
            }
            pump();
          });
        }, 0);
      };
      inner.addEventListener = (type, listener, options) => {
        const next = (event) => {
          queue.push(() => listener.call(inner, event));
          pump();
        };
        wrapped.set(listener, next);
        origAdd(type, next, options);
      };
      inner.removeEventListener = (type, listener, options) => {
        origRemove(type, wrapped.get(listener) || listener, options);
      };
      return inner;
    }
    return Held;
  };
  Object.defineProperty(window, "EventSource", {
    configurable: true,
    get() { return current; },
    set(next) { current = wrap(next); },
  });
})();
`;

function arg(flag) {
  const index = process.argv.indexOf(flag);
  const value = index === -1 ? "" : process.argv[index + 1] || "";
  if (!value || value.startsWith("--")) {
    console.error(`missing ${flag}`);
    process.exit(1);
  }
  return value;
}

function pageUrl(base, pathname) {
  return new URL(pathname, base.endsWith("/") ? base : `${base}/`).href;
}

function watch(page) {
  const errors = [];
  page.on("pageerror", (error) => {
    errors.push(String(error));
  });
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    const url = message.location().url || "";
    if (text.includes("favicon") || url.includes("favicon")) return;
    if (text.includes("ERR_ABORTED")) return;
    errors.push(text);
  });
  return errors;
}

async function assertHealthy(page, errors, canvas) {
  if (errors.length > 0) throw new Error(`console error: ${errors[0]}`);
  const box = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    width: window.innerWidth,
  }));
  if (box.scroll > box.width + 1) {
    throw new Error(`horizontal overflow ${box.scroll} > ${box.width}`);
  }
  if (!canvas) return;
  const nodes = await page.locator(".canvas-wrap .react-flow__node").count();
  if (nodes < MIN_NODES) throw new Error(`canvas nodes ${nodes}`);
}

async function save(page, file) {
  await page.screenshot({ path: file, type: "png" });
}

async function runsShot(page, base) {
  await page.goto(pageUrl(base, "/"), { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: "Runs" }).waitFor();
  await page.getByText("build-full").waitFor();
  await page.getByText("ask-repaired").waitFor();
}

async function liveShot(page, base) {
  const replay = page.waitForRequest((request) => {
    const url = request.url();
    return url.includes("/runs/build-full/events") && url.includes("replay=1") && url.includes("speed=4");
  });
  await page.goto(pageUrl(base, "/runs/build-full"), { waitUntil: "domcontentloaded" });
  await replay;
  await page.getByRole("button", { name: `4${MARK[0]}` }).waitFor();
  const speed = page.getByRole("button", { name: `4${MARK[0]}` });
  if ((await speed.getAttribute("aria-pressed")) !== "true") await speed.click();
  await page.waitForFunction(() => globalThis.__governorLiveFrame === true, null, { timeout: 20000 });
  const frame = await page.evaluate((mark) => {
    const running = Boolean(document.querySelector(".canvas-wrap .node-running"));
    const retry = Array.from(document.querySelectorAll(".canvas-wrap .node-badge"))
      .some((el) => (el.textContent || "").includes(mark));
    const nodes = document.querySelectorAll(".canvas-wrap .react-flow__node").length;
    return { running, retry, nodes };
  }, MARK);
  if (!frame.running || !frame.retry) {
    throw new Error(`live frame missing running=${frame.running} retry=${frame.retry} nodes=${frame.nodes}`);
  }
  await zoomRunning(page);
}

async function zoomRunning(page) {
  const zoomIn = page.locator(".canvas-wrap .react-flow__controls-zoomin");
  const canvas = page.locator(".canvas-wrap .canvas-stage");
  const node = page.locator(".canvas-wrap .node-running");
  await zoomIn.waitFor();
  await page.waitForTimeout(700);
  for (let step = 0; step < 14; step += 1) {
    const box = await node.boundingBox();
    if (box && box.width >= 180) break;
    await zoomIn.click();
  }
  const canvasBox = await canvas.boundingBox();
  const box = await node.boundingBox();
  if (!canvasBox || !box || box.width < 180) {
    throw new Error(`running node too small (${box ? Math.round(box.width) : 0})`);
  }
  const dx = canvasBox.x + canvasBox.width / 2 - (box.x + box.width / 2);
  const dy = canvasBox.y + canvasBox.height / 2 - (box.y + box.height / 2);
  if (Math.abs(dx) > 24 || Math.abs(dy) > 24) {
    const startX = canvasBox.x + canvasBox.width / 2;
    const startY = canvasBox.y + canvasBox.height - 36;
    await page.mouse.move(startX, startY);
    await page.mouse.down();
    await page.mouse.move(startX + dx, startY + dy, { steps: 12 });
    await page.mouse.up();
  }
  const badge = page.locator(".canvas-wrap .node-badge").filter({ hasText: MARK });
  const mark = await badge.boundingBox();
  const after = await canvas.boundingBox();
  const inside = mark && after
    && mark.x >= after.x + 4
    && mark.x + mark.width <= after.x + after.width - 4
    && mark.y >= after.y + 4
    && mark.y + mark.height <= after.y + after.height - 4;
  if (!inside) throw new Error("retry badge is outside the canvas");
}

async function toggleTheme(page) {
  await page.getByRole("button", { name: "Light theme" }).click();
  await page.waitForFunction(() => document.documentElement.dataset.theme === "light");
  await page.locator(".lineage-canvas .react-flow__node").first().waitFor();
  await page.getByRole("button", { name: "Dark theme" }).click();
  await page.waitForFunction(() => document.documentElement.dataset.theme === "dark");
}

async function lineageShot(page, base) {
  await page.goto(pageUrl(base, "/runs/build-full"), { waitUntil: "domcontentloaded" });
  await page.locator(".canvas-wrap .react-flow__node").nth(MIN_NODES - 1).waitFor();
  await page.getByRole("tab", { name: "Lineage" }).click();
  await page.locator(".lineage-canvas .react-flow__node").nth(9).waitFor();
  await toggleTheme(page);
  await page.locator(".lineage-canvas .react-flow__controls-fitview").click();
  await page.locator(".lineage-canvas").scrollIntoViewIfNeeded();
}

async function guardShot(page, base) {
  await page.goto(pageUrl(base, "/runs/ask-repaired"), { waitUntil: "domcontentloaded" });
  await page.locator(".canvas-wrap .react-flow__node").nth(MIN_NODES - 1).waitFor();
  await page.waitForFunction(() => {
    const steps = Array.from(document.querySelectorAll(".waterfall-step"));
    const repair = steps.some((el) => el.classList.contains("outcome-repair"));
    const answer = steps.find((el) => el.querySelector(".step-name")?.textContent === "Answer");
    return repair && answer != null && answer.classList.contains("outcome-pass");
  }, null, { timeout: 20000 });
  await page.locator(".waterfall").scrollIntoViewIfNeeded();
}

async function main() {
  const base = arg("--url");
  const out = path.resolve(arg("--out"));
  await mkdir(out, { recursive: true });
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: WIDTH, height: HEIGHT },
    deviceScaleFactor: 1,
  });
  await context.addInitScript(HOLD_SOURCE);
  const page = await context.newPage();
  const errors = watch(page);
  try {
    await runsShot(page, base);
    await assertHealthy(page, errors, false);
    await save(page, path.join(out, "console-runs.png"));
    errors.length = 0;

    const live = await context.newPage();
    await live.addInitScript(() => {
      globalThis.__governorHoldLive = true;
    });
    const liveErrors = watch(live);
    await liveShot(live, base);
    await assertHealthy(live, liveErrors, true);
    await save(live, path.join(out, "console-build-live.png"));
    await live.close();

    await lineageShot(page, base);
    await assertHealthy(page, errors, true);
    await save(page, path.join(out, "console-build-lineage.png"));
    errors.length = 0;

    await guardShot(page, base);
    await assertHealthy(page, errors, true);
    await save(page, path.join(out, "console-ask-guard.png"));
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});
