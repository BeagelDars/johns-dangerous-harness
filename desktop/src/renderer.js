// John's Harness - Minimalist Antigravity & Claude Code Renderer
// Rock-solid session persistence, project management, and file review

let isGenerating = false;
let currentAgentMessageEl = null;
let currentTraceGroup = null;
let currentTraceContainer = null;
let currentTraceBody = null;
let currentTracePillLabel = null;
let currentTurnStartTime = null;
let currentTurnDurationTimer = null;
let currentMarkdownBody = null;
let currentActiveItemEl = null;
let activeToolCalls = []; // { id, name, args, output, status, element }
let typewriterTimer = null;

// Session & Project State
let currentSessionId = null;
let currentSessionTitle = "New Conversation";
let currentSessionMessages = [];
let currentWorkspacePath = "";
let currentActiveMode = "auto";
let currentModelName = "gemini-flash-lite-latest";
let registeredProjects = [];

// Clean vector icons (zero unicode emojis)
const SVG_CHECK = `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
const SVG_DOT = `<span class="trace-dot"></span>`;
const SVG_ARROW = `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>`;
const SVG_STOP_SQUARE = `<svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2"></rect></svg>`;

// DOM Elements
const chatContainer = document.getElementById('chatContainer');
const messagesList = document.getElementById('messagesList');
const welcomeHero = document.getElementById('welcomeHero');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const clearBtn = document.getElementById('clearBtn');
const segButtons = document.querySelectorAll('.seg-btn');
const stepsInput = document.getElementById('stepsInput');
const projectPill = document.getElementById('projectPill');
const projectNameLabel = document.getElementById('projectNameLabel');

// Sidebar DOM Elements
const sidebar = document.getElementById('sidebar');
const toggleSidebarBtn = document.getElementById('toggleSidebarBtn');
const newChatBtn = document.getElementById('newChatBtn');
const projectsTree = document.getElementById('projectsTree');
const refreshProjectsBtn = document.getElementById('refreshProjectsBtn');
const addProjectBtn = document.getElementById('addProjectBtn');

// Inspector DOM Elements
const inspectorPanel = document.getElementById('inspectorPanel');
const inspectorResizer = document.getElementById('inspectorResizer');
const inspectorToolName = document.getElementById('inspectorToolName');
const inspectorStatus = document.getElementById('inspectorStatus');
const closeInspectorBtn = document.getElementById('closeInspectorBtn');
const inspectorArgsTitle = document.getElementById('inspectorArgsTitle');
const inspectorArgsCode = document.getElementById('inspectorArgsCode');
const inspectorOutputCode = document.getElementById('inspectorOutputCode');
const copyArgsBtn = document.getElementById('copyArgsBtn');
const copyOutputBtn = document.getElementById('copyOutputBtn');

// Background Tasks Bar DOM Elements
const tasksBarContainer = document.getElementById('tasksBarContainer');
const tasksBar = document.getElementById('tasksBar');
const tasksBarToggle = document.getElementById('tasksBarToggle');
const tasksCountLabel = document.getElementById('tasksCountLabel');
const tasksDrawer = document.getElementById('tasksDrawer');
const tasksList = document.getElementById('tasksList');

// Attachment & Lightbox DOM Elements
const inputCard = document.getElementById('inputCard');
const attachmentsPreview = document.getElementById('attachmentsPreview');
const attachBtn = document.getElementById('attachBtn');
const imageLightbox = document.getElementById('imageLightbox');
const lightboxBackdrop = document.getElementById('lightboxBackdrop');
const lightboxCloseBtn = document.getElementById('lightboxCloseBtn');
const lightboxOpenExternalBtn = document.getElementById('lightboxOpenExternalBtn');
const lightboxFilename = document.getElementById('lightboxFilename');
const lightboxImg = document.getElementById('lightboxImg');

let stagedAttachments = []; // Array of { id, path, name, size, isImage, preview }
let currentLightboxPath = null;

// Cloud Tasks & GitHub Actions DOM Elements
const cloudTasksBtn = document.getElementById('cloudTasksBtn');
const cloudTasksDot = document.getElementById('cloudTasksDot');
const cloudDashboardModal = document.getElementById('cloudDashboardModal');
const cloudModalBackdrop = document.getElementById('cloudModalBackdrop');
const cloudCloseBtn = document.getElementById('cloudCloseBtn');
const cloudRefreshBtn = document.getElementById('cloudRefreshBtn');
const cloudTelegramBtn = document.getElementById('cloudTelegramBtn');
const closeTelegramPanelBtn = document.getElementById('closeTelegramPanelBtn');
const cloudTelegramPanel = document.getElementById('cloudTelegramPanel');
const telegramBotTokenInput = document.getElementById('telegramBotTokenInput');
const telegramChatIdInput = document.getElementById('telegramChatIdInput');
const saveTelegramSecretsBtn = document.getElementById('saveTelegramSecretsBtn');
const testTelegramPingBtn = document.getElementById('testTelegramPingBtn');
const telegramStatusMsg = document.getElementById('telegramStatusMsg');

const cloudWorkflowsList = document.getElementById('cloudWorkflowsList');
const cloudWorkflowsCount = document.getElementById('cloudWorkflowsCount');
const cloudRunsList = document.getElementById('cloudRunsList');
const cloudRunsCount = document.getElementById('cloudRunsCount');

const cloudLogsTargetLabel = document.getElementById('cloudLogsTargetLabel');
const copyCloudLogsBtn = document.getElementById('copyCloudLogsBtn');
const cloudLogsTerminal = document.getElementById('cloudLogsTerminal');

const cloudScriptsList = document.getElementById('cloudScriptsList');
const cloudScriptFilename = document.getElementById('cloudScriptFilename');
const copyCloudScriptBtn = document.getElementById('copyCloudScriptBtn');
const cloudScriptCode = document.getElementById('cloudScriptCode');

const statFilesCount = document.getElementById('statFilesCount');
const statTotalBytes = document.getElementById('statTotalBytes');
const cloudFilesList = document.getElementById('cloudFilesList');

let cachedCloudData = null;
let activeCloudScriptPath = null;

let activeBackgroundTasks = [];
let inspectedTaskId = null;
const stoppingPids = new Set();

function stripAnsi(str) {
  if (!str) return '';
  return String(str)
    .replace(/\x1b\[[0-9;]*[a-zA-Z]/g, '')
    .replace(/\x1b\][^\x07]*\x07/g, '');
}

function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function openLightbox(filePath, previewUrl, filename) {
  if (!imageLightbox || !lightboxImg) return;
  currentLightboxPath = filePath || null;
  if (lightboxFilename) lightboxFilename.textContent = filename || (filePath ? filePath.split(/[\\/]/).pop() : 'Screenshot / Image');
  lightboxImg.src = previewUrl || (filePath ? `file:///${filePath.replace(/\\/g, '/')}` : '');
  imageLightbox.style.display = 'flex';
}

function closeLightbox() {
  if (!imageLightbox) return;
  imageLightbox.style.display = 'none';
  if (lightboxImg) lightboxImg.src = '';
  currentLightboxPath = null;
}

function addStagedAttachment(att) {
  if (!att) return;
  if (stagedAttachments.some(a => a.path && a.path === att.path)) return;
  stagedAttachments.push(att);
  renderStagedAttachments();
}

function renderStagedAttachments() {
  if (!attachmentsPreview) return;
  if (stagedAttachments.length === 0) {
    attachmentsPreview.style.display = 'none';
    attachmentsPreview.innerHTML = '';
    return;
  }

  attachmentsPreview.style.display = 'flex';
  attachmentsPreview.innerHTML = '';

  stagedAttachments.forEach(att => {
    const chip = document.createElement('div');
    chip.className = 'staged-att-chip' + (att.isImage ? ' is-image' : ' is-file');
    chip.setAttribute('data-id', att.id);

    if (att.isImage && att.preview) {
      chip.innerHTML = `
        <div class="staged-att-thumb" title="${escapeHtml(att.name || 'Screenshot')} (${formatBytes(att.size || 0)})">
          <img src="${att.preview}" alt="${escapeHtml(att.name || 'Image')}" />
          <button class="staged-att-remove" title="Remove attachment">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
      `;
    } else {
      chip.innerHTML = `
        <div class="staged-att-doc" title="${escapeHtml(att.path || att.name)}">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
          </svg>
          <span class="staged-att-name">${escapeHtml(att.name || 'File')}</span>
          <span class="staged-att-size">${formatBytes(att.size || 0)}</span>
          <button class="staged-att-remove" title="Remove attachment">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
      `;
    }

    const removeBtn = chip.querySelector('.staged-att-remove');
    if (removeBtn) {
      removeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        stagedAttachments = stagedAttachments.filter(a => a.id !== att.id);
        renderStagedAttachments();
      });
    }

    attachmentsPreview.appendChild(chip);
  });
}

if (tasksBarToggle && tasksBar && tasksDrawer) {
  tasksBarToggle.addEventListener('click', () => {
    tasksBar.classList.toggle('open');
    tasksDrawer.style.display = tasksBar.classList.contains('open') ? 'block' : 'none';
  });
}

// Restore saved sidebar collapsed state
if (localStorage.getItem('harness_sidebar_collapsed') === 'true' && sidebar) {
  sidebar.classList.add('collapsed');
}

if (toggleSidebarBtn && sidebar) {
  toggleSidebarBtn.addEventListener('click', () => {
    sidebar.classList.toggle('collapsed');
    localStorage.setItem('harness_sidebar_collapsed', sidebar.classList.contains('collapsed'));
  });
}

// Global Ctrl+B shortcut to toggle projects sidebar
window.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'b' && sidebar) {
    e.preventDefault();
    sidebar.classList.toggle('collapsed');
    localStorage.setItem('harness_sidebar_collapsed', sidebar.classList.contains('collapsed'));
  }
});

// New Conversation button
if (newChatBtn) {
  newChatBtn.addEventListener('click', () => {
    startNewConversation();
  });
}

// Open / Add Project button
if (addProjectBtn) {
  addProjectBtn.addEventListener('click', async () => {
    if (window.harness && window.harness.selectWorkspace) {
      await window.harness.selectWorkspace();
    }
  });
}

// Refresh projects list button
if (refreshProjectsBtn) {
  refreshProjectsBtn.addEventListener('click', () => {
    if (window.harness && window.harness.listProjects) {
      window.harness.listProjects();
    }
  });
}

if (projectPill) {
  projectPill.addEventListener('click', async () => {
    if (window.harness && window.harness.selectWorkspace) {
      const selected = await window.harness.selectWorkspace();
      if (selected && projectNameLabel) {
        const parts = selected.replace(/\\/g, '/').split('/').filter(Boolean);
        projectNameLabel.textContent = parts[parts.length - 1] || selected;
        projectPill.title = selected;
      }
    }
  });
}

// Auto-expand textarea
userInput.addEventListener('input', () => {
  userInput.style.height = 'auto';
  userInput.style.height = Math.min(userInput.scrollHeight, 180) + 'px';
});

// Keypress: Enter sends, Shift+Enter newlines
userInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (isGenerating) {
      handleStop();
      setTimeout(() => {
        handleSend();
      }, 70);
    } else {
      handleSend();
    }
  }
});

sendBtn.addEventListener('click', () => {
  if (isGenerating) {
    handleStop();
  } else {
    handleSend();
  }
});

// Attach button (+) click handler
if (attachBtn) {
  attachBtn.addEventListener('click', async () => {
    if (window.harness && window.harness.selectFile) {
      const selected = await window.harness.selectFile({ multiple: true });
      if (selected && selected.length > 0) {
        for (const fp of selected) {
          const fileInfo = await window.harness.readFilePreview(fp);
          if (fileInfo) {
            addStagedAttachment({
              id: 'att_' + Date.now() + '_' + Math.random().toString(36).substring(2, 7),
              path: fileInfo.path,
              name: fileInfo.name,
              size: fileInfo.size,
              isImage: fileInfo.isImage,
              preview: fileInfo.preview
            });
          }
        }
      }
    }
  });
}

