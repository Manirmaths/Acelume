// Acelume desktop shell. Like the Android wrapper, this loads the live
// site directly (https://acelume.ng) inside an Electron BrowserWindow
// rather than bundling a static copy of the frontend -- so the existing
// httpOnly auth cookie and CORS setup work exactly as they do in a normal
// browser, and every site update is instantly live in the desktop app too.
const { app, BrowserWindow, shell } = require('electron');

const APP_URL = 'https://acelume.ng';

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 900,
    minHeight: 600,
    title: 'Acelume',
    backgroundColor: '#f8f9fb',
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  win.setMenuBarVisibility(false);
  win.loadURL(APP_URL);

  // Open any link that tries to open a new window (e.g. target="_blank")
  // in the user's real browser instead of a second Electron window.
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
