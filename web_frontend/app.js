const API = {
  chat: "/api/chat",
  resume: "/api/resume",
  upload: "/api/upload",
};

const DEFAULT_COMPANY_ID = "019f1b62-dd8f-77f9-8500-22881b24065f";

const els = {
  sidebar: document.querySelector("#sidebar"),
  sidebarToggle: document.querySelector("#sidebarToggle"),
  threadList: document.querySelector("#threadList"),
  newChatButton: document.querySelector("#newChatButton"),
  themeButton: document.querySelector("#themeButton"),
  messages: document.querySelector("#messages"),
  hero: document.querySelector("#hero"),
  input: document.querySelector("#messageInput"),
  sendButton: document.querySelector("#sendButton"),
  attachButton: document.querySelector("#attachButton"),
  fileInput: document.querySelector("#fileInput"),
  copyButton: document.querySelector("#copyButton"),
  downloadButton: document.querySelector("#downloadButton"),
  toast: document.querySelector("#toast"),
};

let state = loadClientState();
let pendingInterrupt = null;
let lastMarkdown = "";

init();

function init() {
  applyTheme();
  ensureCurrentThread();
  renderThreadList();
  renderMessages();
  bindEvents();
}

function bindEvents() {
  els.newChatButton.addEventListener("click", createNewThread);
  els.themeButton.addEventListener("click", toggleTheme);
  els.sidebarToggle.addEventListener("click", () => els.sidebar.classList.toggle("open"));
  els.sendButton.addEventListener("click", sendCurrentInput);
  els.attachButton.addEventListener("click", () => els.fileInput.click());
  els.fileInput.addEventListener("change", handleFileSelected);
  els.copyButton.addEventListener("click", copyMarkdown);
  els.downloadButton.addEventListener("click", downloadMarkdown);

  els.input.addEventListener("input", autoResizeInput);
  els.input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendCurrentInput();
    }
  });

  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      els.input.value = chip.dataset.prompt || "";
      autoResizeInput();
      els.input.focus();
    });
  });
}

function loadClientState() {
  const saved = localStorage.getItem("nqj.chat.state");

  if (saved) {
    try {
      return JSON.parse(saved);
    } catch {
      localStorage.removeItem("nqj.chat.state");
    }
  }

  return {
    theme: "light",
    currentThreadId: null,
    threads: {},
  };
}

function saveClientState() {
  localStorage.setItem("nqj.chat.state", JSON.stringify(state));
}

function ensureCurrentThread() {
  if (state.currentThreadId && state.threads[state.currentThreadId]) {
    return;
  }

  createNewThread(false);
}

function createNewThread(render = true) {
  const threadId = `web-${crypto.randomUUID()}`;

  state.currentThreadId = threadId;
  state.threads[threadId] = {
    id: threadId,
    title: "새 매뉴얼 작업",
    createdAt: new Date().toISOString(),
    messages: [],
  };

  pendingInterrupt = null;
  lastMarkdown = "";
  saveClientState();

  if (render) {
    renderThreadList();
    renderMessages();
    showToast("새 작업을 시작했습니다.");
  }
}

function getCurrentThread() {
  ensureCurrentThread();
  return state.threads[state.currentThreadId];
}

function setThreadTitleFromMessage(message) {
  const thread = getCurrentThread();

  if (thread.title === "새 매뉴얼 작업") {
    thread.title = message.slice(0, 32) || "매뉴얼 작업";
  }
}

function renderThreadList() {
  const threads = Object.values(state.threads).sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  els.threadList.innerHTML = "";

  for (const thread of threads) {
    const button = document.createElement("button");
    button.className = `thread-item ${thread.id === state.currentThreadId ? "active" : ""}`;
    button.type = "button";
    button.innerHTML = `
      <strong>${escapeHtml(thread.title)}</strong>
      <span>${formatDate(thread.createdAt)}</span>
    `;
    button.addEventListener("click", () => {
      state.currentThreadId = thread.id;
      pendingInterrupt = null;
      saveClientState();
      renderThreadList();
      renderMessages();
      els.sidebar.classList.remove("open");
    });
    els.threadList.appendChild(button);
  }
}

