const apiBase = window.RESEARCH_API_BASE || "";
const form = document.querySelector("#research-form");
const submitButton = document.querySelector("#submit-button");
const pollButton = document.querySelector("#poll-button");
const statusTitle = document.querySelector("#status-title");
const jobMeta = document.querySelector("#job-meta");
const result = document.querySelector("#result");
const progress = document.querySelector("#progress");
const progressBar = document.querySelector("#progress-bar");

let currentJobId = "";
let pollTimer = null;

function payloadFromForm() {
  const data = new FormData(form);
  return {
    query: data.get("query").trim(),
    domain: data.get("domain"),
    depth: data.get("depth"),
    factCheck: data.get("factCheck") === "on",
    maxSources: Number(data.get("maxSources")),
    outputFormat: data.get("outputFormat"),
  };
}

async function requestJson(path, options = {}) {
  const response = await fetch(`${apiBase}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const text = await response.text();
  const body = text ? JSON.parse(text) : null;
  if (!response.ok) {
    throw new Error(body?.message || `Request failed with ${response.status}`);
  }
  return body;
}

function setBusy(isBusy) {
  submitButton.disabled = isBusy;
  submitButton.textContent = isBusy ? "Running" : "Run";
}

function showError(error) {
  statusTitle.textContent = "Error";
  result.innerHTML = `<span class="error">${error.message}</span>`;
}

function renderStatus(status) {
  const label = (status.status || "unknown").toLowerCase();
  statusTitle.textContent = status.status || "Unknown";
  statusTitle.className = `status-${label}`;
  currentJobId = status.jobId || currentJobId;
  pollButton.disabled = !currentJobId;

  const percent = Math.max(0, Math.min(100, status.progressPercent ?? 0));
  progress.hidden = false;
  progressBar.style.width = `${percent}%`;

  let progressLabel = document.querySelector("#progress-label");
  if (!progressLabel) {
    progressLabel = document.createElement("div");
    progressLabel.id = "progress-label";
    progressLabel.className = "progress-label";
    progress.after(progressLabel);
  }
  progressLabel.innerHTML = `<span>${status.currentStage || "Processing"}</span><span>${percent}%</span>`;

  jobMeta.innerHTML = [
    currentJobId ? `<div>Job: <strong>${currentJobId}</strong></div>` : "",
    status.query ? `<div>Query: ${status.query}</div>` : "",
  ].join("");

  result.textContent = JSON.stringify(status, null, 2);

  if (status.status === "COMPLETED") {
    stopPolling();
    fetchReport(currentJobId);
  }
  if (status.status === "FAILED") {
    stopPolling();
  }
}

function startPolling() {
  stopPolling();
  pollTimer = window.setInterval(() => {
    if (currentJobId) {
      pollStatus(currentJobId);
    }
  }, 2500);
}

function stopPolling() {
  if (pollTimer) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function pollStatus(jobId) {
  try {
    const status = await requestJson(`/api/research/jobs/${jobId}`);
    renderStatus(status);
  } catch (error) {
    stopPolling();
    showError(error);
  }
}

async function fetchReport(jobId) {
  try {
    const report = await requestJson(`/api/research/jobs/${jobId}/report`);
    result.textContent = JSON.stringify(report, null, 2);
  } catch (error) {
    showError(error);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setBusy(true);
  stopPolling();
  try {
    const accepted = await requestJson("/api/research/send", {
      method: "POST",
      body: JSON.stringify(payloadFromForm()),
    });
    currentJobId = accepted.jobId;
    statusTitle.textContent = accepted.status;
    jobMeta.innerHTML = `<div>Job: <strong>${currentJobId}</strong></div>`;
    result.textContent = JSON.stringify(accepted, null, 2);
    pollButton.disabled = false;
    startPolling();
  } catch (error) {
    showError(error);
  } finally {
    setBusy(false);
  }
});

pollButton.addEventListener("click", () => {
  if (currentJobId) {
    pollStatus(currentJobId);
  }
});