// Screenshot / image clipboard paste (Ctrl+V) handler
userInput.addEventListener('paste', async (e) => {
  const clipboardData = e.clipboardData || window.clipboardData;
  if (!clipboardData || !clipboardData.items) return;

  const items = Array.from(clipboardData.items);
  const imageItems = items.filter(item => item.type && item.type.indexOf('image') !== -1);

  if (imageItems.length > 0) {
    e.preventDefault();
    for (const item of imageItems) {
      const blob = item.getAsFile();
      if (!blob) continue;

      const reader = new FileReader();
      reader.onload = async (ev) => {
        const base64Data = ev.target.result;
        const now = new Date();
        const stamp = now.getFullYear().toString() +
          String(now.getMonth() + 1).padStart(2, '0') +
          String(now.getDate()).padStart(2, '0') + '_' +
          String(now.getHours()).padStart(2, '0') +
          String(now.getMinutes()).padStart(2, '0') +
          String(now.getSeconds()).padStart(2, '0');
        const filename = `screenshot_${stamp}.png`;

        if (window.harness && window.harness.saveAttachment) {
          const saved = await window.harness.saveAttachment(filename, base64Data, currentWorkspacePath);
          if (saved && saved.success) {
            addStagedAttachment({
              id: 'att_' + Date.now() + '_' + Math.random().toString(36).substring(2, 7),
              path: saved.path,
              name: saved.name,
              size: saved.size,
              isImage: true,
              preview: base64Data
            });
          }
        }
      };
      reader.readAsDataURL(blob);
    }
  }
});

// Window-level paste: if user presses Ctrl+V anywhere, redirect images to attachments
window.addEventListener('paste', (e) => {
  if (document.activeElement !== userInput) {
    const clipboardData = e.clipboardData || window.clipboardData;
    if (clipboardData && clipboardData.items) {
      const items = Array.from(clipboardData.items);
      if (items.some(item => item.type && item.type.indexOf('image') !== -1)) {
        userInput.focus();
      }
    }
  }
});

// Drag and drop files / screenshots onto input card
if (inputCard) {
  inputCard.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.stopPropagation();
    inputCard.classList.add('drag-over');
  });

  inputCard.addEventListener('dragleave', (e) => {
    e.preventDefault();
    e.stopPropagation();
    inputCard.classList.remove('drag-over');
  });

  inputCard.addEventListener('drop', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    inputCard.classList.remove('drag-over');

    const files = e.dataTransfer?.files;
    if (!files || files.length === 0) return;

    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      if (f.path && window.harness && window.harness.readFilePreview) {
        const fileInfo = await window.harness.readFilePreview(f.path);
        if (fileInfo) {
          addStagedAttachment({
            id: 'att_' + Date.now() + '_' + Math.random().toString(36).substring(2, 7),
            path: fileInfo.path,
            name: fileInfo.name,
            size: fileInfo.size,
            isImage: fileInfo.isImage,
            preview: fileInfo.preview
          });
        }
      }
    }
  });
}

// Lightbox Modal event handlers
if (lightboxBackdrop) lightboxBackdrop.addEventListener('click', closeLightbox);
if (lightboxCloseBtn) lightboxCloseBtn.addEventListener('click', closeLightbox);
if (lightboxOpenExternalBtn) {
  lightboxOpenExternalBtn.addEventListener('click', () => {
    if (currentLightboxPath && window.harness && window.harness.openFile) {
      window.harness.openFile(currentLightboxPath);
    }
  });
}

// Suggestion card clicks
document.querySelectorAll('.suggestion-card').forEach(card => {
  card.addEventListener('click', () => {
    const prompt = card.getAttribute('data-prompt');
    if (prompt) {
      userInput.value = prompt;
      handleSend();
    }
  });
});

// Segmented Control (Mode Switcher)
segButtons.forEach(btn => {
  btn.addEventListener('click', () => {
    segButtons.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const mode = btn.getAttribute('data-mode');
    currentActiveMode = mode;
    window.harness.switchProfile(mode);
  });
});

// Reasoning Steps Select
stepsInput.addEventListener('change', () => {
  const steps = parseInt(stepsInput.value, 10);
  window.harness.setSteps(steps);
});

// Helper to derive a clean session title from first prompt
function deriveTitle(text) {
  if (!text) return "Conversation";
  let firstLine = text.trim().split('\n')[0].trim();
  firstLine = firstLine.replace(/^[#\-*`>\s]+/, '').trim();
  if (firstLine.length > 40) {
    firstLine = firstLine.substring(0, 37).trim() + '...';
  }
  return firstLine || "Conversation";
}

// Session & Conversation Management
function startNewConversation() {
  if (isGenerating) {
    handleStop();
  }
  if (typewriterTimer) {
    clearInterval(typewriterTimer);
    typewriterTimer = null;
  }
  stopThinking();
  stopTurnTimer();
  currentSessionId = null;
  currentSessionTitle = "New Conversation";
  currentSessionMessages = [];
  currentAgentMessageEl = null;
  currentTraceGroup = null;
  currentTraceContainer = null;
  currentTraceBody = null;
  currentTracePillLabel = null;
  currentTurnStartTime = null;
  currentMarkdownBody = null;
  activeToolCalls = [];

  if (window.harness && window.harness.clearHistory) {
    window.harness.clearHistory();
  }

  messagesList.innerHTML = '';
  if (welcomeHero) welcomeHero.style.display = 'flex';
  closeInspector();
  updateActiveSessionHighlight();
  setGenerating(false);
  persistLastActiveState();
}

// Clear conversation history button
clearBtn.addEventListener('click', () => {
  startNewConversation();
});

// Format relative time for sessions
function formatTime(timestamp) {
  if (!timestamp) return '';
  const now = Date.now() / 1000;
  const diff = Math.floor(now - timestamp);
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  const d = new Date(timestamp * 1000);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

// Last active workspace & session state persistence in localStorage
function persistLastActiveState() {
  try {
    if (currentWorkspacePath) {
      localStorage.setItem('harness_last_workspace', currentWorkspacePath);
    }
    if (currentSessionId) {
      localStorage.setItem('harness_last_session_id', currentSessionId);
    } else {
      localStorage.removeItem('harness_last_session_id');
    }
  } catch (e) {}
}

window.addEventListener('beforeunload', persistLastActiveState);

let initialRestoreAttempted = false;
function tryRestoreLastSession() {
  if (initialRestoreAttempted) return;

  try {
    const lastWorkspace = localStorage.getItem('harness_last_workspace');
    const lastSessionId = localStorage.getItem('harness_last_session_id');

    if (!lastWorkspace && !lastSessionId) return;
    initialRestoreAttempted = true;

    if (lastWorkspace) {
      if (lastSessionId && window.harness && window.harness.loadSession) {
        window.harness.loadSession(lastWorkspace, lastSessionId);
      } else if (window.harness && window.harness.setWorkspace) {
        if (!currentWorkspacePath || currentWorkspacePath.toLowerCase() !== lastWorkspace.toLowerCase()) {
          window.harness.setWorkspace(lastWorkspace);
        }
      }
    }
  } catch (e) {
    console.error('Failed to restore last active session state:', e);
  }
}

// Collapsed project groups state in localStorage
function getCollapsedProjects() {
  try {
    const raw = localStorage.getItem('harness_collapsed_projects');
    return new Set(raw ? JSON.parse(raw) : []);
  } catch {
    return new Set();
  }
}

function setProjectCollapsedState(projectPath, collapsed) {
  try {
    const set = getCollapsedProjects();
    const norm = (projectPath || '').toLowerCase();
    if (collapsed) {
      set.add(norm);
    } else {
      set.delete(norm);
    }
    localStorage.setItem('harness_collapsed_projects', JSON.stringify(Array.from(set)));
  } catch {}
}

// Render projects and sessions tree
function renderProjectsTree(projects) {
  if (!projectsTree) return;
  registeredProjects = projects || [];
  const savedScrollTop = projectsTree.scrollTop;
  const collapsedSet = getCollapsedProjects();
  projectsTree.innerHTML = '';

  if (registeredProjects.length === 0) {
    const emptyDiv = document.createElement('div');
    emptyDiv.className = 'empty-sessions-label';
    emptyDiv.textContent = 'No projects registered yet.';
    projectsTree.appendChild(emptyDiv);
    return;
  }

  registeredProjects.forEach((proj) => {
    const isCurrentProject = currentWorkspacePath &&
      (proj.path === currentWorkspacePath || proj.path.toLowerCase() === currentWorkspacePath.toLowerCase());
    const isCollapsed = !isCurrentProject && collapsedSet.has((proj.path || '').toLowerCase());

    const group = document.createElement('div');
    group.className = `project-group ${isCollapsed ? 'collapsed' : 'expanded'}`;

    // Header
    const header = document.createElement('div');
    header.className = `project-group-header ${isCurrentProject ? 'active' : ''}`;
    header.title = proj.path;

    const leftDiv = document.createElement('div');
    leftDiv.className = 'project-group-left';
    leftDiv.innerHTML = `
      <svg class="project-chevron" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <polyline points="9 18 15 12 9 6"></polyline>
      </svg>
      <svg class="project-folder-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
      </svg>
      <span class="project-group-title">${escapeHtml(proj.name || 'project')}</span>
    `;

    // Clicking chevron toggles expand/collapse without switching workspace
    const chevronEl = leftDiv.querySelector('.project-chevron');
    chevronEl.addEventListener('click', (e) => {
      e.stopPropagation();
      const willCollapse = !group.classList.contains('collapsed');
      group.classList.toggle('collapsed', willCollapse);
      group.classList.toggle('expanded', !willCollapse);
      setProjectCollapsedState(proj.path, willCollapse);
    });

    const rightDiv = document.createElement('div');
    rightDiv.className = 'project-group-right';

    const countSpan = document.createElement('span');
    countSpan.className = 'project-group-count';
    countSpan.textContent = proj.sessions ? proj.sessions.length : 0;
    rightDiv.appendChild(countSpan);

    const unpinBtn = document.createElement('button');
    unpinBtn.className = 'project-unpin-btn';
    unpinBtn.title = 'Remove project from recent list';
    unpinBtn.innerHTML = `
      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
        <line x1="18" y1="6" x2="6" y2="18"></line>
        <line x1="6" y1="6" x2="18" y2="18"></line>
      </svg>
    `;
    unpinBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      if (confirm(`Remove "${proj.name || proj.path}" from recent projects list?`)) {
        if (window.harness && window.harness.unregisterProject) {
          window.harness.unregisterProject(proj.path);
        }
      }
    });
    rightDiv.appendChild(unpinBtn);

    header.appendChild(leftDiv);
    header.appendChild(rightDiv);

    header.addEventListener('click', () => {
      if (!isCurrentProject) {
        group.classList.remove('collapsed');
        group.classList.add('expanded');
        setProjectCollapsedState(proj.path, false);
        window.harness.setWorkspace(proj.path);
      } else {
        // Toggle collapse on click of active project header
        const willCollapse = !group.classList.contains('collapsed');
        group.classList.toggle('collapsed', willCollapse);
        group.classList.toggle('expanded', !willCollapse);
        setProjectCollapsedState(proj.path, willCollapse);
      }
    });

    group.appendChild(header);

    // Sessions List
    const sessList = document.createElement('div');
    sessList.className = 'project-sessions-list';

    if (proj.sessions && proj.sessions.length > 0) {
      proj.sessions.forEach((s) => {
        const item = document.createElement('div');
        item.className = `session-item ${s.id === currentSessionId ? 'active' : ''}`;
        item.setAttribute('data-session-id', s.id);
        item.setAttribute('data-project-path', proj.path);

        const content = document.createElement('div');
        content.className = 'session-item-content';
        content.innerHTML = `
          <span class="session-item-title" title="${escapeHtml(s.title || 'Conversation')}">${escapeHtml(s.title || 'Conversation')}</span>
          <span class="session-item-time">${formatTime(s.updated_at || s.created_at)}</span>
        `;

        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'session-actions';

        const renameBtn = document.createElement('button');
        renameBtn.className = 'session-action-btn';
        renameBtn.title = 'Rename conversation';
        renameBtn.innerHTML = `
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 20h9"></path>
            <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
          </svg>
        `;

        // Modern inline renaming without modal prompt()
        renameBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          const titleSpan = content.querySelector('.session-item-title');
          if (!titleSpan || content.querySelector('.session-rename-input')) return;

          const oldTitle = s.title || 'Conversation';
          const input = document.createElement('input');
          input.type = 'text';
          input.className = 'session-rename-input';
          input.value = oldTitle;
          titleSpan.style.display = 'none';
          content.insertBefore(input, titleSpan);
          input.focus();
          input.select();

          let committed = false;
          const finishRename = () => {
            if (committed) return;
            committed = true;
            const newTitle = input.value.trim();
            input.remove();
            titleSpan.style.display = '';
            if (newTitle && newTitle !== oldTitle) {
              titleSpan.textContent = newTitle;
              s.title = newTitle;
              if (currentSessionId === s.id) {
                currentSessionTitle = newTitle;
              }
              if (window.harness && window.harness.renameSession) {
                window.harness.renameSession(proj.path, s.id, newTitle);
              }
            }
          };

          input.addEventListener('keydown', (ev) => {
            if (ev.key === 'Enter') {
              ev.preventDefault();
              ev.stopPropagation();
              finishRename();
            } else if (ev.key === 'Escape') {
              ev.preventDefault();
              ev.stopPropagation();
              committed = true;
              input.remove();
              titleSpan.style.display = '';
            }
          });

          input.addEventListener('blur', finishRename);
          input.addEventListener('click', (ev) => ev.stopPropagation());
        });

        const delBtn = document.createElement('button');
        delBtn.className = 'session-action-btn delete';
        delBtn.title = 'Delete conversation';
        delBtn.innerHTML = `
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        `;
        delBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          if (confirm(`Delete conversation "${s.title || 'Conversation'}"?`)) {
            window.harness.deleteSession(proj.path, s.id);
            if (currentSessionId === s.id) {
              startNewConversation();
            }
          }
        });

        actionsDiv.appendChild(renameBtn);
        actionsDiv.appendChild(delBtn);

        item.appendChild(content);
        item.appendChild(actionsDiv);

        item.addEventListener('click', () => {
          if (currentSessionId === s.id) return;
          if (isGenerating) handleStop();
          window.harness.loadSession(proj.path, s.id);
        });

        sessList.appendChild(item);
      });
    } else {
      const noSess = document.createElement('div');
      noSess.className = 'empty-sessions-label';
      noSess.textContent = 'No past conversations';
      sessList.appendChild(noSess);
    }

    group.appendChild(sessList);
    projectsTree.appendChild(group);
  });

  // Restore scroll position
  projectsTree.scrollTop = savedScrollTop;
}

