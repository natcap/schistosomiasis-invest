import path from 'path';
import connect from 'connect';
import serveStatic from 'serve-static';
import http from 'http';

import {
  BrowserWindow,
  ipcMain,
} from 'electron';

import {
  createJupyterProcess,
  shutdownPythonProcess,
} from './createPythonFlaskProcess';
import setupContextMenu from './setupContextMenu';
import { ipcMainChannels } from './ipcMainChannels';

function createWindow(parentWindow, isDevMode) {
  const devModeArg = isDevMode ? '--devMode' : '';
  const win = new BrowserWindow({
    parent: parentWindow,
    width: 1200,
    height: 900,
    frame: true,
    webPreferences: {
      minimumFontSize: 12,
      preload: path.join(__dirname, '../preload/preload.js'),
      defaultEncoding: 'UTF-8',
      additionalArguments: [devModeArg],
    },
  });
  setupContextMenu(win);
  win.setMenu(null);
  if (isDevMode) {
    win.webContents.openDevTools();
  }
  return win;
}

function serveWorkspace(dir) {
  console.log('SERVING', dir);
  const app = connect();
  app.use(serveStatic(dir));
  // Listening on 8081 to avoid conflict with VM testing
  return http.createServer(app).listen(8081);
}

export default function setupJupyter(parentWindow, isDevMode) {
  ipcMain.on(
    ipcMainChannels.OPEN_JUPYTER, async (event, filepath, pluginID) => {
      const httpServer = serveWorkspace(path.dirname(filepath));
      const [subprocess, port] = await createJupyterProcess(pluginID);
      const child = createWindow(parentWindow, isDevMode);
      child.loadURL(`http://localhost:${port}/?token=${process.env.JUPYTER_TOKEN}`);
      child.on('close', async () => {
        await shutdownPythonProcess(subprocess.pid);
        httpServer.close();
      });
      // TODO: what if entire app is quit instead of this window closing first
    }
  );
}
