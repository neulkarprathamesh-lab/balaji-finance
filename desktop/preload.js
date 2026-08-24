const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('feehub', {
  onProgress: (cb) => ipcRenderer.on('connect-progress', (_e, msg) => cb(msg)),
  onDiscoveryFailed: (cb) => ipcRenderer.on('discovery-failed', () => cb()),
  connectManual: (ip) => ipcRenderer.invoke('connect-manual', ip),
  rediscover: () => ipcRenderer.invoke('rediscover'),
  getSavedServer: () => ipcRenderer.invoke('get-saved-server'),

  updater: {
    check: () => ipcRenderer.invoke('updater:check'),
    getContext: () => ipcRenderer.invoke('updater:context'),
    downloadAndInstall: (opts) => ipcRenderer.invoke('updater:downloadAndInstall', opts),
    downloadAndRunFullInstaller: (opts) => ipcRenderer.invoke('updater:downloadAndRunFullInstaller', opts),
    onProgress: (cb) => ipcRenderer.on('updater:progress', (_e, data) => cb(data)),
    removeAllProgressListeners: () => ipcRenderer.removeAllListeners('updater:progress'),
    openExternal: (url) => ipcRenderer.invoke('updater:openReleaseNotes', url),
    reconnect: () => ipcRenderer.invoke('updater:reconnect'),
  },
});