function updateActiveSessionHighlight() {
  if (!projectsTree) return;
  const items = projectsTree.querySelectorAll('.session-item');
  items.forEach(el => {
    const sId = el.getAttribute('data-session-id');
    if (sId && sId === currentSessionId) {
      el.classList.add('active');
    } else {
      el.classList.remove('active');
    }
  });
}

// Helper: safely parse tool arguments
function parseToolArgs(rawArgs) {
  if (!rawArgs) return {};
  if (typeof rawArgs === 'object') return rawArgs;
  if (typeof rawArgs === 'string') {
    try {
      return JSON.parse(rawArgs);
    } catch {
      return { raw: rawArgs };
    }
  }
  return {};
}

// Format tool call arguments cleanly for trace display
function formatToolBrief(toolName, rawArgs) {
  const a = parseToolArgs(rawArgs);
  const name = toolName || '';

  if (name === 'write_file') {
    const file = a.filepath || a.path || 'file';
    const lines = a.content ? a.content.split('\n').length : 0;
    return `${file} (+${lines} lines)`;
  }
  if (name === 'replace_in_file') {
    const file = a.filepath || a.path || 'file';
    const tLines = a.target ? a.target.split('\n').length : 0;
    const rLines = a.replacement ? a.replacement.split('\n').length : 0;
    const diff = rLines - tLines;
    const sign = diff >= 0 ? `+${diff}` : `${diff}`;
    return `${file} (${sign} lines)`;
  }
  if (name === 'read_file' || name === 'open_file') {
    return a.filepath || a.path || '';
  }
  if (name === 'read_file_range') {
    const file = a.filepath || a.path || '';
    const start = a.start_line || 1;
    const end = a.end_line || 100;
    return `${file} (L${start}-${end})`;
  }
  if (name === 'powershell' || name === 'run_powershell' || name === 'run_background_process') {
    const cmd = (a.command || '').trim();
    return cmd.length > 55 ? cmd.substring(0, 55) + '...' : cmd;
  }
  if (name === 'stop_background_process') {
    return `PID: ${a.pid || ''}`;
  }
  if (name === 'run_python_code') {
    const code = (a.code || '').trim();
    const firstLine = code.split('\n')[0] || '';
    return firstLine.length > 55 ? firstLine.substring(0, 55) + '...' : (firstLine || 'python code');
  }
  if (name === 'web_search') {
    return a.query || '';
  }
  if (name === 'fetch_webpage') {
    return a.url || '';
  }
  if (name === 'find_files') {
    return a.name_pattern || a.pattern || '';
  }
  if (name === 'search_file_contents') {
    return a.query || a.pattern || '';
  }
  if (name === 'download_file') {
    return a.destination_path || a.save_as || a.url || '';
  }
  if (name === 'create_project') {
    return `${a.project_name || 'project'} (${a.template || 'python'})`;
  }
  if (name === 'set_workspace') {
    return a.directory_path || '';
  }
  if (name === 'git_status') {
    return a.repo_dir && a.repo_dir !== '.' ? a.repo_dir : '';
  }
  if (name === 'git_diff') {
    return a.cached ? 'cached' : (a.path || '');
  }
  if (name === 'git_commit_and_push') {
    return a.message ? `"${a.message}"` : '';
  }
  if (name === 'git_remote_add') {
    return `${a.remote_name || 'origin'} ${a.remote_url || ''}`;
  }
  if (name === 'git_init') {
    return a.repo_dir && a.repo_dir !== '.' ? a.repo_dir : '';
  }
  if (name === 'github_create_repo') {
    return a.repo_name || '';
  }
  if (name === 'github_repo_info') {
    return '';
  }
  if (name === 'copy_file') {
    return `${a.src || ''} -> ${a.dest || ''}`;
  }
  if (name === 'move_file') {
    return `${a.src || ''} -> ${a.dest || ''}`;
  }
  if (name === 'delete_file') {
    return a.path || a.filepath || '';
  }

  if (a.command) return a.command.length > 55 ? a.command.substring(0, 55) + '...' : a.command;
  if (a.path) return a.path;
  if (a.filepath) return a.filepath;
  if (a.query) return a.query;
  if (a.expression) return a.expression;

  let s = typeof rawArgs === 'string' ? rawArgs : JSON.stringify(a);
  if (s === '{}' || s === '""') return '';
  return s.length > 55 ? s.substring(0, 55) + '...' : s;
}

// Collect file changes across tools in a turn
function collectFileChanges(toolsList) {
  if (!toolsList || toolsList.length === 0) return [];
  const fileMap = new Map();

  toolsList.forEach(t => {
    const a = parseToolArgs(t.args);
    if (t.name === 'write_file') {
      const file = a.filepath || a.path;
      if (file) {
        const lines = a.content ? a.content.split('\n').length : 0;
        fileMap.set(file, {
          filepath: file,
          added: lines,
          deleted: 0,
          toolCall: t
        });
      }
    } else if (t.name === 'replace_in_file') {
      const file = a.filepath || a.path;
      if (file) {
        const tLines = a.target ? a.target.split('\n').length : 0;
        const rLines = a.replacement ? a.replacement.split('\n').length : 0;
        const prev = fileMap.get(file) || { filepath: file, added: 0, deleted: 0, toolCall: t };
        prev.added += rLines;
        prev.deleted += tLines;
        prev.toolCall = t;
        fileMap.set(file, prev);
      }
    } else if (t.name === 'create_project') {
      const pName = a.project_name || 'project';
      const file = `${pName}/README.md`;
      fileMap.set(file, {
        filepath: file,
        added: 3,
        deleted: 0,
        toolCall: t
      });
    }
  });

  return Array.from(fileMap.values());
}

// Build Antigravity File Changes Card Widget
function createChangesBanner(toolsList) {
  const changes = collectFileChanges(toolsList);
  if (changes.length === 0) return null;

  let totalAdded = 0;
  let totalDeleted = 0;
  changes.forEach(c => {
    totalAdded += c.added;
    totalDeleted += c.deleted;
  });

  const banner = document.createElement('div');
  banner.className = 'changes-banner-card';

  const fileText = changes.length === 1 ? '1 file changed' : `${changes.length} files changed`;

  let statsHtml = `<span class="changes-stat-add">+${totalAdded}</span>`;
  if (totalDeleted > 0) {
    statsHtml += `<span class="changes-stat-del">-${totalDeleted}</span>`;
  }

  const header = document.createElement('div');
  header.className = 'changes-banner-header';
  header.innerHTML = `
    <div class="changes-banner-left">
      <span class="changes-banner-title">${fileText}</span>
      ${statsHtml}
      <svg class="changes-chevron" viewBox="0 0 24 24" fill="none" stroke-width="2.5">
        <polyline points="9 18 15 12 9 6"></polyline>
      </svg>
    </div>
    <button class="changes-review-btn" type="button" title="Review modified files">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke-width="2">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
        <polyline points="14 2 14 8 20 8"></polyline>
        <line x1="16" y1="13" x2="8" y2="13"></line>
        <line x1="16" y1="17" x2="8" y2="17"></line>
        <polyline points="10 9 9 9 8 9"></polyline>
      </svg>
      <span>Review</span>
    </button>
  `;

  const filesList = document.createElement('div');
  filesList.className = 'changes-files-list';

  changes.forEach(item => {
    const row = document.createElement('div');
    row.className = 'changes-file-row';

    let fileStats = `<span class="changes-stat-add">+${item.added}</span>`;
    if (item.deleted > 0) {
      fileStats += `<span class="changes-stat-del">-${item.deleted}</span>`;
    }

    row.innerHTML = `
      <div class="changes-file-left">
        <svg class="changes-file-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke-width="2">
          <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path>
          <polyline points="13 2 13 9 20 9"></polyline>
        </svg>
        <span class="changes-file-name">${escapeHtml(item.filepath)}</span>
      </div>
      <div class="changes-file-stats">
        ${fileStats}
      </div>
    `;

    row.addEventListener('click', (e) => {
      e.stopPropagation();
      openInspector(item.toolCall);
    });

    filesList.appendChild(row);
  });

  header.addEventListener('click', (e) => {
    if (e.target.closest('.changes-review-btn')) return;
    banner.classList.toggle('open');
  });

  const reviewBtn = header.querySelector('.changes-review-btn');
  if (reviewBtn && changes.length > 0) {
    reviewBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      openInspector(changes[0].toolCall);
    });
  }

  banner.appendChild(header);
  banner.appendChild(filesList);
  return banner;
}

// -------------------------------------------------------------
// Antigravity Chunking & Duration Engine
// -------------------------------------------------------------
function formatDuration(ms) {
  const totalSec = Math.max(1, Math.round(ms / 1000));
  if (totalSec < 60) {
    return `${totalSec}s`;
  }
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  if (sec === 0) {
    return `${min}m`;
  }
  return `${min}m ${sec}s`;
}

function startTurnTimer(pillLabelEl) {
  stopTurnTimer();
  currentTurnStartTime = Date.now();
  const update = () => {
    if (!pillLabelEl) return;
    const elapsed = Date.now() - currentTurnStartTime;
    pillLabelEl.textContent = `Worked for ${formatDuration(elapsed)}`;
  };
  update();
  currentTurnDurationTimer = setInterval(update, 1000);
}

function stopTurnTimer() {
  if (currentTurnDurationTimer) {
    clearInterval(currentTurnDurationTimer);
    currentTurnDurationTimer = null;
  }
}

const EXPLORATION_TOOLS = new Set([
  'read_file',
  'read_file_range',
  'read_document',
  'search_file_contents',
  'find_files',
  'list_directory',
  'get_workspace',
  'list_projects',
  'get_file_tree',
  'read_symbol'
]);

const EDIT_TOOLS = new Set([
  'replace_in_file',
  'write_file',
  'create_file',
  'create_project',
  'copy_file',
  'move_file',
  'delete_file'
]);

const GIT_TOOLS = new Set([
  'git_status',
  'git_diff',
  'git_init',
  'git_remote_add',
  'git_commit_and_push',
  'github_create_repo',
  'github_repo_info'
]);

const COMMAND_TOOLS = new Set([
  'powershell',
  'run_powershell',
  'run_command',
  'run_background_process',
  'stop_background_process',
  'list_background_processes'
]);

const WEB_TOOLS = new Set([
  'web_search',
  'fetch_webpage',
  'browse_url'
]);

