// Automated screenshot + feature-recording capture for the Library Management app.
// Drives the real Frappe desk UI with Playwright, against seeded demo data.
//   node capture.js
// Outputs PNG screenshots to docs/assets/ and per-feature .webm to ./_videos/
// (convert.js then turns the .webm files into GIFs).

const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BASE = process.env.BASE_URL || "http://localhost:8000";
const USER = "library-demo@example.com";
const PASS = "Capture@2026xyz";
const STUDENT_REF = "DEMO001";
const FREE_ACC = process.env.FREE_ACC || "107119"; // a free demo book accession to issue live
const BRANCH = process.env.DEMO_BRANCH || "Demo Branch";
const ROOM = process.env.DEMO_ROOM || "DEMO-ROOM";
const SHELF = process.env.DEMO_SHELF || "DEMO-01";

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

// Set a Frappe Link field by typing and clicking the awesomplete match.
async function setLink(page, fieldname, value) {
  const wrap = `[data-fieldname="${fieldname}"]`;
  const input = page.locator(`${wrap} input`).first();
  await input.click();
  await input.fill(value);
  await page.waitForTimeout(900);
  const item = page.locator(`${wrap} .awesomplete li`, { hasText: value }).first();
  if (await item.count()) await item.click();
  else await page.keyboard.press("Escape");
  await page.waitForTimeout(400);
  await dismissModals(page);
}

async function openCounter(page) {
  await page.goto(`${BASE}/app/library-counter`, { waitUntil: "networkidle" });
  await page.waitForSelector("#student-form", { timeout: 20000 });
  await page.waitForTimeout(800);
}

async function fetchStudent(page) {
  await page.fill('#student-form [data-fieldname="reference_number"] input', STUDENT_REF);
  await page.click("#fetch-student");
  await page.waitForSelector(".student-card", { timeout: 15000 });
  await page.waitForTimeout(1000);
  await dismissModals(page);
  await page.waitForTimeout(400);
}

// ---- Screenshot tasks ------------------------------------------------------
async function shotCounter(browser, state) {
  const ctx = await browser.newContext({ viewport: VIEWPORT, storageState: state });
  const page = await ctx.newPage();
  await openCounter(page);
  await fetchStudent(page);
  await page.screenshot({ path: path.join(ASSETS, "library-counter.png"), fullPage: true });
  await ctx.close();
  console.log("shot: library-counter.png");
}

async function shotAddBooks(browser, state) {
  const ctx = await browser.newContext({ viewport: VIEWPORT, storageState: state });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/app/add-library-books`, { waitUntil: "networkidle" });
  await page.waitForSelector("#intake-filters", { timeout: 20000 });
  await setLink(page, "branch", BRANCH);
  await setLink(page, "room", ROOM);
  await page.fill('[data-fieldname="book_shelf"] input', SHELF);
  await page.locator('[data-fieldname="book_shelf"] input').press("Enter");
  await page.waitForTimeout(400);
  await dismissModals(page);
  await page.click("#load-books");
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(ASSETS, "add-books.png"), fullPage: true });
  await ctx.close();
  console.log("shot: add-books.png");
}

async function shotReportsDialog(browser, state) {
  const ctx = await browser.newContext({ viewport: VIEWPORT, storageState: state });
  const page = await ctx.newPage();
  await openCounter(page);
  await page.getByRole("button", { name: "Reports" }).click();
  await page.waitForSelector(".library-report-links", { timeout: 8000 });
  await page.waitForTimeout(700);
  await page.screenshot({ path: path.join(ASSETS, "reports.png") });
  await ctx.close();
  console.log("shot: reports.png");
}

async function shotReport(browser, state) {
  const ctx = await browser.newContext({ viewport: VIEWPORT, storageState: state });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/app/query-report/Book Issue Register`, { waitUntil: "networkidle" });
  await page.waitForTimeout(3500);
  await page.screenshot({ path: path.join(ASSETS, "report-book-issue-register.png"), fullPage: true });
  await ctx.close();
  console.log("shot: report-book-issue-register.png");
}

