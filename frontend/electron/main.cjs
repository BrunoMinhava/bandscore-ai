// BandScore AI — processo principal do Electron.
// Em desenvolvimento carrega o servidor Vite; empacotado carrega dist/.
// Em produção arranca também o backend Python local.
const { app, BrowserWindow, ipcMain, dialog } = require("electron");
const path = require("node:path");
const { spawn } = require("node:child_process");

const DEV_URL = process.env.ELECTRON_START_URL || "http://localhost:5173";
let backendProcess = null;

function createWindow() {
  const win = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1080,
    minHeight: 700,
    titleBarStyle: process.platform === "darwin" ? "hiddenInset" : "default",
    backgroundColor: "#0b0d12",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  if (app.isPackaged) {
    win.loadFile(path.join(__dirname, "../dist/index.html"));
  } else {
    win.loadURL(DEV_URL);
  }
  return win;
}

function startBackend() {
  if (!app.isPackaged) return; // em dev, o backend arranca à parte (scripts/dev.sh)
  const python = path.join(process.resourcesPath, "backend", ".venv", "bin", "python");
  backendProcess = spawn(python, ["-m", "uvicorn", "app.main:app", "--port", "8765"], {
    cwd: path.join(process.resourcesPath, "backend"),
    stdio: "ignore",
  });
}

ipcMain.handle("dialog:openFiles", async (_e, filters) => {
  const result = await dialog.showOpenDialog({
    properties: ["openFile", "multiSelections"],
    filters: filters || [],
  });
  return result.canceled ? [] : result.filePaths;
});

ipcMain.handle("window:new", () => {
  createWindow();
});

app.whenReady().then(() => {
  startBackend();
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  if (backendProcess) backendProcess.kill();
});