function getLanguageBadgeInfo(filepath) {
  if (!filepath) return { ext: 'txt', label: 'txt', className: 'badge-default' };
  const cleanPath = filepath.split('?')[0].split('#')[0];
  const parts = cleanPath.split('.');
  const ext = parts.length > 1 ? parts[parts.length - 1].toLowerCase() : 'txt';

  switch (ext) {
    case 'js':
    case 'mjs':
    case 'cjs':
      return { ext: 'js', label: 'js', className: 'badge-js' };
    case 'jsx':
      return { ext: 'jsx', label: 'jsx', className: 'badge-js' };
    case 'ts':
      return { ext: 'ts', label: 'ts', className: 'badge-ts' };
    case 'tsx':
      return { ext: 'tsx', label: 'tsx', className: 'badge-ts' };
    case 'py':
    case 'pyw':
      return { ext: 'py', label: 'py', className: 'badge-py' };
    case 'css':
    case 'scss':
    case 'sass':
    case 'less':
      return { ext: 'css', label: 'css', className: 'badge-css' };
    case 'html':
    case 'htm':
      return { ext: 'html', label: 'html', className: 'badge-html' };
    case 'json':
      return { ext: 'json', label: 'json', className: 'badge-json' };
    case 'md':
    case 'markdown':
      return { ext: 'md', label: 'md', className: 'badge-md' };
    case 'sh':
    case 'bash':
    case 'ps1':
      return { ext: 'sh', label: 'sh', className: 'badge-sh' };
    default:
      return { ext: ext.substring(0, 4), label: ext.substring(0, 4), className: 'badge-default' };
  }
}

function getBasename(pathStr) {
  if (!pathStr) return 'file';
  const norm = pathStr.replace(/\\/g, '/');
  const segments = norm.split('/').filter(Boolean);
  return segments[segments.length - 1] || pathStr;
}

function computeToolDiff(tool) {
  const args = parseToolArgs(tool.args);
  if (tool.name === 'write_file') {
    const lines = args.content ? args.content.split('\n').length : 0;
    return { added: lines, deleted: 0 };
  }
  if (tool.name === 'replace_in_file') {
    const tLines = args.target ? args.target.split('\n').length : 0;
    const rLines = args.replacement ? args.replacement.split('\n').length : 0;
    return { added: rLines, deleted: tLines };
  }
  if (tool.name === 'create_project') {
    return { added: 5, deleted: 0 };
  }
  return { added: 0, deleted: 0 };
}

function groupToolCallsIntoChunks(toolsList) {
  if (!toolsList || toolsList.length === 0) return [];

  const chunks = [];
  let currentExploreChunk = null;
  let currentWebChunk = null;

  function flushExplore() {
    if (currentExploreChunk) {
      chunks.push(currentExploreChunk);
      currentExploreChunk = null;
    }
  }

  function flushWeb() {
    if (currentWebChunk) {
      chunks.push(currentWebChunk);
      currentWebChunk = null;
    }
  }

  toolsList.forEach((t) => {
    const name = t.name;

    if (EXPLORATION_TOOLS.has(name)) {
      flushWeb();
      if (!currentExploreChunk) {
        currentExploreChunk = {
          type: 'explore',
          files: new Set(),
          searchCount: 0,
          items: []
        };
      }
      currentExploreChunk.items.push(t);
      const args = parseToolArgs(t.args);
      if (name === 'read_file' || name === 'read_file_range' || name === 'read_document') {
        const f = args.filepath || args.path;
        if (f) currentExploreChunk.files.add(f);
      } else if (name === 'search_file_contents' || name === 'find_files') {
        currentExploreChunk.searchCount++;
      }
      return;
    }

    flushExplore();

    if (WEB_TOOLS.has(name)) {
      if (!currentWebChunk) {
        currentWebChunk = {
          type: 'web',
          count: 0,
          items: []
        };
      }
      currentWebChunk.count++;
      currentWebChunk.items.push(t);
      return;
    }

    flushWeb();

    if (EDIT_TOOLS.has(name)) {
      const args = parseToolArgs(t.args);
      const filepath = args.filepath || args.path || (name === 'create_project' ? `${args.project_name || 'project'}/README.md` : 'file');
      const basename = getBasename(filepath);
      const badgeInfo = getLanguageBadgeInfo(filepath);
      const diff = computeToolDiff(t);

      chunks.push({
        type: 'edit',
        tool: t,
        filepath: filepath,
        basename: basename,
        badgeInfo: badgeInfo,
        added: diff.added,
        deleted: diff.deleted
      });
      return;
    }

    if (COMMAND_TOOLS.has(name)) {
      const args = parseToolArgs(t.args);
      const cmd = (args.command || '').trim();
      chunks.push({
        type: 'command',
        tool: t,
        command: cmd,
        isDaemon: name === 'run_background_process'
      });
      return;
    }

    if (GIT_TOOLS.has(name)) {
      chunks.push({
        type: 'git',
        tool: t
      });
      return;
    }

    chunks.push({
      type: 'generic',
      tool: t
    });
  });

  flushExplore();
  flushWeb();

  return chunks;
}

function renderTraceChunks(container, toolsList) {
  if (!container) return;
  container.innerHTML = '';
  const chunks = groupToolCallsIntoChunks(toolsList);

  chunks.forEach(chunk => {
    if (chunk.type === 'explore') {
      const row = document.createElement('div');
      row.className = 'chunk-row chunk-explore-row';

      const fileCount = chunk.files.size;
      const searchCount = chunk.searchCount;
      let label = '';
      if (fileCount > 0 && searchCount > 0) {
        label = `Explored ${fileCount} file${fileCount > 1 ? 's' : ''}, ${searchCount} search${searchCount > 1 ? 'es' : ''}`;
      } else if (fileCount > 0) {
        label = `Explored ${fileCount} file${fileCount > 1 ? 's' : ''}`;
      } else if (searchCount > 0) {
        label = `Explored ${searchCount} search${searchCount > 1 ? 'es' : ''}`;
      } else {
        label = `Explored workspace`;
      }

      row.innerHTML = `
        <div class="chunk-row-header">
          <span class="chunk-explore-text">${escapeHtml(label)}</span>
          <svg class="chunk-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="9 18 15 12 9 6"></polyline>
          </svg>
        </div>
        <div class="chunk-sub-items" style="display: none;"></div>
      `;

      const subItemsContainer = row.querySelector('.chunk-sub-items');
      chunk.items.forEach(toolCall => {
        const subItem = document.createElement('div');
        subItem.className = 'chunk-sub-item';
        const briefArgs = formatToolBrief(toolCall.name, toolCall.args);
        subItem.innerHTML = `
          <span class="chunk-sub-marker">${SVG_CHECK}</span>
          <span class="chunk-sub-name">${escapeHtml(toolCall.name)}</span>
          <span class="chunk-sub-args">${escapeHtml(briefArgs)}</span>
        `;
        subItem.addEventListener('click', (e) => {
          e.stopPropagation();
          openInspector(toolCall);
        });
        subItemsContainer.appendChild(subItem);
      });

      row.querySelector('.chunk-row-header').addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = row.classList.toggle('open');
        subItemsContainer.style.display = isOpen ? 'flex' : 'none';
      });

      container.appendChild(row);
    }

    else if (chunk.type === 'edit') {
      const row = document.createElement('div');
      row.className = 'chunk-row chunk-edit-row';
      row.innerHTML = `
        <div class="chunk-edit-left">
          <span class="chunk-action-label">Edited</span>
          <span class="chunk-badge ${chunk.badgeInfo.className}">${chunk.badgeInfo.label}</span>
          <span class="chunk-filename" title="${escapeHtml(chunk.filepath)}">${escapeHtml(chunk.basename)}</span>
          <div class="chunk-diff-stats">
            <span class="chunk-stat-add">+${chunk.added}</span>
            <span class="chunk-stat-del">-${chunk.deleted}</span>
          </div>
        </div>
        <span class="chunk-row-arrow">${SVG_ARROW}</span>
      `;

      row.addEventListener('click', (e) => {
        e.stopPropagation();
        openInspector(chunk.tool);
      });

      container.appendChild(row);
    }

    else if (chunk.type === 'command') {
      const row = document.createElement('div');
      row.className = 'chunk-row chunk-command-row';
      const badgeClass = chunk.isDaemon ? 'badge-daemon' : 'badge-sh';
      const badgeLabel = chunk.isDaemon ? 'daemon' : 'sh';
      const cmdShort = chunk.command.length > 50 ? chunk.command.substring(0, 50) + '...' : chunk.command;

      row.innerHTML = `
        <div class="chunk-cmd-left">
          <span class="chunk-action-label">${chunk.isDaemon ? 'Started' : 'Ran'}</span>
          <span class="chunk-badge ${badgeClass}">${badgeLabel}</span>
          <span class="chunk-command-text" title="${escapeHtml(chunk.command)}">${escapeHtml(cmdShort)}</span>
        </div>
        <svg class="chunk-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="9 18 15 12 9 6"></polyline>
        </svg>
      `;

      row.addEventListener('click', (e) => {
        e.stopPropagation();
        openInspector(chunk.tool);
      });

      container.appendChild(row);
    }

    else if (chunk.type === 'web') {
      const row = document.createElement('div');
      row.className = 'chunk-row chunk-explore-row';
      const label = `Searched ${chunk.count} web page${chunk.count > 1 ? 's' : ''}`;

      row.innerHTML = `
        <div class="chunk-row-header">
          <span class="chunk-explore-text">${escapeHtml(label)}</span>
          <svg class="chunk-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="9 18 15 12 9 6"></polyline>
          </svg>
        </div>
        <div class="chunk-sub-items" style="display: none;"></div>
      `;

      const subItemsContainer = row.querySelector('.chunk-sub-items');
      chunk.items.forEach(toolCall => {
        const subItem = document.createElement('div');
        subItem.className = 'chunk-sub-item';
        const briefArgs = formatToolBrief(toolCall.name, toolCall.args);
        subItem.innerHTML = `
          <span class="chunk-sub-marker">${SVG_CHECK}</span>
          <span class="chunk-sub-name">${escapeHtml(toolCall.name)}</span>
          <span class="chunk-sub-args">${escapeHtml(briefArgs)}</span>
        `;
        subItem.addEventListener('click', (e) => {
          e.stopPropagation();
          openInspector(toolCall);
        });
        subItemsContainer.appendChild(subItem);
      });

      row.querySelector('.chunk-row-header').addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = row.classList.toggle('open');
        subItemsContainer.style.display = isOpen ? 'flex' : 'none';
      });

      container.appendChild(row);
    }

    else if (chunk.type === 'git') {
      const row = document.createElement('div');
      row.className = 'chunk-row chunk-git-row';
      const brief = formatToolBrief(chunk.tool.name, chunk.tool.args);
      row.innerHTML = `
        <div class="chunk-generic-left">
          <span class="chunk-action-label">Git</span>
          <span class="chunk-badge badge-git">git</span>
          <span class="chunk-generic-name">${escapeHtml(chunk.tool.name)}</span>
          <span class="chunk-generic-args">${escapeHtml(brief)}</span>
        </div>
        <span class="chunk-row-arrow">${SVG_ARROW}</span>
      `;
      row.addEventListener('click', (e) => {
        e.stopPropagation();
        openInspector(chunk.tool);
      });
      container.appendChild(row);
    }

    else if (chunk.type === 'generic') {
      const row = document.createElement('div');
      row.className = 'chunk-row chunk-generic-row';
      const brief = formatToolBrief(chunk.tool.name, chunk.tool.args);
      row.innerHTML = `
        <div class="chunk-generic-left">
          <span class="chunk-action-label">Called</span>
          <span class="chunk-generic-name">${escapeHtml(chunk.tool.name)}</span>
          <span class="chunk-generic-args">${escapeHtml(brief)}</span>
        </div>
        <span class="chunk-row-arrow">${SVG_ARROW}</span>
      `;
      row.addEventListener('click', (e) => {
        e.stopPropagation();
        openInspector(chunk.tool);
      });
      container.appendChild(row);
    }
  });
}

function createTraceWidget(toolsList, durationStr = null, initiallyOpen = false) {
  const container = document.createElement('div');
  container.className = `trace-pill-container ${initiallyOpen ? 'open' : ''}`;

  const duration = durationStr || (toolsList && toolsList.length > 0 ? formatDuration(toolsList.length * 1800) : '1s');

  const btn = document.createElement('button');
  btn.className = 'trace-pill-btn';
  btn.type = 'button';
  btn.title = 'Toggle tool execution trace';
  btn.innerHTML = `
    <span class="trace-pill-label">Worked for ${duration}</span>
    <svg class="trace-pill-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <polyline points="6 9 12 15 18 9"></polyline>
    </svg>
  `;

  btn.addEventListener('click', () => {
    container.classList.toggle('open');
  });

  const body = document.createElement('div');
  body.className = 'trace-chunks-body';

  if (toolsList && toolsList.length > 0) {
    renderTraceChunks(body, toolsList);
  }

  container.appendChild(btn);
  container.appendChild(body);
  return container;
}