// ---- Recording tasks (each ~5-8s) ------------------------------------------
async function record(browser, state, name, fn) {
  const ctx = await browser.newContext({
    viewport: VIEWPORT,
    storageState: state,
    recordVideo: { dir: VIDEOS, size: VIEWPORT },
  });
  const page = await ctx.newPage();
  try {
    await fn(page);
  } catch (e) {
    console.log(`  ! ${name} error: ${e.message}`);
  }
  await page.waitForTimeout(500);
  const video = page.video();
  await ctx.close();
  if (video) {
    const src = await video.path();
    const dst = path.join(VIDEOS, `${name}.webm`);
    try {
      fs.renameSync(src, dst);
    } catch {
      fs.copyFileSync(src, dst);
    }
    console.log(`rec : ${name}.webm`);
  }
}

const recIssue = async (page) => {
  await openCounter(page);
  await fetchStudent(page);
  await page.fill('#book-form [data-fieldname="book_identifier"] input', FREE_ACC);
  await sleep(700);
  await page.click("#add-book");
  await sleep(1500);
  await page.click("#submit-issue");
  await sleep(2600);
};

const recReturn = async (page) => {
  await openCounter(page);
  await fetchStudent(page);
  await sleep(800);
  await page.locator(".return-check").first().check();
  await sleep(1200);
  await page.click("#submit-return");
  await sleep(2600);
};

const recReissue = async (page) => {
  await openCounter(page);
  await fetchStudent(page);
  await sleep(800);
  await page.locator(".return-check").first().check();
  await sleep(1200);
  await page.click("#submit-reissue");
  await sleep(2600);
};

const recHistory = async (page) => {
  await openCounter(page);
  await fetchStudent(page);
  await page.locator("#student-history").scrollIntoViewIfNeeded();
  await sleep(3500);
};

const recReports = async (page) => {
  await openCounter(page);
  await sleep(800);
  await page.getByRole("button", { name: "Reports" }).click();
  await page.waitForSelector(".library-report-links", { timeout: 8000 });
  await sleep(3500);
};

const recAddBooks = async (page) => {
  await page.goto(`${BASE}/app/add-library-books`, { waitUntil: "networkidle" });
  await page.waitForSelector("#intake-filters", { timeout: 20000 });
  await setLink(page, "branch", BRANCH);
  await setLink(page, "room", ROOM);
  await page.fill('[data-fieldname="book_shelf"] input', SHELF);
  await page.locator('[data-fieldname="book_shelf"] input').press("Enter");
  await sleep(600);
  await dismissModals(page);
  await page.click("#load-books");
  await sleep(3500);
};

const recReportView = async (page) => {
  await page.goto(`${BASE}/app/query-report/Overdue Books`, { waitUntil: "networkidle" });
  await sleep(5500);
};

(async () => {
  const browser = await chromium.launch({ headless: true });
  const state = await login(browser);
  console.log("logged in, capturing...");

  const safe = async (name, fn) => {
    try {
      await fn();
    } catch (e) {
      console.log(`! ${name}: ${e.message.split("\n")[0]}`);
    }
  };

  // screenshots
  await safe("shotCounter", () => shotCounter(browser, state));
  await safe("shotAddBooks", () => shotAddBooks(browser, state));
  await safe("shotReportsDialog", () => shotReportsDialog(browser, state));
  await safe("shotReport", () => shotReport(browser, state));

  // recordings (issue first while a free book exists; it consumes one)
  await record(browser, state, "feature-issue", recIssue);
  await record(browser, state, "feature-reissue", recReissue);
  await record(browser, state, "feature-return", recReturn);
  await record(browser, state, "feature-history", recHistory);
  await record(browser, state, "feature-reports", recReports);
  await record(browser, state, "feature-add-books", recAddBooks);
  await record(browser, state, "feature-report-view", recReportView);

  await browser.close();
  console.log("DONE");
})();
