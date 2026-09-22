const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('harness', {
  sendQuery: (text, attachments = []) => ipcRenderer.send('agent:query', { text, attachments }),
  abort: () => ipcRenderer.send('agent:abort'),
  switchProfile: (profile) => ipcRenderer.send('agent:switch_profile', { profile }),
  setSteps: (steps) => ipcRenderer.send('agent:set_steps', { steps }),
  clearHistory: () => ipcRenderer.send('agent:clear'),
  getStatus: () => ipcRenderer.send('agent:get_status'),
  selectWorkspace: () => ipcRenderer.invoke('dialog:select_workspace'),
  selectFile: (options) => ipcRenderer.invoke('dialog:select_file', options),
  saveAttachment: (filename, base64Data, workspacePath) => ipcRenderer.invoke('media:save_attachment', { filename, base64Data, workspacePath }),
  readFilePreview: (filePath) => ipcRenderer.invoke('media:read_file_preview', { filePath }),
  openFile: (filePath) => ipcRenderer.invoke('media:open_file', { filePath }),
  setWorkspace: (path) => ipcRenderer.send('agent:set_workspace', { path }),
  listProjects: () => ipcRenderer.send('agent:list_projects'),
  unregisterProject: (path) => ipcRenderer.send('agent:unregister_project', { path }),
  listSessions: (path) => ipcRenderer.send('agent:list_sessions', { path }),
  loadSession: (path, sessionId) => ipcRenderer.send('agent:load_session', { path, session_id: sessionId }),
  saveSession: (path, sessionId, title, messages, model, mode) => ipcRenderer.send('agent:save_session', { path, session_id: sessionId, title, messages, model, mode }),
  renameSession: (path, sessionId, title) => ipcRenderer.send('agent:rename_session', { path, session_id: sessionId, title }),
  deleteSession: (path, sessionId) => ipcRenderer.send('agent:delete_session', { path, session_id: sessionId }),
  getBackgroundTasks: () => ipcRenderer.send('tasks:get'),
  stopProcess: (pid) => ipcRenderer.send('tasks:stop', { pid }),
  getProcessOutput: (pid) => ipcRenderer.send('tasks:get_output', { pid }),
  openExternal: (url) => ipcRenderer.invoke('app:open_external', url),
  cloudListTasks: () => ipcRenderer.send('cloud:list_tasks'),
  cloudTriggerRun: (workflow) => ipcRenderer.send('cloud:trigger_run', { workflow }),
  cloudGetLogs: (runId) => ipcRenderer.send('cloud:get_logs', { run_id: runId }),
  cloudSetTelegram: (botToken, chatId) => ipcRenderer.send('cloud:set_telegram', { bot_token: botToken, chat_id: chatId }),
  cloudTestTelegram: (botToken, chatId, message) => ipcRenderer.send('cloud:test_telegram', { bot_token: botToken, chat_id: chatId, message }),
  onEvent: (callback) => {
    const handler = (event, data) => callback(data);
    ipcRenderer.on('agent:event', handler);
    return () => ipcRenderer.removeListener('agent:event', handler);
  }
});