function renderRestoredMessage(msg) {
  if (!msg) return;

  if (msg.role === 'user') {
    appendUserMessage(msg.content || '', msg.attachments || []);
    return;
  }

  // Agent message
  const row = document.createElement('div');
  row.className = 'message-row agent';

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';

  if (msg.tools && msg.tools.length > 0) {
    const traceWidget = createTraceWidget(msg.tools, msg.duration, false);
    bubble.appendChild(traceWidget);

    const changesBanner = createChangesBanner(msg.tools);
    if (changesBanner) {
      bubble.appendChild(changesBanner);
    }
  }

  // Markdown body
  const mdEl = document.createElement('div');
  mdEl.className = 'markdown-body';
  if (typeof marked !== 'undefined') {
    mdEl.innerHTML = marked.parse(msg.content || '');
  } else {
    mdEl.textContent = msg.content || '';
  }
  attachCodeCopyButtons(mdEl);
  bubble.appendChild(mdEl);

  row.appendChild(bubble);
  messagesList.appendChild(row);
}

// Inspector Close Handlers
closeInspectorBtn.addEventListener('click', closeInspector);
window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    if (imageLightbox && imageLightbox.style.display !== 'none') {
      closeLightbox();
      return;
    }
    if (isGenerating) {
      handleStop();
      return;
    }
    if (inspectorPanel && inspectorPanel.style.display !== 'none') {
      closeInspector();
    }
  }
});

// Resizable Handle for Inspector Panel
if (inspectorResizer) {
  let isResizing = false;

  inspectorResizer.addEventListener('mousedown', (e) => {
    e.preventDefault();
    isResizing = true;
    inspectorResizer.classList.add('resizing');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    const onMouseMove = (moveEvent) => {
      if (!isResizing) return;
      const newWidth = window.innerWidth - moveEvent.clientX;
      const clampedWidth = Math.max(260, Math.min(newWidth, window.innerWidth * 0.85));
      inspectorPanel.style.width = clampedWidth + 'px';
    };

    const onMouseUp = () => {
      isResizing = false;
      inspectorResizer.classList.remove('resizing');
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
  });
}

// Copy button helpers
setupCopyButton(copyArgsBtn, () => inspectorArgsCode.textContent);
setupCopyButton(copyOutputBtn, () => inspectorOutputCode.textContent);

function setupCopyButton(btn, textGetter) {
  btn.addEventListener('click', () => {
    const text = textGetter();
    navigator.clipboard.writeText(text).then(() => {
      const orig = btn.textContent;
      btn.textContent = 'copied!';
      btn.style.borderColor = 'var(--accent-claude)';
      setTimeout(() => {
        btn.textContent = orig;
        btn.style.borderColor = '';
      }, 1500);
    });
  });
}

function openInspector(toolCall) {
  if (!toolCall) return;

  inspectedTaskId = null;
  inspectorToolName.textContent = toolCall.name;
  inspectorStatus.textContent = toolCall.status || 'completed';
  if (toolCall.status === 'running') {
    inspectorStatus.className = 'inspector-badge running';
  } else {
    inspectorStatus.className = 'inspector-badge';
  }

  const args = parseToolArgs(toolCall.args);
  const titleEl = document.getElementById('inspectorArgsTitle');

  inspectorArgsCode.className = 'inspector-code';

  if (toolCall.name === 'write_file') {
    const file = args.filepath || args.path || 'file';
    const lines = args.content ? args.content.split('\n').length : 0;
    if (titleEl) titleEl.textContent = `FILE CONTENT: ${file} (+${lines} lines)`;
    inspectorArgsCode.classList.add('file-content-view');
    inspectorArgsCode.textContent = args.content || '';
  } else if (toolCall.name === 'replace_in_file') {
    const file = args.filepath || args.path || 'file';
    const tLines = args.target ? args.target.split('\n').length : 0;
    const rLines = args.replacement ? args.replacement.split('\n').length : 0;
    const diff = rLines - tLines;
    const sign = diff >= 0 ? `+${diff}` : `${diff}`;
    if (titleEl) titleEl.textContent = `DIFF: ${file} (${sign} lines)`;
    inspectorArgsCode.classList.add('file-content-view');

    const searchLines = (args.target || '').split('\n');
    const replLines = (args.replacement || '').split('\n');

    let diffText = `--- SEARCH BLOCK (${tLines} lines):\n`;
    diffText += searchLines.map(l => `-  ${l}`).join('\n');
    diffText += `\n\n+++ REPLACEMENT BLOCK (${rLines} lines):\n`;
    diffText += replLines.map(l => `+  ${l}`).join('\n');

    inspectorArgsCode.textContent = diffText;
  } else if (toolCall.name === 'run_python_code') {
    if (titleEl) titleEl.textContent = 'PYTHON SCRIPT';
    inspectorArgsCode.classList.add('file-content-view');
    inspectorArgsCode.textContent = args.code || '';
  } else if (toolCall.name === 'powershell' || toolCall.name === 'run_powershell' || toolCall.name === 'run_background_process') {
    if (titleEl) titleEl.textContent = toolCall.name === 'run_background_process' ? 'BACKGROUND PROCESS COMMAND' : 'POWERSHELL COMMAND';
    inspectorArgsCode.textContent = args.command || '';
  } else if (toolCall.name.startsWith('git_') || toolCall.name.startsWith('github_')) {
    if (titleEl) titleEl.textContent = `GIT: ${toolCall.name.toUpperCase()}`;
    try {
      const formatted = typeof toolCall.args === 'string'
        ? JSON.stringify(JSON.parse(toolCall.args), null, 2)
        : JSON.stringify(toolCall.args, null, 2);
      inspectorArgsCode.textContent = formatted || '{}';
    } catch {
      inspectorArgsCode.textContent = String(toolCall.args || '{}');
    }
  } else {
    if (titleEl) titleEl.textContent = 'COMMAND / INPUT';
    try {
      const formatted = typeof toolCall.args === 'string'
        ? JSON.stringify(JSON.parse(toolCall.args), null, 2)
        : JSON.stringify(toolCall.args, null, 2);
      inspectorArgsCode.textContent = formatted || '{}';
    } catch {
      inspectorArgsCode.textContent = String(toolCall.args || '{}');
    }
  }

  if (toolCall.status === 'completed') {
    inspectorOutputCode.textContent = (toolCall.output !== '' && toolCall.output !== undefined && toolCall.output !== null)
      ? toolCall.output
      : '[Command completed with no output]';
  } else {
    inspectorOutputCode.textContent = toolCall.output || '[Waiting for execution output...]';
  }
  inspectorPanel.style.display = 'flex';

  if (currentActiveItemEl) {
    currentActiveItemEl.classList.remove('active');
  }
  if (toolCall.element) {
    toolCall.element.classList.add('active');
    currentActiveItemEl = toolCall.element;
  }
}

function closeInspector() {
  inspectorPanel.style.display = 'none';
  inspectedTaskId = null;
  if (currentActiveItemEl) {
    currentActiveItemEl.classList.remove('active');
    currentActiveItemEl = null;
  }
  if (tasksList) {
    tasksList.querySelectorAll('.task-item-row.active').forEach(el => el.classList.remove('active'));
  }
}

function openInspectorForTask(task) {
  if (!inspectorPanel) return;
  inspectedTaskId = task.pid;
  inspectorPanel.style.display = 'flex';
  inspectorToolName.textContent = `Process [PID ${task.pid}]`;
  inspectorStatus.textContent = task.status || 'running';
  inspectorStatus.className = 'inspector-badge running';

  const titleEl = document.getElementById('inspectorArgsTitle');
  if (titleEl) titleEl.textContent = 'PROCESS DETAILS';

  inspectorArgsCode.className = 'inspector-code';
  inspectorArgsCode.textContent = JSON.stringify({
    pid: task.pid,
    command: task.command,
    uptime: task.uptime,
    started_at: task.started_at,
    workspace: task.workspace
  }, null, 2);

  inspectorOutputCode.textContent = 'Loading process output...';

  if (currentActiveItemEl) {
    currentActiveItemEl.classList.remove('active');
    currentActiveItemEl = null;
  }

  if (tasksList) {
    tasksList.querySelectorAll('.task-item-row').forEach(el => {
      const isThis = el.getAttribute('data-pid') == String(task.pid);
      el.classList.toggle('active', isThis);
    });
  }

  if (window.harness && window.harness.getProcessOutput) {
    window.harness.getProcessOutput(task.pid);
  }
}

function renderBackgroundTasks(tasks) {
  activeBackgroundTasks = tasks || [];

  if (!tasksBarContainer || !tasksCountLabel || !tasksList) return;

  // Prune stoppingPids that no longer exist
  const activePids = new Set(activeBackgroundTasks.map(t => t.pid));
  for (const pid of stoppingPids) {
    if (!activePids.has(pid)) {
      stoppingPids.delete(pid);
    }
  }

  if (activeBackgroundTasks.length === 0) {
    tasksBarContainer.style.display = 'none';
    if (tasksBar) tasksBar.classList.remove('open');
    if (tasksDrawer) tasksDrawer.style.display = 'none';
    if (inspectedTaskId !== null) {
      if (inspectorPanel.style.display !== 'none' && inspectorToolName.textContent.includes(`[PID ${inspectedTaskId}]`)) {
        inspectorStatus.textContent = 'stopped';
        inspectorStatus.className = 'inspector-badge';
      }
    }
    return;
  }

  tasksBarContainer.style.display = 'block';
  const count = activeBackgroundTasks.length;
  tasksCountLabel.textContent = `${count} task${count > 1 ? 's' : ''} running`;

  tasksList.innerHTML = '';
  activeBackgroundTasks.forEach(task => {
    const row = document.createElement('div');
    row.className = 'task-item-row';
    row.setAttribute('data-pid', String(task.pid));
    if (inspectedTaskId === task.pid) {
      row.classList.add('active');
    }

    const isStopping = stoppingPids.has(task.pid);

    row.innerHTML = `
      <div class="task-item-main">
        <div class="task-item-command" title="${escapeHtml(task.command)}">${escapeHtml(task.command)}</div>
        <div class="task-item-meta">
          <span class="task-pill-pid">PID: ${task.pid}</span>
          <span class="task-pill-uptime">${escapeHtml(task.uptime || '0s')}</span>
          <span class="task-pill-start">started ${escapeHtml(task.started_at || '')}</span>
        </div>
      </div>
      <div class="task-actions">
        <button class="task-inspect-btn" title="Inspect output in drawer">Inspect</button>
        <button class="task-stop-btn" title="Terminate process immediately" ${isStopping ? 'disabled' : ''}>${isStopping ? 'Stopping...' : 'Stop'}</button>
      </div>
    `;

    const openInInspector = () => {
      openInspectorForTask(task);
    };

    row.addEventListener('click', (e) => {
      if (e.target.closest('.task-stop-btn')) return;
      openInInspector();
    });

    const inspectBtn = row.querySelector('.task-inspect-btn');
    inspectBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      openInInspector();
    });

    const stopBtn = row.querySelector('.task-stop-btn');
    stopBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      stoppingPids.add(task.pid);
      stopBtn.disabled = true;
      stopBtn.textContent = 'Stopping...';
      if (window.harness && window.harness.stopProcess) {
        window.harness.stopProcess(task.pid);
      }
    });

    tasksList.appendChild(row);
  });

  // If currently inspecting a task, update its status and metadata
  if (inspectedTaskId !== null && inspectorPanel.style.display !== 'none' && inspectorToolName.textContent.includes(`[PID ${inspectedTaskId}]`)) {
    const cur = activeBackgroundTasks.find(t => t.pid === inspectedTaskId);
    if (cur) {
      inspectorStatus.textContent = cur.status || 'running';
      inspectorStatus.className = 'inspector-badge running';
      inspectorArgsCode.textContent = JSON.stringify({
        pid: cur.pid,
        command: cur.command,
        uptime: cur.uptime,
        started_at: cur.started_at,
        workspace: cur.workspace
      }, null, 2);
    } else {
      inspectorStatus.textContent = 'stopped';
      inspectorStatus.className = 'inspector-badge';
    }
  }
}

let userScrolledUp = false;
let scrollRafId = null;

if (chatContainer) {
  chatContainer.addEventListener('scroll', () => {
    const distFromBottom = chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight;
    userScrolledUp = distFromBottom > 100;
  }, { passive: true });
}

function scrollToBottom(force = false) {
  if (!chatContainer) return;
  if (force) userScrolledUp = false;
  if (userScrolledUp && !force) return;
  if (scrollRafId) cancelAnimationFrame(scrollRafId);
  scrollRafId = requestAnimationFrame(() => {
    scrollRafId = null;
    if (chatContainer && (!userScrolledUp || force)) {
      chatContainer.scrollTop = chatContainer.scrollHeight;
    }
  });
}


