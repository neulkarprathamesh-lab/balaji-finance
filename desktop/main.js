/**
 * Balaji FeeHub - Electron main process
 *
 * One EXE, two behaviours:
 *   - On the Main Server PC: auto-detects http://127.0.0.1:8001 -> loads http://127.0.0.1:3000
 *   - On a Client PC:        loads saved server IP from %APPDATA%\BalajiFeeHub\config.json,
 *                            else LAN /24 scan, else manual entry via connect.html
 *
 * MongoDB stays on 127.0.0.1 on the Main Server. Clients only ever talk to the
 * backend + frontend on ports 8001/3000 - never to Mongo directly.
 */
const { app, BrowserWindow, Menu, ipcMain, shell, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const http = require('http');
const os = require('os');

// -----------------------------------------------------------------------------
// Config persistence
// -----------------------------------------------------------------------------
const CONFIG_DIR = path.join(app.getPath('appData'), 'BalajiFeeHub');
const CONFIG_FILE = path.join(CONFIG_DIR, 'config.json');
const BACKEND_PORT = 8001;
const FRONTEND_PORT = 3000;
const PROBE_TIMEOUT_MS = 800;
const MANUAL_TIMEOUT_MS = 5000;

function readConfig() {
  try {
    return JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf8'));
  } catch (_) {
    return {};
  }
}
function writeConfig(cfg) {
  try {
    fs.mkdirSync(CONFIG_DIR, { recursive: true });
    fs.writeFileSync(CONFIG_FILE, JSON.stringify(cfg, null, 2), 'utf8');
  } catch (err) {
    console.error('Failed to write config:', err);
  }
}

// -----------------------------------------------------------------------------
// Server probing
// -----------------------------------------------------------------------------
function probeServer(ip, timeoutMs) {
  return new Promise((resolve) => {
    const options = { host: ip, port: BACKEND_PORT, path: '/api/version', timeout: timeoutMs };
    const req = http.get(options, (res) => {
      let body = '';
      res.on('data', (chunk) => { body += chunk; if (body.length > 4096) { req.destroy(); } });
      res.on('end', () => {
        if (res.statusCode === 200) resolve(true); else resolve(false);
      });
    });
    req.on('error', () => resolve(false));
    req.on('timeout', () => { req.destroy(); resolve(false); });
  });
}

function getLocalSubnets() {
  const subnets = new Set();
  const ifaces = os.networkInterfaces();
  for (const list of Object.values(ifaces)) {
    if (!list) continue;
    for (const iface of list) {
      if (iface.family === 'IPv4' && !iface.internal) {
        const parts = iface.address.split('.');
        subnets.add(`${parts[0]}.${parts[1]}.${parts[2]}.`);
      }
    }
  }
  return Array.from(subnets);
}

async function scanLan(onProgress) {
  const subnets = getLocalSubnets();
  for (const prefix of subnets) {
    const promises = [];
    for (let i = 1; i <= 254; i++) {
      const ip = `${prefix}${i}`;
      promises.push(
        probeServer(ip, PROBE_TIMEOUT_MS).then((ok) => (ok ? ip : null))
      );
    }
    if (onProgress) onProgress(`Scanning ${prefix}0/24 (254 addresses in parallel)...`);
    const results = await Promise.all(promises);
    const found = results.find((x) => x);
    if (found) return found;
  }
  return null;
}

async function detectMainServer(onProgress) {
  if (onProgress) onProgress('Checking local Main Server (127.0.0.1)...');
  if (await probeServer('127.0.0.1', 1500)) return '127.0.0.1';

  const cfg = readConfig();
  if (cfg.serverIp && cfg.serverIp !== '127.0.0.1') {
    if (onProgress) onProgress(`Trying saved Main Server (${cfg.serverIp})...`);
    if (await probeServer(cfg.serverIp, 3000)) return cfg.serverIp;
  }

  if (onProgress) onProgress('Scanning your school LAN for the Main Server...');
  const found = await scanLan(onProgress);
  return found;
}

// -----------------------------------------------------------------------------
// Window management
// -----------------------------------------------------------------------------
let mainWindow = null;
let currentServerIp = null;

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: 'Balaji FeeHub',
    icon: path.join(__dirname, 'icon.ico'),
    autoHideMenuBar: true,
    backgroundColor: '#0f172a',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  mainWindow.once('ready-to-show', () => mainWindow.show());
  mainWindow.on('closed', () => { mainWindow = null; });

  // External links (mailto, https support portal, etc.) open in system browser.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//i.test(url) && !url.startsWith(`http://${currentServerIp}:`)) {
      shell.openExternal(url);
      return { action: 'deny' };
    }
    return { action: 'allow' };
  });

  // If the loaded backend disappears (Main Server goes down), fall back to connect.
  mainWindow.webContents.on('did-fail-load', (_e, errorCode, errorDesc, validatedURL) => {
    if (validatedURL && validatedURL.includes(`:${FRONTEND_PORT}`)) {
      console.warn(`Lost connection to ${validatedURL} (${errorCode} ${errorDesc}) - showing connect screen`);
      showConnectScreen(`Lost connection to Main Server at ${currentServerIp}.`);
    }
  });

  buildMenu();
  showConnectScreen();
  startDetectionFlow();
}