function renderMessages() {
  const thread = getCurrentThread();
  els.messages.innerHTML = "";
  els.hero.classList.toggle("hidden", thread.messages.length > 0);

  for (const message of thread.messages) {
    if (message.kind === "markdown") {
      appendMarkdownCard(message.markdown, message.title || "Markdown 초안", false);
    } else if (message.kind === "interrupt") {
      appendInterruptCard(message.interrupt, false);
    } else if (message.kind === "error") {
      appendErrorCard(message.message, message.error, false);
    } else {
      appendChatBubble(message.role, message.content, false);
    }
  }

  scrollToBottom();
}

async function sendCurrentInput() {
  const text = els.input.value.trim();

  if (!text) {
    return;
  }

  if (pendingInterrupt) {
    await resumeWithValue(text);
    els.input.value = "";
    autoResizeInput();
    return;
  }

  const thread = getCurrentThread();
  thread.messages.push({ role: "user", content: text });
  setThreadTitleFromMessage(text);
  saveClientState();
  renderThreadList();
  appendChatBubble("user", text);
  els.hero.classList.add("hidden");
  els.input.value = "";
  autoResizeInput();

  const typingId = showTyping();
  setBusy(true);

  try {
    const response = await fetchJson(API.chat, {
      method: "POST",
      body: JSON.stringify({
        thread_id: state.currentThreadId,
        company_id: DEFAULT_COMPANY_ID,
        message: text,
      }),
    });

    removeTyping(typingId);
    handleAgentResponse(response);
  } catch (error) {
    removeTyping(typingId);
    handleError(error);
  } finally {
    setBusy(false);
  }
}

async function resumeWithValue(value) {
  const thread = getCurrentThread();
  thread.messages.push({ role: "user", content: value });
  saveClientState();
  appendChatBubble("user", value);

  const typingId = showTyping();
  setBusy(true);

  try {
    const response = await fetchJson(API.resume, {
      method: "POST",
      body: JSON.stringify({
        thread_id: state.currentThreadId,
        company_id: DEFAULT_COMPANY_ID,
        resume: value,
      }),
    });

    removeTyping(typingId);
    pendingInterrupt = null;
    handleAgentResponse(response);
  } catch (error) {
    removeTyping(typingId);
    handleError(error);
  } finally {
    setBusy(false);
  }
}

function handleAgentResponse(response) {
  const thread = getCurrentThread();

  if (response.status === "failed") {
    const message = response.message || "오류가 발생했습니다.";
    thread.messages.push({ kind: "error", message, error: response.error });
    saveClientState();
    appendErrorCard(message, response.error);
    return;
  }

  if (response.status === "interrupted") {
    pendingInterrupt = response.interrupt;
    thread.messages.push({ kind: "interrupt", interrupt: response.interrupt });
    saveClientState();
    appendInterruptCard(response.interrupt);
    return;
  }

  if (response.message) {
    thread.messages.push({ role: "assistant", content: response.message });
    saveClientState();
    appendChatBubble("assistant", response.message);
  }

  if (response.draft_markdown) {
    lastMarkdown = response.draft_markdown;
    const title = response.final_markdown ? "최종 Markdown" : "Markdown 초안";
    thread.messages.push({ kind: "markdown", title, markdown: response.draft_markdown });
    saveClientState();
    appendMarkdownCard(response.draft_markdown, title);
  }

  if (response.status === "quality_failed" && response.quality_result) {
    const detail = JSON.stringify(response.quality_result, null, 2);
    thread.messages.push({ kind: "error", message: "품질 검수 실패", error: detail });
    saveClientState();
    appendErrorCard("품질 검수 실패", detail);
  }
}

function appendChatBubble(role, content, persist = true) {
  const row = document.createElement("div");
  row.className = `message-row ${role}`;
  row.innerHTML = `
    <div class="avatar">${role === "user" ? "ME" : "AI"}</div>
    <div class="bubble">${escapeHtml(content)}</div>
  `;
  els.messages.appendChild(row);

  if (persist) {
    scrollToBottom();
  }
}

