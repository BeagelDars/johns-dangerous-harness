const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const readline = require('readline');

let mainWindow = null;
let pythonProcess = null;
let queryCounter = 0;



function getProjectRoot() {
  const candidates = [
    __dirname,
    path.resolve(__dirname, '..'),
    path.resolve(__dirname, '..', '..', '..', '..'),
    path.resolve(__dirname, '..', '..', '..'),
    process.cwd(),
    'C:\\Users\\User\\Downloads\\Johns dangerous harness'
  ];
  for (const dir of candidates) {
    if (fs.existsSync(path.join(dir, 'harness', 'bridge.py'))) {
      return dir;
    }
  }
  return 'C:\\Users\\User\\Downloads\\Johns dangerous harness';
}

function getPythonCommand() {
  const candidates = [
    'C:\\Users\\User\\AppData\\Local\\Programs\\Python\\Python312\\python.exe',
    'python',
    'python3'
  ];
  for (const c of candidates) {
    if (c.includes('\\') && fs.existsSync(c)) {
      return c;
    }
  }
  return 'python';
}

function startPythonBackend() {
  const rootDir = getProjectRoot();
  const bridgeScript = path.join(rootDir, 'harness', 'bridge.py');
  const pyCmd = getPythonCommand();

  // Spawn python with unbuffered stdio and explicit UTF-8 mode
  pythonProcess = spawn(pyCmd, ['-X', 'utf8', '-u', bridgeScript], {
    cwd: rootDir,
    env: { ...process.env, PYTHONUNBUFFERED: '1', PYTHONIOENCODING: 'utf-8' },
    stdio: ['pipe', 'pipe', 'pipe']
  });

  pythonProcess.on('error', (err) => {
    console.error('Failed to spawn Python process:', err);
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('agent:event', {
        type: 'error',
        error: `Python backend failed to start: ${err.message}`
      });
    }
  });

  const rl = readline.createInterface({
    input: pythonProcess.stdout,
    crlfDelay: Infinity
  });

  rl.on('line', (line) => {
    line = line.trim();
    if (!line) return;
    try {
      const eventData = JSON.parse(line);
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('agent:event', eventData);
      }
    } catch (err) {
      console.error('Failed to parse Python line:', line, err);
    }
  });

  pythonProcess.stderr.on('data', (data) => {
    console.error(`Python stderr: ${data.toString()}`);
  });

  pythonProcess.on('exit', (code, signal) => {
    console.log(`Python process exited with code ${code}, signal ${signal}`);
    pythonProcess = null;
    if (code !== 0 && code !== null && mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('agent:event', {
        type: 'error',
        error: `Python backend disconnected (code: ${code}). Reconnecting on next action...`
      });
    }
  });
}