function showConnectScreen(errorMessage) {
  if (!mainWindow) return;
  const url = 'file://' + path.join(__dirname, 'renderer', 'connect.html');
  const suffix = errorMessage ? `?error=${encodeURIComponent(errorMessage)}` : '';
  mainWindow.loadURL(url + suffix);
}

function loadServerApp(ip) {
  if (!mainWindow) return;
  currentServerIp = ip;
  writeConfig({ serverIp: ip, lastConnectedAt: new Date().toISOString() });
  mainWindow.loadURL(`http://${ip}:${FRONTEND_PORT}`);
}

async function startDetectionFlow() {
  const send = (msg) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('connect-progress', msg);
    }
  };
  send('Starting...');
  try {
    const ip = await detectMainServer(send);
    if (ip) {
      send(`Found Main Server at ${ip}. Loading Balaji FeeHub...`);
      setTimeout(() => loadServerApp(ip), 300);
    } else {
      send(null);
      if (mainWindow) mainWindow.webContents.send('discovery-failed');
    }
  } catch (err) {
    console.error('Detection error:', err);
    if (mainWindow) mainWindow.webContents.send('discovery-failed');
  }
}

// -----------------------------------------------------------------------------
// Menu
// -----------------------------------------------------------------------------
function buildMenu() {
  const template = [
    {
      label: '&File',
      submenu: [
        { label: 'Reload Balaji FeeHub', accelerator: 'F5', click: () => mainWindow && mainWindow.webContents.reload() },
        { label: 'Change Main Server...', click: () => { currentServerIp = null; showConnectScreen(); startDetectionFlow(); } },
        { type: 'separator' },
        { label: 'Exit', role: 'quit' },
      ],
    },
    {
      label: '&View',
      submenu: [
        { label: 'Toggle Full Screen', role: 'togglefullscreen' },
        { type: 'separator' },
        { label: 'Zoom In', role: 'zoomIn' },
        { label: 'Zoom Out', role: 'zoomOut' },
        { label: 'Reset Zoom', role: 'resetZoom' },
      ],
    },
    {
      label: '&Help',
      submenu: [
        {
          label: 'About Balaji FeeHub',
          click: () => {
            dialog.showMessageBox(mainWindow, {
              type: 'info',
              title: 'About Balaji FeeHub',
              message: 'Balaji FeeHub',
              detail:
                'Version 1.0.0\n' +
                'Balaji Convent & Junior College, Butibori, Nagpur\n\n' +
                'Fee & accounting software - LAN-based, offline-first.\n' +
                (currentServerIp ? `Connected to Main Server: ${currentServerIp}\n` : '') +
                `Config: ${CONFIG_FILE}`,
              buttons: ['OK'],
            });
          },
        },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

// -----------------------------------------------------------------------------
// IPC from renderer
// -----------------------------------------------------------------------------
ipcMain.handle('connect-manual', async (_event, rawIp) => {
  const ip = (rawIp || '').trim().replace(/^https?:\/\//i, '').replace(/:\d+.*$/, '').replace(/\/$/, '');
  if (!/^\d{1,3}(\.\d{1,3}){3}$/.test(ip)) {
    return { ok: false, error: 'Please enter a valid IPv4 address (e.g. 192.168.1.10).' };
  }
  const ok = await probeServer(ip, MANUAL_TIMEOUT_MS);
  if (!ok) {
    return {
      ok: false,
      error: `Could not reach the Balaji FeeHub Main Server at http://${ip}:${BACKEND_PORT}. Check that the Main Server is running and that Windows Firewall allows port ${BACKEND_PORT}.`,
    };
  }
  loadServerApp(ip);
  return { ok: true, ip };
});

ipcMain.handle('rediscover', async () => {
  showConnectScreen();
  startDetectionFlow();
  return { ok: true };
});

ipcMain.handle('get-saved-server', async () => {
  return readConfig();
});

// -----------------------------------------------------------------------------
// Boot
// -----------------------------------------------------------------------------
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  app.whenReady().then(createMainWindow);

  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
  });

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createMainWindow();
  });
}
