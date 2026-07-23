#!/usr/bin/env node
// Local-only HTTP server exposing the two-phase Sainsbury's login (startLogin /
// submitMfaCode) so a long-running process outside this CLI — the sAInsburys
// Slack bot — can drive a login across two separate Slack modal submissions
// without needing a real terminal stdin for the MFA prompt.
//
// Bound to 127.0.0.1 by default: this only ever needs to be reachable from the
// same machine's Slack bot process, never from the network.
import http from 'node:http';
import { URL } from 'node:url';
import { startLogin, submitMfaCode } from './auth/login';

const host = process.env.GROC_AUTH_HOST || '127.0.0.1';
const port = parsePort(process.env.GROC_AUTH_PORT || '7877');

function parsePort(value: string): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 1 || parsed > 65535) {
    throw new Error(`Invalid GROC_AUTH_PORT: ${value}`);
  }
  return parsed;
}

function sendJson(res: http.ServerResponse, status: number, data: unknown): void {
  const body = JSON.stringify(data);
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': 'no-store',
  });
  res.end(body);
}

function readJsonBody(req: http.IncomingMessage): Promise<any> {
  return new Promise((resolve, reject) => {
    let raw = '';
    req.on('data', (chunk) => { raw += chunk; });
    req.on('end', () => {
      if (!raw) return resolve({});
      try {
        resolve(JSON.parse(raw));
      } catch {
        reject(Object.assign(new Error('Invalid JSON body'), { statusCode: 400 }));
      }
    });
    req.on('error', reject);
  });
}

async function handleRequest(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
  const url = new URL(req.url || '/', `http://${req.headers.host || `${host}:${port}`}`);

  if (url.pathname === '/' || url.pathname === '/health') {
    return sendJson(res, 200, { ok: true, endpoints: ['POST /login/start', 'POST /login/mfa'] });
  }

  if (req.method !== 'POST') {
    return sendJson(res, 405, { error: 'Method not allowed' });
  }

  if (url.pathname === '/login/start') {
    const body = await readJsonBody(req);
    if (!body.email || !body.password) {
      return sendJson(res, 400, { error: 'email and password are required' });
    }
    const result = await startLogin(body.email, body.password);
    return sendJson(res, 200, result);
  }

  if (url.pathname === '/login/mfa') {
    const body = await readJsonBody(req);
    if (!body.handle || !body.code) {
      return sendJson(res, 400, { error: 'handle and code are required' });
    }
    const result = await submitMfaCode(body.handle, body.code);
    return sendJson(res, 200, result);
  }

  return sendJson(res, 404, { error: 'Not found' });
}

const server = http.createServer((req, res) => {
  handleRequest(req, res).catch((error: any) => {
    const status = Number.isInteger(error?.statusCode) ? error.statusCode : 500;
    sendJson(res, status, { error: error?.message || 'Internal server error' });
  });
});

server.listen(port, host, () => {
  console.log(`groc auth-server listening on http://${host}:${port}`);
});
