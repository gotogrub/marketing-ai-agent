const questionInput = document.querySelector("#questionInput");
const providerSelect = document.querySelector("#providerSelect");
const sendBtn = document.querySelector("#sendBtn");
const clearBtn = document.querySelector("#clearBtn");
const answerEl = document.querySelector("#answer");
const debugEl = document.querySelector("#debug");
const sourcesEl = document.querySelector("#sources");
const examplesEl = document.querySelector("#examples");
const intentBadge = document.querySelector("#intentBadge");
const providerBadge = document.querySelector("#providerBadge");
const healthProvider = document.querySelector("#healthProvider");
const healthToken = document.querySelector("#healthToken");
const latencyEl = document.querySelector("#latency");
const sourceCount = document.querySelector("#sourceCount");
const copyDebugBtn = document.querySelector("#copyDebugBtn");

// small ui to see how the agent responds

let lastDebug = {};

const fallbackExamples = [
  "Какой tone of voice у VerdaVita и дай 3 заголовка под TikTok?",
  "Give me 3 Amazon listing headline ideas for PureRoot Creatine Pure.",
  "Сравни Meta и TikTok по CTR и CPC",
  "Как использовать философию Жана Бодрийяра в продвижении бренда VerdaVita",
];

function setBusy(isBusy) {
  sendBtn.disabled = isBusy;
  sendBtn.innerHTML = isBusy
    ? '<span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>Run'
    : '<i class="bi bi-send"></i>Run';
}

function renderExamples(examples) {
  examplesEl.innerHTML = "";
  examples.forEach((question) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn btn-outline-secondary example-btn";
    button.textContent = question;
    button.addEventListener("click", () => {
      questionInput.value = question;
      runQuestion();
    });
    examplesEl.appendChild(button);
  });
}

function renderSources(sources) {
  sourceCount.textContent = String(sources.length);
  sourcesEl.innerHTML = "";

  if (!sources.length) {
    sourcesEl.innerHTML = '<div class="text-secondary small">No source chunks for this answer.</div>';
    return;
  }

  sources.forEach((source) => {
    const item = document.createElement("div");
    item.className = "source-item";
    item.innerHTML = `
      <div class="source-meta">
        <span class="badge text-bg-dark">${escapeHtml(source.brand || "brand")}</span>
        <span class="badge text-bg-light border">${escapeHtml(source.section || "section")}</span>
        <span class="badge text-bg-light border">${escapeHtml(source.source_file || "source")}</span>
      </div>
      <div class="small">${escapeHtml(source.text || "")}</div>
    `;
    sourcesEl.appendChild(item);
  });
}

function renderResponse(payload, startedAt) {
  const elapsed = Math.round(performance.now() - startedAt);
  answerEl.textContent = payload.answer || "";
  intentBadge.textContent = payload.intent || "unknown";
  intentBadge.className = payload.debug && payload.debug.guardrail
    ? "badge rounded-pill text-bg-warning"
    : "badge rounded-pill text-bg-secondary";
  providerBadge.textContent = payload.provider || "provider";
  latencyEl.textContent = `${elapsed} ms`;
  lastDebug = payload.debug || {};
  debugEl.textContent = JSON.stringify(lastDebug, null, 2);
  renderSources(payload.sources || []);
}

async function runQuestion() {
  const question = questionInput.value.trim();

  if (!question) {
    questionInput.focus();
    return;
  }

  setBusy(true);
  answerEl.textContent = "Running...";
  const startedAt = performance.now();

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        provider: providerSelect.value,
      }),
    });
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.error || `HTTP ${response.status}`);
    }

    renderResponse(payload, startedAt);
  } catch (error) {
    answerEl.textContent = `Error: ${error.message}`;
    intentBadge.textContent = "error";
    intentBadge.className = "badge rounded-pill text-bg-danger";
    latencyEl.textContent = "";
  } finally {
    setBusy(false);
  }
}

async function loadHealth() {
  try {
    const response = await fetch("/api/health");
    const payload = await response.json();
    healthProvider.textContent = `provider: ${payload.provider}`;

    const hf = payload.hf_token_present ? "HF yes" : "HF no";
    const sber = payload.sber_auth_present ? "Sber yes" : "Sber no";

    healthToken.textContent = `${hf} · ${sber}`;
  } catch {
    healthProvider.textContent = "provider: unknown";
    healthToken.textContent = "HF token: unknown";
  }
}

async function loadExamples() {
  try {
    const response = await fetch("/api/examples");
    const payload = await response.json();

    renderExamples(payload.examples || fallbackExamples);
    questionInput.value = (payload.examples || fallbackExamples)[0];
  } catch {
    renderExamples(fallbackExamples);
    questionInput.value = fallbackExamples[0];
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

sendBtn.addEventListener("click", runQuestion);
clearBtn.addEventListener("click", () => {
  questionInput.value = "";
  answerEl.textContent = "Выберите пример или задайте вопрос.";
  debugEl.textContent = "{}";
  sourcesEl.innerHTML = "";
  sourceCount.textContent = "0";
  intentBadge.textContent = "idle";
  intentBadge.className = "badge rounded-pill text-bg-secondary";
  providerBadge.textContent = "provider";
  latencyEl.textContent = "";
});

questionInput.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    runQuestion();
  }
});

copyDebugBtn.addEventListener("click", async () => {
  await navigator.clipboard.writeText(JSON.stringify(lastDebug, null, 2));
});

loadHealth();
loadExamples();
