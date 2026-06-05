// Extra captures: ISBN metadata auto-fill + QR label printing (Add Library Books page).
//   node capture_extra.js
// Outputs feature-metadata.webm + feature-qr-print.webm to ./_videos and qr-labels.png to ../assets.

const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BASE = process.env.BASE_URL || "http://localhost:8000";
const USER = "library-demo@example.com";
const PASS = "Capture@2026xyz";
const BRANCH = process.env.DEMO_BRANCH || "Demo Branch";
const ROOM = process.env.DEMO_ROOM || "DEMO-ROOM";
const SHELF = process.env.DEMO_SHELF || "DEMO-01";
const DEMO_ISBN = "9780743273565"; // The Great Gatsby — full metadata (title/author/publisher)

const ASSETS = path.resolve(__dirname, "../assets");
const VIDEOS = path.resolve(__dirname, "_videos");
const VIEWPORT = { width: 1320, height: 820 };
fs.mkdirSync(ASSETS, { recursive: true });
fs.mkdirSync(VIDEOS, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function dismissModals(page) {
  for (let i = 0; i < 4; i++) {
    if (await page.locator(".modal.show").count()) {
      await page.keyboard.press("Escape");
      await page.waitForTimeout(300);
    } else break;
  }
}

async function setLink(page, fieldname, value) {
  const wrap = `[data-fieldname="${fieldname}"]`;
  const input = page.locator(`${wrap} input`).first();
  await input.click();
  await input.fill(value);
  await page.waitForTimeout(1000);
  const item = page.locator(`${wrap} .awesomplete li`, { hasText: value }).first();
  if (await item.count()) await item.click();
  else await page.keyboard.press("Escape");
  await page.waitForTimeout(400);
  await dismissModals(page);
}

async function login(browser) {
  const ctx = await browser.newContext({ viewport: VIEWPORT });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
  await page.fill("#login_email", USER);
  await page.fill("#login_password", PASS);
  await page.click(".btn-login");
  await page.waitForURL(/\/app/, { timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(2000);
  const state = await ctx.storageState();
  await ctx.close();
  return state;
}

async function openAddBooks(page) {
  await page.goto(`${BASE}/app/add-library-books`, { waitUntil: "networkidle" });
  await page.waitForSelector("#intake-filters", { timeout: 20000 });
  await setLink(page, "branch", BRANCH);
  await setLink(page, "room", ROOM);
  await page.fill('[data-fieldname="book_shelf"] input', SHELF);
  await page.locator('[data-fieldname="book_shelf"] input').press("Enter");
  await page.waitForTimeout(400);
  await dismissModals(page);
}

async function record(browser, state, name, fn) {
  const ctx = await browser.newContext({ viewport: VIEWPORT, storageState: state, recordVideo: { dir: VIDEOS, size: VIEWPORT } });
  const page = await ctx.newPage();
  try {
    await fn(page);
  } catch (e) {
    console.log(`  ! ${name}: ${e.message.split("\n")[0]}`);
  }
  await page.waitForTimeout(400);
  const video = page.video();
  await ctx.close();
  if (video) {
    const src = await video.path();
    const dst = path.join(VIDEOS, `${name}.webm`);
    try { fs.renameSync(src, dst); } catch { fs.copyFileSync(src, dst); }
    console.log(`rec : ${name}.webm`);
  }
}

const recMetadata = async (page) => {
  await openAddBooks(page);
  await page.click("#add-row");
  await sleep(900);
  const isbn = page.locator(".isbn-input").last();
  await isbn.click();
  await isbn.type(DEMO_ISBN, { delay: 60 });
  await sleep(500);
  await page.keyboard.press("Tab"); // blur -> triggers metadata fetch
  // wait on the LIVE DOM until the last Title cell is auto-filled (re-queries each tick,
  // so it catches the input that renderRows() recreates after the lookup returns)
  await page
    .waitForFunction(
      () => {
        const els = document.querySelectorAll('.book-input[data-field="book_name"]');
        const el = els[els.length - 1];
        return el && el.value.trim().length > 0;
      },
      { timeout: 15000 }
    )
    .catch(() => {});
  await sleep(2500); // hold on the filled result
};

const recQrPrint = async (page) => {
  await openAddBooks(page);
  await page.click("#load-books");
  await sleep(2500);
  await page.check("#select-all-books");
  await sleep(1500);
  await page.click("#print-labels"); // opens the printable QR sheet popup
  await sleep(2800);
};

async function shotQrLabels(browser, state) {
  const ctx = await browser.newContext({ viewport: VIEWPORT, storageState: state });
  const page = await ctx.newPage();
  await openAddBooks(page);
  await page.click("#load-books");
  await page.waitForTimeout(2200);
  await page.check("#select-all-books");
  await page.waitForTimeout(600);
  const [popup] = await Promise.all([page.waitForEvent("popup"), page.click("#print-labels")]);
  await popup.waitForLoadState("networkidle").catch(() => {});
  await popup.waitForTimeout(1500);
  await popup.screenshot({ path: path.join(ASSETS, "qr-labels.png"), fullPage: true });
  await ctx.close();
  console.log("shot: qr-labels.png");
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const state = await login(browser);
  console.log("logged in, capturing extras...");
  await record(browser, state, "feature-metadata", recMetadata);
  await record(browser, state, "feature-qr-print", recQrPrint);
  try { await shotQrLabels(browser, state); } catch (e) { console.log("! shotQrLabels: " + e.message.split("\n")[0]); }
  await browser.close();
  console.log("DONE");
})();