// Thinking state & phrases
let thinkingInterval = null;
let currentThinkingEl = null;

const THINKING_PHRASES = [
  "Thinking...",
  "Analyzing request...",
  "Inspecting workspace...",
  "Planning next action...",
  "Evaluating approach...",
  "Formulating response..."
];

function startThinking(container, initialText = "Thinking...") {
  stopThinking();

  const thinkingEl = document.createElement('div');
  thinkingEl.className = 'thinking-status';
  thinkingEl.innerHTML = `<span class="thinking-text">${escapeHtml(initialText)}</span>`;
  container.appendChild(thinkingEl);
  currentThinkingEl = thinkingEl;

  let phraseIdx = 0;
  thinkingInterval = setInterval(() => {
    if (!currentThinkingEl) return;
    phraseIdx = (phraseIdx + 1) % THINKING_PHRASES.length;
    const textSpan = currentThinkingEl.querySelector('.thinking-text');
    if (textSpan) {
      textSpan.textContent = THINKING_PHRASES[phraseIdx];
    }
  }, 2200);
}

function updateThinking(text) {
  if (currentThinkingEl) {
    const textSpan = currentThinkingEl.querySelector('.thinking-text');
    if (textSpan) {
      textSpan.textContent = text;
    }
  }
}

function stopThinking() {
  if (thinkingInterval) {
    clearInterval(thinkingInterval);
    thinkingInterval = null;
  }
  if (currentThinkingEl) {
    currentThinkingEl.remove();
    currentThinkingEl = null;
  }
}

// Attach Copy buttons to all code blocks
function attachCodeCopyButtons(container) {
  if (!container) return;
  const pres = container.querySelectorAll('pre');
  pres.forEach(pre => {
    if (pre.querySelector('.code-copy-btn')) return;

    const btn = document.createElement('button');
    btn.className = 'code-copy-btn';
    btn.type = 'button';
    btn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg><span>Copy</span>`;

    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const code = pre.querySelector('code');
      const textToCopy = code ? code.innerText : pre.innerText;
      navigator.clipboard.writeText(textToCopy).then(() => {
        btn.innerHTML = `<span>Copied!</span>`;
        btn.classList.add('copied');
        setTimeout(() => {
          btn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg><span>Copy</span>`;
          btn.classList.remove('copied');
        }, 1500);
      });
    });

    pre.appendChild(btn);
  });
}

function handleSend() {
  const text = userInput.value.trim();
  const currentAttachments = [...stagedAttachments];
  if ((!text && currentAttachments.length === 0) || isGenerating) return;

  if (typewriterTimer) {
    clearInterval(typewriterTimer);
    typewriterTimer = null;
  }

  if (welcomeHero) welcomeHero.style.display = 'none';

  // Ensure active session exists
  if (!currentSessionId) {
    currentSessionId = 'sess_' + Date.now() + '_' + Math.random().toString(36).substring(2, 7);
    const titleSeed = text || (currentAttachments.length > 0 ? `Inspect ${currentAttachments[0].name}` : 'New Conversation');
    currentSessionTitle = deriveTitle(titleSeed);
    persistLastActiveState();
  }

  // Record user turn with timestamp and attachments
  currentSessionMessages.push({
    role: 'user',
    content: text,
    attachments: currentAttachments,
    timestamp: Date.now() / 1000
  });

  // Incrementally save immediately so prompt is never lost on crash or kill!
  if (currentWorkspacePath && currentSessionId) {
    window.harness.saveSession(
      currentWorkspacePath,
      currentSessionId,
      currentSessionTitle,
      currentSessionMessages,
      currentModelName,
      currentActiveMode
    );
  }

  appendUserMessage(text, currentAttachments);
  activeToolCalls = [];
  ensureAgentMessage();

  userInput.value = '';
  userInput.style.height = 'auto';
  stagedAttachments = [];
  renderStagedAttachments();
  setGenerating(true);

  window.harness.sendQuery(text, currentAttachments);
  scrollToBottom(true);
}

function handleStop() {
  if (!isGenerating) return;

  stopThinking();
  stopTurnTimer();
  if (typewriterTimer) {
    clearInterval(typewriterTimer);
    typewriterTimer = null;
  }

  if (window.harness && window.harness.abort) {
    window.harness.abort();
  }

  if (currentTracePillLabel) {
    const elapsed = Date.now() - (currentTurnStartTime || Date.now());
    currentTracePillLabel.textContent = `Stopped after ${formatDuration(elapsed)}`;
  }
  if (currentTraceContainer) {
    currentTraceContainer.classList.remove('open');
  }

  if (currentMarkdownBody) {
    const badge = document.createElement('div');
    badge.className = 'stopped-badge';
    badge.innerHTML = `${SVG_STOP_SQUARE}<span>Generation stopped by user</span>`;
    currentMarkdownBody.appendChild(badge);
  }

  // Preserve in session transcript
  if (currentWorkspacePath && currentSessionId) {
    const toolsSnapshot = activeToolCalls.map(t => ({
      name: t.name,
      args: t.args,
      output: t.output,
      status: t.status
    }));
    currentSessionMessages.push({
      role: 'agent',
      content: '[Generation stopped by user]',
      tools: toolsSnapshot,
      timestamp: Date.now() / 1000
    });
    window.harness.saveSession(
      currentWorkspacePath,
      currentSessionId,
      currentSessionTitle,
      currentSessionMessages,
      currentModelName,
      currentActiveMode
    );
  }

  setGenerating(false);
  scrollToBottom();
}