function appendInterruptCard(interrupt, persist = true) {
  const payload = typeof interrupt === "object" && interrupt !== null ? interrupt : { message: String(interrupt) };
  const type = payload.type || "interrupt";
  const markdown = payload.markdown || "";
  const options = Array.isArray(payload.options) ? payload.options : [];
  const examples = Array.isArray(payload.examples) ? payload.examples : [];

  const card = document.createElement("div");
  card.className = "interrupt-card";

  const markdownHtml = markdown ? `<div class="markdown-preview">${renderMarkdown(markdown)}</div>` : "";
  const examplesHtml = examples.length
    ? `<div class="interrupt-actions">${examples.map((item) => `<button class="interrupt-secondary" data-resume="${escapeAttr(item)}">${escapeHtml(item)}</button>`).join("")}</div>`
    : "";
  const optionsHtml = options.length
    ? `<div class="interrupt-actions">${options.map((item) => `<button class="interrupt-secondary" data-resume="${escapeAttr(item)}">${escapeHtml(item)}</button>`).join("")}</div>`
    : "";

  const uploadButton = type === "manual_source_choice"
    ? `<button class="interrupt-primary" data-action="upload">매뉴얼 파일 업로드</button>
       <button class="interrupt-secondary" data-resume="skip">skip으로 진행</button>`
    : "";

  const approvalButtons = type === "approval"
    ? `<button class="interrupt-primary" data-resume="승인">승인</button>
       <button class="interrupt-secondary" data-focus="feedback">수정 요청 입력</button>`
    : "";

  card.innerHTML = `
    <div class="card-header">
      <div>
        <div class="card-title">사용자 확인 필요</div>
        <div class="page-subtitle">${escapeHtml(type)}</div>
      </div>
    </div>
    <div class="card-body">
      <p>${escapeHtml(payload.message || "입력이 필요합니다.")}</p>
      ${markdownHtml}
      ${examplesHtml}
      ${optionsHtml}
      <div class="interrupt-actions">${uploadButton}${approvalButtons}</div>
      <textarea class="inline-input" placeholder="여기에 응답을 입력하고 아래 버튼을 누르세요."></textarea>
      <div class="interrupt-actions">
        <button class="interrupt-primary" data-action="submit-inline">응답 보내기</button>
      </div>
    </div>
  `;

  card.querySelectorAll("[data-resume]").forEach((button) => {
    button.addEventListener("click", () => resumeWithValue(button.dataset.resume));
  });

  const inlineInput = card.querySelector(".inline-input");

  card.querySelector("[data-action='submit-inline']").addEventListener("click", () => {
    const value = inlineInput.value.trim();
    if (value) resumeWithValue(value);
  });

  const focusButton = card.querySelector("[data-focus='feedback']");
  if (focusButton) {
    focusButton.addEventListener("click", () => inlineInput.focus());
  }

  const uploadButtonElement = card.querySelector("[data-action='upload']");
  if (uploadButtonElement) {
    uploadButtonElement.addEventListener("click", () => els.fileInput.click());
  }

  els.messages.appendChild(card);

  if (persist) {
    scrollToBottom();
  }
}

function appendMarkdownCard(markdown, title = "Markdown", persist = true) {
  lastMarkdown = markdown || lastMarkdown;

  const card = document.createElement("div");
  card.className = "markdown-card";
  card.innerHTML = `
    <div class="card-header">
      <div class="card-title">${escapeHtml(title)}</div>
      <button class="ghost-button" type="button">복사</button>
    </div>
    <div class="card-body">
      <div class="markdown-preview">${renderMarkdown(markdown)}</div>
    </div>
  `;

  card.querySelector("button").addEventListener("click", () => {
    navigator.clipboard.writeText(markdown || "");
    showToast("Markdown을 복사했습니다.");
  });

  els.messages.appendChild(card);

  if (persist) {
    scrollToBottom();
  }
}

function appendErrorCard(message, error, persist = true) {
  const card = document.createElement("div");
  card.className = "error-card";
  card.innerHTML = `
    <div class="card-header">
      <div class="card-title">${escapeHtml(message)}</div>
    </div>
    <div class="card-body">
      <pre>${escapeHtml(error || "서버 로그를 확인해 주세요.")}</pre>
    </div>
  `;
  els.messages.appendChild(card);

  if (persist) {
    scrollToBottom();
  }
}

function showTyping() {
  const id = `typing-${Date.now()}`;
  const row = document.createElement("div");
  row.className = "message-row assistant";
  row.id = id;
  row.innerHTML = `
    <div class="avatar">AI</div>
    <div class="bubble"><div class="typing"><span></span><span></span><span></span></div></div>
  `;
  els.messages.appendChild(row);
  scrollToBottom();
  return id;
}