function sendToPython(cmd) {
  if (!pythonProcess || !pythonProcess.stdin || pythonProcess.stdin.destroyed) {
    startPythonBackend();
    setTimeout(() => {
      if (pythonProcess && pythonProcess.stdin && !pythonProcess.stdin.destroyed) {
        pythonProcess.stdin.write(JSON.stringify(cmd) + '\n');
      }
    }, 250);
    return;
  }
  pythonProcess.stdin.write(JSON.stringify(cmd) + '\n');
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1180,
    height: 840,
    minWidth: 800,
    minHeight: 600,
    backgroundColor: '#000000',
    title: "John's Harness",
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  mainWindow.loadFile(path.join(__dirname, 'src', 'index.html'));

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// App lifecycle
app.whenReady().then(() => {
  startPythonBackend();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  // Terminate python process cleanly
  if (pythonProcess) {
    try {
      sendToPython({ action: 'exit' });
      pythonProcess.kill();
    } catch (e) {}
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  if (pythonProcess) {
    try {
      pythonProcess.kill();
    } catch (e) {}
  }
});

// IPC listeners from UI
ipcMain.on('agent:query', (event, { text, attachments }) => {
  queryCounter++;
  sendToPython({ action: 'query', text, attachments: attachments || [], id: queryCounter });
});

ipcMain.on('agent:abort', () => {
  sendToPython({ action: 'abort' });
});

ipcMain.on('agent:switch_profile', (event, { profile }) => {
  sendToPython({ action: 'switch_profile', profile });
});

ipcMain.on('agent:set_steps', (event, { steps }) => {
  sendToPython({ action: 'set_steps', steps: parseInt(steps, 10) });
});

ipcMain.on('agent:clear', () => {
  sendToPython({ action: 'clear' });
});

ipcMain.on('agent:get_status', () => {
  sendToPython({ action: 'get_status' });
});

ipcMain.on('agent:list_projects', () => {
  sendToPython({ action: 'list_projects' });
});

ipcMain.on('agent:list_sessions', (event, { path }) => {
  sendToPython({ action: 'list_sessions', path });
});

ipcMain.on('agent:load_session', (event, { path, session_id }) => {
  sendToPython({ action: 'load_session', path, session_id });
});

ipcMain.on('agent:save_session', (event, { path, session_id, title, messages, model, mode }) => {
  sendToPython({ action: 'save_session', path, session_id, title, messages, model, mode });
});

ipcMain.on('agent:rename_session', (event, { path, session_id, title }) => {
  sendToPython({ action: 'rename_session', path, session_id, title });
});

ipcMain.on('agent:delete_session', (event, { path, session_id }) => {
  sendToPython({ action: 'delete_session', path, session_id });
});

ipcMain.on('agent:unregister_project', (event, { path }) => {
  sendToPython({ action: 'unregister_project', path });
});

ipcMain.on('agent:set_workspace', (event, { path }) => {
  sendToPython({ action: 'set_workspace', path });
});

ipcMain.on('tasks:get', () => {
  sendToPython({ action: 'get_background_tasks' });
});

ipcMain.on('tasks:stop', (event, { pid }) => {
  sendToPython({ action: 'stop_process', pid });
});

ipcMain.on('tasks:get_output', (event, { pid }) => {
  sendToPython({ action: 'get_process_output', pid });
});

ipcMain.handle('dialog:select_workspace', async () => {
  if (!mainWindow) return null;
  const result = await dialog.showOpenDialog(mainWindow, {
    title: 'Select Project Directory',
    properties: ['openDirectory', 'createDirectory']
  });
  if (!result.canceled && result.filePaths.length > 0) {
    const selectedDir = result.filePaths[0];
    sendToPython({ action: 'set_workspace', path: selectedDir });
    return selectedDir;
  }
  return null;
});

ipcMain.handle('dialog:select_file', async (event, options = {}) => {
  if (!mainWindow) return null;
  const result = await dialog.showOpenDialog(mainWindow, {
    title: options.title || 'Attach Image or File',
    properties: ['openFile', ...(options.multiple !== false ? ['multiSelections'] : [])],
    filters: [
      { name: 'Supported Files & Images', extensions: ['png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'svg', 'pdf', 'docx', 'xlsx', 'pptx', 'txt', 'py', 'js', 'json', 'md', 'html', 'css'] },
      { name: 'Images (*.png;*.jpg;*.jpeg;*.webp)', extensions: ['png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'svg'] },
      { name: 'Documents (*.pdf;*.docx;*.txt;...)', extensions: ['pdf', 'docx', 'xlsx', 'pptx', 'txt', 'csv', 'md'] },
      { name: 'All Files (*.*)', extensions: ['*'] }
    ]
  });
  if (!result.canceled && result.filePaths.length > 0) {
    return result.filePaths;
  }
  return null;
});

ipcMain.handle('media:save_attachment', async (event, { filename, base64Data, workspacePath }) => {
  try {
    const ws = workspacePath || getProjectRoot();
    const uploadsDir = path.join(ws, '.harness', 'uploads');
    if (!fs.existsSync(uploadsDir)) {
      fs.mkdirSync(uploadsDir, { recursive: true });
    }
    const safeName = filename || `screenshot_${Date.now()}.png`;
    const targetPath = path.join(uploadsDir, safeName);
    const cleanB64 = base64Data.replace(/^data:[^;]+;base64,/, '');
    const buffer = Buffer.from(cleanB64, 'base64');
    fs.writeFileSync(targetPath, buffer);
    return {
      success: true,
      path: targetPath,
      name: safeName,
      size: buffer.length
    };
  } catch (err) {
    console.error('Failed to save attachment:', err);
    return { success: false, error: err.message };
  }
});

ipcMain.handle('media:read_file_preview', async (event, { filePath }) => {
  try {
    if (!filePath || !fs.existsSync(filePath)) return null;
    const ext = path.extname(filePath).toLowerCase();
    const isImage = ['.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.svg'].includes(ext);
    const stat = fs.statSync(filePath);
    let base64Preview = null;
    if (isImage && stat.size <= 25 * 1024 * 1024) {
      const buf = fs.readFileSync(filePath);
      const mime = ext === '.svg' ? 'image/svg+xml' : (ext === '.jpg' || ext === '.jpeg' ? 'image/jpeg' : `image/${ext.slice(1)}`);
      base64Preview = `data:${mime};base64,${buf.toString('base64')}`;
    }
    return {
      path: filePath,
      name: path.basename(filePath),
      size: stat.size,
      isImage,
      preview: base64Preview
    };
  } catch (e) {
    return null;
  }
});

ipcMain.handle('media:open_file', async (event, { filePath }) => {
  if (filePath && fs.existsSync(filePath)) {
    shell.openPath(filePath);
    return true;
  }
  return false;
});