function setGenerating(generating) {
  isGenerating = generating;
  if (generating) {
    sendBtn.disabled = false;
    sendBtn.classList.add('stop-btn');
    sendBtn.title = 'Stop generation (Esc)';
    sendBtn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2" ry="2"></rect></svg>`;
  } else {
    sendBtn.disabled = false;
    sendBtn.classList.remove('stop-btn');
    sendBtn.title = 'Send (Enter)';
    sendBtn.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><line x1="12" y1="19" x2="12" y2="5"></line><polyline points="5 12 12 5 19 12"></polyline></svg>`;
  }
}

function appendUserMessage(text, attachments = []) {
  const row = document.createElement('div');
  row.className = 'message-row user';

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';

  if (attachments && attachments.length > 0) {
    const attContainer = document.createElement('div');
    attContainer.className = 'user-message-attachments';

    attachments.forEach(att => {
      if (att.isImage) {
        const imgWrap = document.createElement('div');
        imgWrap.className = 'user-att-image';
        imgWrap.title = `${att.name || 'Image'} (Click to view full size)`;

        const img = document.createElement('img');
        if (att.preview) {
          img.src = att.preview;
        } else if (att.path) {
          if (window.harness && window.harness.readFilePreview) {
            window.harness.readFilePreview(att.path).then(res => {
              if (res && res.preview) {
                img.src = res.preview;
                att.preview = res.preview;
              }
            });
          }
        }
        img.alt = att.name || 'Screenshot';
        imgWrap.appendChild(img);

        imgWrap.addEventListener('click', () => {
          openLightbox(att.path, att.preview || img.src, att.name);
        });

        attContainer.appendChild(imgWrap);
      } else {
        const fileChip = document.createElement('div');
        fileChip.className = 'user-att-file';
        fileChip.title = `${att.path || att.name} (Click to open)`;
        fileChip.innerHTML = `
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
          </svg>
          <span class="user-att-filename">${escapeHtml(att.name || 'File')}</span>
          <span class="user-att-size">${formatBytes(att.size || 0)}</span>
        `;
        fileChip.addEventListener('click', () => {
          if (att.path && window.harness && window.harness.openFile) {
            window.harness.openFile(att.path);
          }
        });
        attContainer.appendChild(fileChip);
      }
    });

    bubble.appendChild(attContainer);
  }

  if (text) {
    const textEl = document.createElement('div');
    textEl.className = 'user-message-text';
    textEl.textContent = text;
    bubble.appendChild(textEl);
  }

  row.appendChild(bubble);
  messagesList.appendChild(row);
}

function ensureAgentMessage() {
  if (currentAgentMessageEl) return;

  const row = document.createElement('div');
  row.className = 'message-row agent';

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';

  // Antigravity Chunked Trace Widget (initially hidden until first tool call)
  const traceWidget = createTraceWidget([], null, true);
  traceWidget.style.display = 'none';
  bubble.appendChild(traceWidget);

  currentTraceContainer = traceWidget;
  currentTraceBody = traceWidget.querySelector('.trace-chunks-body');
  currentTracePillLabel = traceWidget.querySelector('.trace-pill-label');

  startTurnTimer(currentTracePillLabel);
  startThinking(bubble, "Thinking...");

  currentMarkdownBody = document.createElement('div');
  currentMarkdownBody.className = 'markdown-body';
  bubble.appendChild(currentMarkdownBody);

  row.appendChild(bubble);
  messagesList.appendChild(row);
  currentAgentMessageEl = row;
}

// High-performance, instant & snappy text streaming
function streamText(targetEl, fullText, onDone) {
  if (!fullText) {
    if (onDone) onDone();
    return;
  }

  if (typewriterTimer) {
    clearInterval(typewriterTimer);
    typewriterTimer = null;
  }

  const length = fullText.length;

  // Short and direct answers (<= 250 chars) render INSTANTLY with zero delay
  if (length <= 250) {
    if (typeof marked !== 'undefined') {
      targetEl.innerHTML = marked.parse(fullText);
    } else {
      targetEl.textContent = fullText;
    }
    attachCodeCopyButtons(targetEl);
    scrollToBottom(true);
    if (onDone) onDone();
    return;
  }

  // For longer responses: buttery 60fps streaming completed in ~120ms total
  let index = 0;
  const chunkSize = Math.max(35, Math.ceil(length / 8));
  let streamRaf = null;

  const cleanup = () => {
    if (streamRaf) {
      cancelAnimationFrame(streamRaf);
      streamRaf = null;
    }
    if (typewriterTimer) {
      clearInterval(typewriterTimer);
      typewriterTimer = null;
    }
    window.removeEventListener('keydown', onInteraction);
    targetEl.removeEventListener('click', flushImmediately);
  };

  const flushImmediately = () => {
    cleanup();
    if (typeof marked !== 'undefined') {
      targetEl.innerHTML = marked.parse(fullText);
    } else {
      targetEl.textContent = fullText;
    }
    attachCodeCopyButtons(targetEl);
    scrollToBottom(false);
    if (onDone) onDone();
  };

  const onInteraction = (e) => {
    if (e.key === 'Escape' || e.key === 'Enter') {
      flushImmediately();
    }
  };

  window.addEventListener('keydown', onInteraction, { once: true });
  targetEl.addEventListener('click', flushImmediately, { once: true });

  const stepStream = () => {
    index = Math.min(length, index + chunkSize);
    const currentChunk = fullText.substring(0, index);
    if (typeof marked !== 'undefined') {
      targetEl.innerHTML = marked.parse(currentChunk);
    } else {
      targetEl.textContent = currentChunk;
    }
    scrollToBottom(false);

    if (index >= length) {
      cleanup();
      attachCodeCopyButtons(targetEl);
      scrollToBottom(false);
      if (onDone) onDone();
    } else {
      streamRaf = requestAnimationFrame(stepStream);
    }
  };

  streamRaf = requestAnimationFrame(stepStream);
}

// Handle incoming events from Python bridge
window.harness.onEvent((event) => {
  const type = event.type;

  if (type === 'ready' || type === 'status') {
    if (event.workspace) currentWorkspacePath = event.workspace;
    if (event.model) currentModelName = event.model;
    if (event.mode) currentActiveMode = event.mode;
    if (event.workspace_name && projectNameLabel) {
      projectNameLabel.textContent = event.workspace_name;
      if (projectPill) projectPill.title = event.workspace;
    }
    if (event.mode) {
      segButtons.forEach(b => {
        b.classList.toggle('active', b.getAttribute('data-mode') === event.mode);
      });
    }
    if (event.max_steps) stepsInput.value = event.max_steps;
    if (event.projects) {
      renderProjectsTree(event.projects);
    }
    if (event.tasks) {
      renderBackgroundTasks(event.tasks);
    }
    tryRestoreLastSession();
  }

  else if (type === 'workspace_changed') {
    if (event.path) currentWorkspacePath = event.path;
    if (projectNameLabel) {
      projectNameLabel.textContent = event.name || 'project';
      if (projectPill) projectPill.title = event.path;
    }
    if (event.projects) {
      renderProjectsTree(event.projects);
    }
    // Only reset conversation if user explicitly initiated workspace change outside generation
    if (event.source === 'user' && !isGenerating) {
      startNewConversation();
    }
    persistLastActiveState();
  }

  else if (type === 'projects_list' || type === 'project_unregistered') {
    if (event.projects) {
      renderProjectsTree(event.projects);
      tryRestoreLastSession();
    }
  }

  else if (type === 'sessions_list') {
    if (event.path && event.sessions) {
      const p = registeredProjects.find(pr => pr.path === event.path || pr.path.toLowerCase() === event.path.toLowerCase());
      if (p) {
        p.sessions = event.sessions;
        renderProjectsTree(registeredProjects);
      }
    }
  }

  else if (type === 'session_saved' || type === 'session_deleted' || type === 'session_renamed') {
    const targetPath = event.path || currentWorkspacePath;
    if (event.sessions && targetPath) {
      const p = registeredProjects.find(pr => pr.path === targetPath || pr.path.toLowerCase() === targetPath.toLowerCase());
      if (p) {
        const prevCount = (p.sessions || []).length;
        p.sessions = event.sessions;
        const newCount = (event.sessions || []).length;
        if (type !== 'session_saved' || prevCount !== newCount) {
          renderProjectsTree(registeredProjects);
        } else {
          // Efficiently update active session title in-place without sidebar DOM destruction
          const activeTitleEl = projectsTree ? projectsTree.querySelector(`.session-item[data-session-id="${currentSessionId}"] .session-item-title`) : null;
          if (activeTitleEl && currentSessionTitle && activeTitleEl.textContent !== currentSessionTitle) {
            activeTitleEl.textContent = currentSessionTitle;
            activeTitleEl.title = currentSessionTitle;
          }
        }
      }
    }
    if (type === 'session_deleted' || type === 'session_renamed') {
      window.harness.listProjects();
    }
  }

  else if (type === 'session_loaded') {
    if (event.session) {
      const sess = event.session;
      if (typewriterTimer) {
        clearInterval(typewriterTimer);
        typewriterTimer = null;
      }
      stopThinking();

      currentSessionId = sess.id;
      currentSessionTitle = sess.title || 'Conversation';
      currentSessionMessages = sess.messages || [];

      // Synchronize active workspace to the project this session belongs to
      const targetPath = event.path || sess.workspace || currentWorkspacePath;
      if (targetPath) {
        currentWorkspacePath = targetPath;
        if (projectNameLabel) {
          const parts = targetPath.replace(/\\/g, '/').split('/').filter(Boolean);
          projectNameLabel.textContent = parts[parts.length - 1] || targetPath;
          if (projectPill) projectPill.title = targetPath;
        }
      }

      messagesList.innerHTML = '';
      if (welcomeHero) welcomeHero.style.display = 'none';

      currentSessionMessages.forEach(msg => {
        renderRestoredMessage(msg);
      });

      updateActiveSessionHighlight();
      scrollToBottom();
      setGenerating(false);
      persistLastActiveState();
    }
  }

  else if (type === 'routing') {
    ensureAgentMessage();
    if (event.model) currentModelName = event.model;
    scrollToBottom();
  }

  else if (type === 'tool_call') {
    ensureAgentMessage();
    if (currentTraceContainer) {
      currentTraceContainer.style.display = 'flex';
    }

    const toolId = event.id || event.tool_call_id || `call_${Date.now()}_${activeToolCalls.length}`;
    const toolName = event.tool;
    const args = event.args || {};

    const toolObj = {
      id: toolId,
      name: toolName,
      args: args,
      output: '',
      status: 'running'
    };
    activeToolCalls.push(toolObj);

    if (currentTraceBody) {
      renderTraceChunks(currentTraceBody, activeToolCalls);
    }

    updateThinking(`Running ${toolName}...`);
    scrollToBottom();
  }

  else if (type === 'tool_result') {
    const output = String(event.output !== undefined && event.output !== null ? event.output : '');
    if (activeToolCalls.length > 0) {
      let targetTool = null;
      const lookupId = event.id || event.tool_call_id;
      if (lookupId && event.tool) {
        targetTool = activeToolCalls.slice().reverse().find(t => t.id === lookupId && t.name === event.tool && t.status === 'running');
      }
      if (!targetTool && lookupId) {
        targetTool = activeToolCalls.slice().reverse().find(t => t.id === lookupId && t.status === 'running');
      }
      if (!targetTool && event.tool) {
        targetTool = activeToolCalls.slice().reverse().find(t => t.name === event.tool && t.status === 'running');
      }
      if (!targetTool && lookupId) {
        targetTool = activeToolCalls.slice().reverse().find(t => t.id === lookupId);
      }
      if (!targetTool) {
        targetTool = activeToolCalls.slice().reverse().find(t => t.status === 'running');
      }
      if (!targetTool) {
        targetTool = activeToolCalls[activeToolCalls.length - 1];
      }

      targetTool.output = output;
      targetTool.status = 'completed';

      if (currentTraceBody) {
        renderTraceChunks(currentTraceBody, activeToolCalls);
      }

      updateThinking(`Analyzing ${targetTool.name} result...`);

      if (inspectorPanel.style.display !== 'none' && inspectorToolName.textContent === targetTool.name) {
        inspectorOutputCode.textContent = output !== '' ? output : '[Command completed with no output]';
        inspectorStatus.textContent = 'completed';
        inspectorStatus.className = 'inspector-badge';
      }
    }
  }

  else if (type === 'final_answer' || type === 'circuit_breaker') {
    stopThinking();
    stopTurnTimer();
    ensureAgentMessage();

    const elapsed = Date.now() - (currentTurnStartTime || Date.now());
    const finalDuration = formatDuration(elapsed);

    // Auto-collapse tool trace window and lock in final duration
    if (currentTraceContainer && activeToolCalls.length > 0) {
      if (currentTracePillLabel) {
        currentTracePillLabel.textContent = `Worked for ${finalDuration}`;
      }
      currentTraceContainer.classList.remove('open');
    }

    // Insert changes banner if files were modified
    const changesBanner = createChangesBanner(activeToolCalls);
    if (changesBanner && currentMarkdownBody && currentMarkdownBody.parentNode) {
      currentMarkdownBody.parentNode.insertBefore(changesBanner, currentMarkdownBody);
    }

    const rawContent = event.content || '';

    // Record agent turn in session messages
    const toolsSnapshot = activeToolCalls.map(t => ({
      name: t.name,
      args: t.args,
      output: t.output,
      status: t.status
    }));
    currentSessionMessages.push({
      role: 'agent',
      content: rawContent,
      tools: toolsSnapshot,
      duration: finalDuration,
      timestamp: Date.now() / 1000
    });

    // Auto-save session
    if (currentWorkspacePath && currentSessionId) {
      window.harness.saveSession(
        currentWorkspacePath,
        currentSessionId,
        currentSessionTitle,
        currentSessionMessages,
        currentModelName,
        currentActiveMode
      );
    }

    streamText(currentMarkdownBody, rawContent, () => {
      setGenerating(false);
    });
  }

  else if (type === 'aborted') {
    stopThinking();
    stopTurnTimer();
    if (typewriterTimer) {
      clearInterval(typewriterTimer);
      typewriterTimer = null;
    }
    if (currentTraceContainer && currentTracePillLabel) {
      const elapsed = Date.now() - (currentTurnStartTime || Date.now());
      currentTracePillLabel.textContent = `Stopped after ${formatDuration(elapsed)}`;
      currentTraceContainer.classList.remove('open');
    }
    setGenerating(false);
  }

  else if (type === 'error') {
    stopThinking();
    stopTurnTimer();
    if (event.error && event.error.includes('Session') && event.error.includes('not found')) {
      try { localStorage.removeItem('harness_last_session_id'); } catch (e) {}
    }
    ensureAgentMessage();
    const errDiv = document.createElement('div');
    errDiv.style.color = 'var(--accent-red)';
    errDiv.style.fontFamily = 'var(--font-mono)';
    errDiv.style.fontSize = '12px';
    errDiv.style.marginTop = '6px';
    errDiv.textContent = `[error] ${event.error}`;
    currentMarkdownBody.appendChild(errDiv);
    scrollToBottom();
    setGenerating(false);
  }

  else if (type === 'tasks_updated') {
    renderBackgroundTasks(event.tasks || []);
    if (inspectedTaskId !== null && inspectorPanel.style.display !== 'none' && activeBackgroundTasks.some(t => t.pid === inspectedTaskId)) {
      if (window.harness && window.harness.getProcessOutput) {
        window.harness.getProcessOutput(inspectedTaskId);
      }
    }
  }

  else if (type === 'process_output') {
    if (inspectedTaskId !== null && event.pid == inspectedTaskId) {
      const wasNearBottom = (inspectorOutputCode.scrollHeight - inspectorOutputCode.scrollTop - inspectorOutputCode.clientHeight) < 50;
      inspectorOutputCode.textContent = stripAnsi(event.output || '[No output recorded yet]');
      if (wasNearBottom) {
        inspectorOutputCode.scrollTop = inspectorOutputCode.scrollHeight;
      }
    }
  }

  else if (type === 'cloud_tasks_data') {
    renderCloudTasksData(event);
  }

  else if (type === 'cloud_run_triggered') {
    if (telegramStatusMsg) {
      telegramStatusMsg.style.display = 'block';
      telegramStatusMsg.style.color = '#34d399';
      telegramStatusMsg.textContent = `Workflow run dispatched on GitHub Actions! (${event.workflow || ''})`;
      setTimeout(() => { telegramStatusMsg.style.display = 'none'; }, 4000);
    }
    setTimeout(() => {
      if (window.harness && window.harness.cloudListTasks) {
        window.harness.cloudListTasks();
      }
    }, 1800);
  }

  else if (type === 'cloud_logs_data') {
    renderCloudLogs(event.run_id, event.logs);
  }

  else if (type === 'cloud_telegram_configured') {
    if (telegramStatusMsg) {
      telegramStatusMsg.style.display = 'block';
      telegramStatusMsg.style.color = '#34d399';
      telegramStatusMsg.textContent = event.message || 'Secrets saved successfully!';
    }
  }

  else if (type === 'cloud_telegram_tested') {
    if (telegramStatusMsg) {
      telegramStatusMsg.style.display = 'block';
      const isOk = event.result && event.result.startsWith('Success');
      telegramStatusMsg.style.color = isOk ? '#34d399' : 'var(--accent-red)';
      telegramStatusMsg.textContent = event.result || 'Test completed.';
    }
  }

  else if (type === 'done') {
    stopThinking();
    stopTurnTimer();
    if (!typewriterTimer) {
      setGenerating(false);
    }
    currentAgentMessageEl = null;
    currentTraceGroup = null;
    currentTraceContainer = null;
    currentTraceBody = null;
    currentTracePillLabel = null;
    currentMarkdownBody = null;
    activeToolCalls = [];
  }
});

// ==============================================================================
// Cloud Scrapers & GitHub Actions UI Controller
// ==============================================================================

function openCloudDashboard() {
  const modal = cloudDashboardModal || document.getElementById('cloudDashboardModal');
  if (!modal) return;
  modal.style.display = 'flex';
  if (window.harness && window.harness.cloudListTasks) {
    window.harness.cloudListTasks();
  }
}

function closeCloudDashboard() {
  const modal = cloudDashboardModal || document.getElementById('cloudDashboardModal');
  if (modal) modal.style.display = 'none';
  const telPanel = cloudTelegramPanel || document.getElementById('cloudTelegramPanel');
  if (telPanel) telPanel.style.display = 'none';
}

const btnCloud = cloudTasksBtn || document.getElementById('cloudTasksBtn');
if (btnCloud) btnCloud.addEventListener('click', openCloudDashboard);
if (cloudCloseBtn) cloudCloseBtn.addEventListener('click', closeCloudDashboard);
if (cloudModalBackdrop) cloudModalBackdrop.addEventListener('click', closeCloudDashboard);

window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    const modal = cloudDashboardModal || document.getElementById('cloudDashboardModal');
    if (modal && modal.style.display !== 'none') {
      closeCloudDashboard();
    }
  }
});

if (cloudRefreshBtn) {
  cloudRefreshBtn.addEventListener('click', () => {
    if (window.harness && window.harness.cloudListTasks) {
      window.harness.cloudListTasks();
    }
  });
}

// Telegram panel toggling
if (cloudTelegramBtn) {
  cloudTelegramBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    if (!cloudTelegramPanel) return;
    const isShown = cloudTelegramPanel.style.display !== 'none';
    cloudTelegramPanel.style.display = isShown ? 'none' : 'block';
    if (telegramStatusMsg) telegramStatusMsg.style.display = 'none';
  });
}

if (closeTelegramPanelBtn) {
  closeTelegramPanelBtn.addEventListener('click', () => {
    if (cloudTelegramPanel) cloudTelegramPanel.style.display = 'none';
  });
}

if (saveTelegramSecretsBtn) {
  saveTelegramSecretsBtn.addEventListener('click', () => {
    const token = (telegramBotTokenInput ? telegramBotTokenInput.value : '').trim();
    const cid = (telegramChatIdInput ? telegramChatIdInput.value : '').trim();
    if (!token || !cid) {
      if (telegramStatusMsg) {
        telegramStatusMsg.style.display = 'block';
        telegramStatusMsg.style.color = 'var(--accent-red)';
        telegramStatusMsg.textContent = 'Both Bot Token and Chat ID are required.';
      }
      return;
    }
    if (telegramStatusMsg) {
      telegramStatusMsg.style.display = 'block';
      telegramStatusMsg.style.color = 'var(--text-muted)';
      telegramStatusMsg.textContent = 'Saving encrypted secrets to GitHub...';
    }
    if (window.harness && window.harness.cloudSetTelegram) {
      window.harness.cloudSetTelegram(token, cid);
    }
  });
}

if (testTelegramPingBtn) {
  testTelegramPingBtn.addEventListener('click', () => {
    const token = (telegramBotTokenInput ? telegramBotTokenInput.value : '').trim();
    const cid = (telegramChatIdInput ? telegramChatIdInput.value : '').trim();
    if (!token || !cid) {
      if (telegramStatusMsg) {
        telegramStatusMsg.style.display = 'block';
        telegramStatusMsg.style.color = 'var(--accent-red)';
        telegramStatusMsg.textContent = 'Please enter Bot Token and Chat ID to test.';
      }
      return;
    }
    if (telegramStatusMsg) {
      telegramStatusMsg.style.display = 'block';
      telegramStatusMsg.style.color = 'var(--text-muted)';
      telegramStatusMsg.textContent = 'Sending test ping via Telegram API...';
    }
    if (window.harness && window.harness.cloudTestTelegram) {
      window.harness.cloudTestTelegram(token, cid, "Test alert from John's Harness! 24/7 Cloud Scraper connection verified.");
    }
  });
}

// Tab navigation
const cloudTabs = document.querySelectorAll('.cloud-tab');
cloudTabs.forEach(tab => {
  tab.addEventListener('click', () => {
    const target = tab.getAttribute('data-tab');
    switchCloudTab(target);
  });
});

function switchCloudTab(tabName) {
  cloudTabs.forEach(t => t.classList.toggle('active', t.getAttribute('data-tab') === tabName));
  const tabWorkflows = document.getElementById('cloudTabWorkflows');
  const tabLogs = document.getElementById('cloudTabLogs');
  const tabScripts = document.getElementById('cloudTabScripts');
  const tabData = document.getElementById('cloudTabData');

  if (tabWorkflows) tabWorkflows.classList.toggle('active', tabName === 'workflows');
  if (tabLogs) tabLogs.classList.toggle('active', tabName === 'logs');
  if (tabScripts) tabScripts.classList.toggle('active', tabName === 'scripts');
  if (tabData) tabData.classList.toggle('active', tabName === 'data');
}

// Copy logs button
if (copyCloudLogsBtn) {
  copyCloudLogsBtn.addEventListener('click', () => {
    const text = cloudLogsTerminal ? cloudLogsTerminal.innerText : '';
    if (text) {
      navigator.clipboard.writeText(text).then(() => {
        copyCloudLogsBtn.textContent = 'copied!';
        setTimeout(() => { copyCloudLogsBtn.textContent = 'copy logs'; }, 1500);
      });
    }
  });
}

// Copy script button
if (copyCloudScriptBtn) {
  copyCloudScriptBtn.addEventListener('click', () => {
    const text = cloudScriptCode ? cloudScriptCode.innerText : '';
    if (text) {
      navigator.clipboard.writeText(text).then(() => {
        copyCloudScriptBtn.textContent = 'copied!';
        setTimeout(() => { copyCloudScriptBtn.textContent = 'copy'; }, 1500);
      });
    }
  });
}

function renderCloudTasksData(data) {
  cachedCloudData = data;
  const workflows = data.workflows || [];
  const runs = data.runs || [];
  const scrapers = data.scrapers || [];
  const savedData = data.saved_data || [];

  // Update badge dot if any run is active
  const hasRunning = runs.some(r => r.status === 'in_progress' || r.status === 'queued');
  if (cloudTasksDot) cloudTasksDot.classList.toggle('active', hasRunning);

  // 1. Workflows
  if (cloudWorkflowsCount) cloudWorkflowsCount.textContent = `${workflows.length} workflow${workflows.length === 1 ? '' : 's'}`;
  if (cloudWorkflowsList) {
    cloudWorkflowsList.innerHTML = '';
    if (workflows.length === 0) {
      cloudWorkflowsList.innerHTML = `<div class="cloud-empty-state">No cloud workflows found in .github/workflows.<br>Prompt John's Harness: <i>"Create a scraper for &lt;website&gt; every hour and alert my Telegram bot"</i>.</div>`;
    } else {
      workflows.forEach(wf => {
        const card = document.createElement('div');
        card.className = 'cloud-wf-card';
        card.innerHTML = `
          <div class="cloud-wf-info">
            <span class="cloud-wf-name">${escapeHtml(wf.name || wf.file)}</span>
            <div class="cloud-wf-meta">
              <span>${escapeHtml(wf.file)}</span>
              <span class="cloud-cron-badge">cron: ${escapeHtml(wf.cron)}</span>
            </div>
          </div>
          <div class="cloud-wf-actions">
            <button class="btn-run-action" data-wf="${escapeHtml(wf.file)}">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
              <span>Run Now</span>
            </button>
          </div>
        `;
        const runBtn = card.querySelector('.btn-run-action');
        if (runBtn) {
          runBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            runBtn.disabled = true;
            runBtn.innerHTML = `<span>Dispatching...</span>`;
            if (window.harness && window.harness.cloudTriggerRun) {
              window.harness.cloudTriggerRun(wf.file);
            }
          });
        }
        cloudWorkflowsList.appendChild(card);
      });
    }
  }

  // 2. Runs
  if (cloudRunsCount) cloudRunsCount.textContent = `${runs.length} run${runs.length === 1 ? '' : 's'}`;
  if (cloudRunsList) {
    cloudRunsList.innerHTML = '';
    if (runs.length === 0) {
      cloudRunsList.innerHTML = `<div class="cloud-empty-state">No GitHub Actions runs recorded yet. Click "Run Now" on a workflow above to execute on the cloud.</div>`;
    } else {
      runs.forEach(run => {
        const row = document.createElement('div');
        row.className = 'cloud-run-row';
        const st = (run.status === 'completed' ? (run.conclusion || 'completed') : run.status).toLowerCase();
        const badgeClass = st === 'success' ? 'success' : (st === 'in_progress' ? 'in_progress' : (st === 'failure' ? 'failure' : 'queued'));
        
        let dateStr = '';
        if (run.createdAt) {
          try {
            const d = new Date(run.createdAt);
            dateStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' ' + d.toLocaleDateString([], { month: 'short', day: 'numeric' });
          } catch(e) {}
        }

        row.innerHTML = `
          <div class="cloud-run-left">
            <span class="cloud-run-badge ${badgeClass}">${escapeHtml(st)}</span>
            <span class="cloud-run-name">${escapeHtml(run.name || run.workflowName || 'Workflow Run')}</span>
          </div>
          <div class="cloud-run-right">
            <span>#${escapeHtml(String(run.databaseId || ''))}</span>
            <span>${escapeHtml(dateStr)}</span>
            <button class="btn-ghost-sm" title="View Terminal Logs">Logs</button>
          </div>
        `;

        row.addEventListener('click', () => {
          if (run.databaseId && window.harness && window.harness.cloudGetLogs) {
            if (cloudLogsTargetLabel) cloudLogsTargetLabel.textContent = `Fetching logs for run #${run.databaseId}...`;
            if (cloudLogsTerminal) cloudLogsTerminal.textContent = 'Loading logs from GitHub Actions...';
            switchCloudTab('logs');
            window.harness.cloudGetLogs(run.databaseId);
          }
        });

        cloudRunsList.appendChild(row);
      });
    }
  }

  // 3. Scrapers
  if (cloudScriptsList) {
    cloudScriptsList.innerHTML = '';
    if (scrapers.length === 0) {
      cloudScriptsList.innerHTML = `<div class="cloud-empty-state">No Python scripts in scrapers/</div>`;
    } else {
      scrapers.forEach((scr, idx) => {
        const item = document.createElement('div');
        item.className = `cloud-script-item ${idx === 0 ? 'active' : ''}`;
        item.textContent = scr.file;
        item.title = scr.path;
        item.addEventListener('click', () => {
          cloudScriptsList.querySelectorAll('.cloud-script-item').forEach(el => el.classList.remove('active'));
          item.classList.add('active');
          loadScriptSource(scr.path, scr.file);
        });
        cloudScriptsList.appendChild(item);
      });

      if (scrapers.length > 0) {
        loadScriptSource(scrapers[0].path, scrapers[0].file);
      }
    }
  }

  // 4. Saved Data
  if (statFilesCount) statFilesCount.textContent = String(savedData.length);
  let totalB = 0;
  savedData.forEach(d => totalB += (d.size_bytes || 0));
  if (statTotalBytes) statTotalBytes.textContent = formatBytes(totalB);

  if (cloudFilesList) {
    cloudFilesList.innerHTML = '';
    if (savedData.length === 0) {
      cloudFilesList.innerHTML = `<div class="cloud-empty-state">No scraped datasets in scrapers/data/ yet. When scrapers finish, extracted datasets will appear here.</div>`;
    } else {
      savedData.forEach(f => {
        const frow = document.createElement('div');
        frow.className = 'cloud-file-row';
        frow.innerHTML = `
          <span class="cloud-file-name">${escapeHtml(f.file)}</span>
          <div class="cloud-file-meta">
            <span>${formatBytes(f.size_bytes || 0)}</span>
            <button class="btn-ghost-sm" title="Open file in editor">Open</button>
          </div>
        `;
        const openBtn = frow.querySelector('button');
        if (openBtn) {
          openBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (f.path && window.harness && window.harness.openFile) {
              window.harness.openFile(f.path);
            }
          });
        }
        cloudFilesList.appendChild(frow);
      });
    }
  }
}

