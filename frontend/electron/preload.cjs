const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("bandscore", {
  openFiles: (filters) => ipcRenderer.invoke("dialog:openFiles", filters),
  newWindow: () => ipcRenderer.invoke("window:new"),
  platform: process.platform,
});
