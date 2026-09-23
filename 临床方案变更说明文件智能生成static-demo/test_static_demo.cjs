const { chromium } = require("playwright");
const { pathToFileURL } = require("url");
const path = require("path");

let browser;
(async () => {
  const html = process.argv[2];
  const edge = process.argv[3];
  if (!html || !edge) throw new Error("usage: node test_static_demo.cjs <html> <edge>");

  browser = await chromium.launch({ headless: true, executablePath: edge });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  const errors = [];
  page.on("pageerror", (error) => errors.push(`pageerror: ${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(`console: ${message.text()}`);
  });

  await page.goto(pathToFileURL(path.resolve(html)).href, { waitUntil: "load" });
  await page.waitForTimeout(2500);
  const diagnostic = await page.evaluate(() => ({
    count: document.querySelector("#change-count")?.textContent,
    save: document.querySelector("#save-status")?.textContent,
    fatal: document.querySelector("#fatal-panel")?.textContent,
    workspaceHidden: document.querySelector("#workspace")?.hidden
  }));
  if (diagnostic.count !== "194" || !diagnostic.save?.includes("静态演示")) {
    throw new Error(`startup failed: ${JSON.stringify({ diagnostic, errors })}`);
  }

  const initial = await page.evaluate(() => ({
    title: document.title,
    count: document.querySelector("#change-count")?.textContent,
    notice: document.querySelector(".static-demo-notice")?.textContent.replace(/\s+/g, " ").trim(),
    overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth
  }));
  if (!initial.title.includes("静态演示") || initial.count !== "194" || initial.overflow) {
    throw new Error(`invalid initial state: ${JSON.stringify(initial)}`);
  }

  await page.locator("#search").fill("PK");
  await page.locator("#clear-filters").click();
  await page.locator("#metadata-button").click();
  await page.locator("#close-dialog").click();

  await page.locator("#submit-button").click();
  await page.locator('[data-role="confirm-submit"]').click();
  await page.waitForFunction(() => document.querySelector("#toast")?.textContent.includes("本次快照已提交"));
  await page.locator("#checks-button").click();
  await page.waitForFunction(() => document.querySelector("#dialog-body")?.textContent.includes("静态演示 · Word 生成流程"));
  const simulated = await page.locator("#dialog-body").textContent();
  if (!simulated.includes("不会创建或下载正式 Word 文件")) throw new Error("missing static submission disclosure");
  await page.locator("#close-dialog").click();

  await page.setViewportSize({ width: 700, height: 900 });
  const narrowOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  if (narrowOverflow) throw new Error("700px viewport has horizontal overflow");
  if (errors.length) throw new Error(errors.join("\n"));

  console.log(JSON.stringify({ loaded: true, offline: true, count: 194, submitSimulated: true, responsive: true }));
  await browser.close();
  browser = null;
})().catch(async (error) => {
  console.error(error.stack || error);
  if (browser) await browser.close().catch(() => {});
  process.exitCode = 1;
});