function removeTyping(id) {
  const node = document.getElementById(id);
  if (node) node.remove();
}

async function handleFileSelected() {
  const file = els.fileInput.files?.[0];
  els.fileInput.value = "";

  if (!file) return;

  if (!pendingInterrupt || pendingInterrupt.type !== "manual_source_choice") {
    showToast("파일은 매뉴얼 확인 단계에서 업로드할 수 있습니다.");
    return;
  }

  const formData = new FormData();
  formData.append("file", file);

  setBusy(true);

  try {
    const response = await fetch(`${API.upload}?thread_id=${encodeURIComponent(state.currentThreadId)}`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(text);
    }

    const uploaded = await response.json();
    showToast(`${uploaded.file_name} 업로드 완료`);
    await resumeWithValue(uploaded.file_path);
  } catch (error) {
    handleError(error);
  } finally {
    setBusy(false);
  }
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const text = await response.text();
  let data = null;

  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { message: text };
  }

  if (!response.ok) {
    throw new Error(data.detail || data.message || response.statusText);
  }

  return data;
}

function handleError(error) {
  const message = error?.message || String(error);
  const thread = getCurrentThread();
  thread.messages.push({ kind: "error", message: "요청 실패", error: message });
  saveClientState();
  appendErrorCard("요청 실패", message);
}

function setBusy(isBusy) {
  els.sendButton.disabled = isBusy;
  els.attachButton.disabled = isBusy;
  els.input.disabled = isBusy;
}

function autoResizeInput() {
  els.input.style.height = "auto";
  els.input.style.height = `${Math.min(els.input.scrollHeight, 180)}px`;
}

function scrollToBottom() {
  requestAnimationFrame(() => {
    els.messages.scrollTop = els.messages.scrollHeight;
  });
}

function toggleTheme() {
  state.theme = state.theme === "dark" ? "light" : "dark";
  applyTheme();
  saveClientState();
}

function applyTheme() {
  document.documentElement.dataset.theme = state.theme || "light";
}

function copyMarkdown() {
  if (!lastMarkdown) {
    showToast("복사할 Markdown이 없습니다.");
    return;
  }

  navigator.clipboard.writeText(lastMarkdown);
  showToast("Markdown을 복사했습니다.");
}

function downloadMarkdown() {
  if (!lastMarkdown) {
    showToast("다운로드할 Markdown이 없습니다.");
    return;
  }

  const blob = new Blob([lastMarkdown], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "manual-section.md";
  link.click();
  URL.revokeObjectURL(url);
}

function showToast(message) {
  els.toast.textContent = message;
  els.toast.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => els.toast.classList.remove("show"), 1800);
}

function renderMarkdown(markdown = "") {
  const escaped = escapeHtml(markdown);
  const lines = escaped.split("\n");
  let html = "";
  let inList = false;

  for (const line of lines) {
    if (/^###\s+/.test(line)) {
      if (inList) { html += "</ul>"; inList = false; }
      html += `<h3>${line.replace(/^###\s+/, "")}</h3>`;
    } else if (/^##\s+/.test(line)) {
      if (inList) { html += "</ul>"; inList = false; }
      html += `<h2>${line.replace(/^##\s+/, "")}</h2>`;
    } else if (/^#\s+/.test(line)) {
      if (inList) { html += "</ul>"; inList = false; }
      html += `<h1>${line.replace(/^#\s+/, "")}</h1>`;
    } else if (/^[-*]\s+/.test(line)) {
      if (!inList) { html += "<ul>"; inList = true; }
      html += `<li>${line.replace(/^[-*]\s+/, "")}</li>`;
    } else if (line.trim() === "") {
      if (inList) { html += "</ul>"; inList = false; }
      html += "<br />";
    } else {
      if (inList) { html += "</ul>"; inList = false; }
      html += `<p>${line}</p>`;
    }
  }

  if (inList) html += "</ul>";

  return html
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
}

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(value = "") {
  return escapeHtml(value).replaceAll("\n", " ");
}

function formatDate(iso) {
  const date = new Date(iso);
  return new Intl.DateTimeFormat("ko-KR", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}
