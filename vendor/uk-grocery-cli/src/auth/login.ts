import { Browser, BrowserContext, Page, chromium } from 'playwright';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import * as readline from 'readline';
import { randomUUID } from 'crypto';

const CONFIG_DIR = path.join(os.homedir(), '.sainsburys');
const SESSION_FILE = path.join(CONFIG_DIR, 'session.json');
const USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36';

export interface SessionData {
  cookies: any[];
  expiresAt: string;
  lastLogin: string;
}

async function dismissCookieBanner(page: Page): Promise<void> {
  try {
    console.log('🍪 Checking for cookie consent...');
    const acceptButton = page.locator('#onetrust-accept-btn-handler');
    if (await acceptButton.isVisible({ timeout: 3000 })) {
      console.log('🍪 Accepting cookies...');
      await acceptButton.click();
      console.log('🍪 Waiting for banner to dismiss...');
      await page.waitForTimeout(3000);
      await page.waitForSelector('#onetrust-consent-sdk.ot-hide, .onetrust-pc-dark-filter.ot-hide', { timeout: 5000 }).catch(() => {});
    }
  } catch (e) {
    console.log('🍪 No cookie consent found or already accepted');
  }
}

async function removeCookieOverlays(page: Page): Promise<void> {
  // @ts-ignore - runs in browser context
  await page.evaluate(() => {
    // @ts-ignore
    const overlay = document.querySelector('.onetrust-pc-dark-filter');
    // @ts-ignore
    const banner = document.querySelector('#onetrust-consent-sdk');
    if (overlay) overlay.remove();
    if (banner) banner.remove();
  });
}

/**
 * Navigates to the login page and submits email/password. Stops right before
 * the MFA prompt (if any) so callers can decide how to collect the code —
 * a blocking terminal prompt (login()) or an out-of-band async submission
 * (startLogin()/submitMfaCode(), driven by e.g. a Slack modal).
 */
async function submitCredentials(page: Page, email: string, password: string): Promise<{ mfaRequired: boolean }> {
  console.log('📍 Navigating to login page...');
  await page.goto('https://www.sainsburys.co.uk/gol-ui/oauth/login', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3000);

  await dismissCookieBanner(page);

  console.log('⏳ Waiting for login form...');
  await page.waitForSelector('input[type="email"], input[name="email"], #username', { timeout: 10000 });

  console.log('📧 Entering email...');
  await page.fill('input[type="email"], input[name="email"], #username', email);
  await page.waitForTimeout(500);

  console.log('🔑 Entering password...');
  await page.fill('input[type="password"], input[name="password"], #password', password);
  await page.waitForTimeout(500);

  console.log('🧹 Removing cookie overlays...');
  await removeCookieOverlays(page);
  await page.waitForTimeout(1000);

  console.log('👆 Clicking login...');
  await page.click('button[type="submit"], button[data-testid="log-in"]');

  console.log('⏳ Waiting for login...');
  await page.waitForTimeout(5000);

  const currentUrl = page.url();
  console.log(`Current URL: ${currentUrl}`);

  if (currentUrl.includes('/mfa')) {
    console.log('🔐 MFA required - SMS code sent');
    console.log('📱 Check your phone for the 6-digit code');
    return { mfaRequired: true };
  }
  if (currentUrl.includes('login')) {
    throw new Error('Login failed - still on login page');
  }
  return { mfaRequired: false };
}

/** Fills and submits the MFA code on a page already sitting on the /mfa step. */
async function submitMfaOnPage(page: Page, mfaCode: string): Promise<void> {
  if (!mfaCode || mfaCode.length !== 6) {
    throw new Error('Invalid MFA code - must be 6 digits');
  }

  console.log('🔑 Submitting MFA code...');
  await page.fill('#code, input[name="code"]', mfaCode);
  await page.waitForTimeout(500);

  // Cookie overlays may reappear on the MFA page.
  await removeCookieOverlays(page);
  await page.waitForTimeout(500);

  await page.click('button[data-testid="submit-code"], button[type="submit"]:has-text("Continue")');

  console.log('⏳ Waiting for redirect...');
  await page.waitForTimeout(5000);

  const finalUrl = page.url();
  console.log(`Final URL after MFA: ${finalUrl}`);

  if (finalUrl.includes('login') || finalUrl.includes('mfa')) {
    throw new Error('MFA verification failed - check code and try again');
  }
}

async function finishLogin(browser: Browser, context: BrowserContext): Promise<SessionData> {
  console.log('✅ Login successful!');
  const cookies = await context.cookies();
  const sessionData: SessionData = {
    cookies,
    expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(), // 7 days
    lastLogin: new Date().toISOString(),
  };
  saveSession(sessionData);
  await browser.close();
  return sessionData;
}