function loadScriptSource(filePath, fileName) {
  if (cloudScriptFilename) cloudScriptFilename.textContent = fileName || 'Script';
  if (cloudScriptCode) cloudScriptCode.textContent = '# Loading script source...';
  if (filePath) {
    if (window.harness && window.harness.readFilePreview) {
      window.harness.readFilePreview(filePath).then(res => {
        if (res && res.text) {
          if (cloudScriptCode) cloudScriptCode.textContent = res.text;
        } else {
          if (cloudScriptCode) cloudScriptCode.textContent = `# Source path: ${filePath}`;
        }
      }).catch(() => {
        if (cloudScriptCode) cloudScriptCode.textContent = `# Source path: ${filePath}`;
      });
    }
  }
}

function renderCloudLogs(runId, logs) {
  if (cloudLogsTargetLabel) cloudLogsTargetLabel.textContent = `Terminal Execution Logs for Run #${runId}`;
  if (cloudLogsTerminal) {
    cloudLogsTerminal.textContent = stripAnsi(logs || '[No logs available]');
    cloudLogsTerminal.scrollTop = cloudLogsTerminal.scrollHeight;
  }
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// Open all external links (http/https/mailto) in default system browser (Chrome, Edge, etc.)
document.addEventListener('click', (e) => {
  const linkEl = e.target.closest('a');
  if (linkEl && linkEl.href) {
    const url = linkEl.href;
    if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('mailto:')) {
      e.preventDefault();
      if (window.harness && window.harness.openExternal) {
        window.harness.openExternal(url).catch(() => {});
      }
    }
  }
});

// Request initial status and project list on load
if (window.harness) {
  if (window.harness.getStatus) window.harness.getStatus();
  if (window.harness.listProjects) window.harness.listProjects();
  if (window.harness.getBackgroundTasks) window.harness.getBackgroundTasks();
  if (window.harness.cloudListTasks) window.harness.cloudListTasks();
}