export async function login(email: string, password: string): Promise<SessionData> {
  console.log('🔐 Logging in to Sainsbury\'s...');

  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ userAgent: USER_AGENT });
  const page = await context.newPage();

  try {
    const { mfaRequired } = await submitCredentials(page, email, password);

    if (mfaRequired) {
      const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
      const mfaCode = await new Promise<string>((resolve) => {
        rl.question('Enter 6-digit MFA code: ', (answer: string) => {
          rl.close();
          resolve(answer.trim());
        });
      });
      await submitMfaOnPage(page, mfaCode);
    }

    return await finishLogin(browser, context);
  } catch (error) {
    await browser.close();
    throw error;
  }
}

// ── Two-phase login (async MFA collection, e.g. from a Slack modal) ──────────

interface PendingLogin {
  browser: Browser;
  page: Page;
  timeout: NodeJS.Timeout;
}

const PENDING_LOGINS = new Map<string, PendingLogin>();
const PENDING_LOGIN_TTL_MS = 5 * 60 * 1000;

function evictPendingLogin(handle: string): void {
  const pending = PENDING_LOGINS.get(handle);
  if (!pending) return;
  PENDING_LOGINS.delete(handle);
  clearTimeout(pending.timeout);
  pending.browser.close().catch(() => {});
}

export type StartLoginResult =
  | { status: 'ok' }
  | { status: 'mfa_required'; handle: string };

/**
 * Phase 1 of the async login flow: submits email/password and returns
 * immediately. If Sainsbury's demands MFA, the browser is kept open (keyed by
 * `handle`) until submitMfaCode() is called or PENDING_LOGIN_TTL_MS elapses.
 */
export async function startLogin(email: string, password: string): Promise<StartLoginResult> {
  console.log('🔐 Logging in to Sainsbury\'s (async)...');

  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ userAgent: USER_AGENT });
  const page = await context.newPage();

  try {
    const { mfaRequired } = await submitCredentials(page, email, password);

    if (!mfaRequired) {
      await finishLogin(browser, context);
      return { status: 'ok' };
    }

    const handle = randomUUID();
    const timeout = setTimeout(() => evictPendingLogin(handle), PENDING_LOGIN_TTL_MS);
    PENDING_LOGINS.set(handle, { browser, page, timeout });
    return { status: 'mfa_required', handle };
  } catch (error) {
    await browser.close();
    throw error;
  }
}

export type SubmitMfaResult =
  | { status: 'ok' }
  | { status: 'error'; message: string };

/** Phase 2: completes a login started by startLogin() with the SMS code. */
export async function submitMfaCode(handle: string, code: string): Promise<SubmitMfaResult> {
  const pending = PENDING_LOGINS.get(handle);
  if (!pending) {
    return { status: 'error', message: 'No pending login for that handle — it may have expired. Run /authenticate again.' };
  }

  try {
    await submitMfaOnPage(pending.page, code);
    await finishLogin(pending.browser, pending.page.context());
    PENDING_LOGINS.delete(handle);
    clearTimeout(pending.timeout);
    return { status: 'ok' };
  } catch (error: any) {
    return { status: 'error', message: error?.message || 'MFA verification failed' };
  }
}

export function saveSession(session: SessionData) {
  if (!fs.existsSync(CONFIG_DIR)) {
    fs.mkdirSync(CONFIG_DIR, { recursive: true });
  }

  fs.writeFileSync(SESSION_FILE, JSON.stringify(session, null, 2), { mode: 0o600 });
  console.log(`💾 Session saved to ${SESSION_FILE}`);
}

export function loadSession(): SessionData | null {
  if (!fs.existsSync(SESSION_FILE)) {
    return null;
  }

  try {
    const data = fs.readFileSync(SESSION_FILE, 'utf8');
    const session: SessionData = JSON.parse(data);

    if (new Date(session.expiresAt) < new Date()) {
      console.log('⚠️  Session expired');
      return null;
    }

    return session;
  } catch (error) {
    console.log('⚠️  Corrupt session file, removing');
    fs.unlinkSync(SESSION_FILE);
    return null;
  }
}

export function getCookieString(session: SessionData): string {
  return session.cookies.map(c => `${c.name}=${c.value}`).join('; ');
}

export function clearSession() {
  if (fs.existsSync(SESSION_FILE)) {
    fs.unlinkSync(SESSION_FILE);
    console.log('🗑️  Session cleared');
  }
}
