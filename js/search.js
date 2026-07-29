const searchInput = document.querySelector("#search-input");
const form = document.querySelector("#search-form");
const resultsCopy = document.querySelector("#results-copy");
const searchResults = document.querySelector("#search-results");
const suggestions = document.querySelectorAll(".suggestion");
const filterInputs = Array.from(document.querySelectorAll("[data-filter]"));
const filterCountEls = Array.from(document.querySelectorAll("[data-filter-count]"));

const state = {
  allDocuments: [],
  currentDocuments: [],
  lastQuery: "",
  mode: "all", // "all" | "ai"
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function getDocTitle(doc) {
  return (
    doc?.document?.title ||
    doc?.title ||
    doc?.original_filename ||
    doc?.filename ||
    "Untitled"
  );
}

function getDocSummary(doc) {
  return (
    doc?.summary ||
    doc?.document?.summary ||
    doc?.document?.purpose ||
    "No summary available."
  );
}

function getDocCategory(doc) {
  return (
    doc?.document?.category ||
    doc?.document?.document_type ||
    doc?.upload_status ||
    "Document"
  );
}

function getScorePercent(doc) {
  const raw = Number(doc?.score ?? doc?.document?.confidence ?? 0);
  const clamped = Math.max(0, Math.min(raw, 1));
  return Math.round(clamped * 100);
}

function inferResultType(doc) {
  const blob = `${doc?.document?.category || ""} ${doc?.document?.document_type || ""} ${doc?.title || ""} ${doc?.original_filename || ""} ${doc?.summary || ""} ${(Array.isArray(doc?.keywords) ? doc.keywords.join(" ") : "")}`.toLowerCase();

  if (/certificate|certification|credential|badge|license|award/.test(blob)) {
    return "credentials";
  }
  if (/project|portfolio|prototype|hackathon|app|website|system|build/.test(blob)) {
    return "projects";
  }
  return "documents";
}

function setFilterCounts(documents) {
  const counts = { all: documents.length, documents: 0, projects: 0, credentials: 0 };

  documents.forEach((doc) => {
    const type = inferResultType(doc);
    if (counts[type] !== undefined) counts[type] += 1;
  });

  filterCountEls.forEach((el) => {
    const key = el.dataset.filterCount;
    if (key && counts[key] !== undefined) {
      el.textContent = String(counts[key]);
    }
  });
}

function getActiveFilters() {
  const allChecked = document.querySelector('[data-filter="all"]')?.checked;
  if (allChecked) return new Set(["all"]);

  const selected = filterInputs
    .filter((input) => input.dataset.filter && input.dataset.filter !== "all" && input.checked)
    .map((input) => input.dataset.filter);

  return selected.length ? new Set(selected) : new Set(["all"]);
}

function buildDocumentCard(doc) {
  const title = escapeHtml(getDocTitle(doc));
  const summary = escapeHtml(getDocSummary(doc));
  const category = escapeHtml(getDocCategory(doc));
  const filename = escapeHtml(doc?.original_filename || doc?.filename || "Untitled");
  const score = getScorePercent(doc);

  return `
    <article class="document-card">
      <div class="doc-icon">DOC</div>

      <div class="doc-content">
        <h3>${title}</h3>
        <div class="doc-summary">${summary}</div>

        <div class="doc-meta">
          <span class="doc-chip">${category}</span>
          <span class="doc-chip">${filename}</span>
        </div>
      </div>

      <div class="doc-score">${score}% match</div>
    </article>
  `;
}

function buildAiAnswerCard(data, term) {
  const answer = window.marked ? marked.parse(data?.answer || "No answer returned.") : escapeHtml(data?.answer || "No answer returned.");
  const confidenceValue = Number(data?.confidence || 0);
  const confidence = Math.round(Math.max(0, Math.min(confidenceValue, 1)) * 100);

  return `
    <article class="ai-answer-card">
      <div class="ai-header">
        <div class="ai-title">
          <div class="ai-icon">AI</div>
          <div>
            <h2>Veyra Answer</h2>
            <p>Search for “${escapeHtml(term)}”</p>
          </div>
        </div>
        <div class="ai-confidence">${confidence}% confidence</div>
      </div>

      <div class="ai-answer">${answer}</div>
    </article>
  `;
}

function getVisibleDocuments() {
  const active = getActiveFilters();
  const docs = state.currentDocuments.length ? state.currentDocuments : state.allDocuments;

  if (active.has("all")) return docs;

  return docs.filter((doc) => active.has(inferResultType(doc)));
}

function renderDocuments(documents) {
  if (!searchResults) return;

  const visible = documents.length ? documents : [];
  setFilterCounts(state.currentDocuments.length ? state.currentDocuments : state.allDocuments);

  if (!visible.length) {
    searchResults.innerHTML = `
      <div class="loading-card">
        <h3 style="margin:0 0 8px;">No results</h3>
        <p class="muted" style="margin:0;">No documents match this filter.</p>
      </div>
    `;
    return;
  }

  searchResults.innerHTML = `
    <div class="documents-grid">
      ${visible.map((doc) => buildDocumentCard(doc)).join("")}
    </div>
  `;

  if (resultsCopy) {
    resultsCopy.textContent = `Showing ${visible.length} document${visible.length === 1 ? "" : "s"}`;
  }
}

function renderAllDocuments() {
  state.mode = "all";
  state.currentDocuments = [...state.allDocuments];
  renderDocuments(getVisibleDocuments());
}

async function loadAllDocuments() {
  try {
    if (resultsCopy) {
      resultsCopy.textContent = "Loading all documents...";
    }

    const response = await fetch("/api/search/documents");
    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(data.message || "Failed to load documents");
    }

    state.allDocuments = Array.isArray(data.documents) ? data.documents : [];
    state.currentDocuments = [...state.allDocuments];
    renderAllDocuments();
  } catch (error) {
    console.error(error);
    if (searchResults) {
      searchResults.innerHTML = `
        <div class="loading-card">
          <h3 style="margin:0 0 8px;">Could not load documents</h3>
          <p class="muted" style="margin:0;">Please refresh and try again.</p>
        </div>
      `;
    }
  }
}

async function runAiSearch(term) {
  const query = (term || "").trim();
  if (!query) {
    renderAllDocuments();
    return;
  }

  state.lastQuery = query;

  if (resultsCopy) {
    resultsCopy.textContent = `Veyra is searching for “${query}”…`;
  }

  searchResults.innerHTML = `
    <div class="loading-card">
      <div class="loading-spinner"></div>
      <h3 style="margin:0 0 8px;">Searching your documents</h3>
      <p class="muted" style="margin:0;">Veyra is connecting the relevant parts of your journey.</p>
    </div>
  `;

  try {
    const response = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });

    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(data.message || "Search failed");
    }

    state.mode = "ai";
    state.currentDocuments = Array.isArray(data.documents) ? data.documents : [];

    const visible = getVisibleDocuments();
    const aiCard = buildAiAnswerCard(data, query);
    const docGrid = visible.length
      ? `<div class="documents-grid">${visible.map((doc) => buildDocumentCard(doc)).join("")}</div>`
      : `
        <div class="loading-card">
          <h3 style="margin:0 0 8px;">No results in this filter</h3>
          <p class="muted" style="margin:0;">Change the filter selection or try a different query.</p>
        </div>
      `;

    searchResults.innerHTML = `${aiCard}${docGrid}`;
    setFilterCounts(state.currentDocuments);
    if (resultsCopy) {
      resultsCopy.textContent = `Veyra found ${visible.length} connected result${visible.length === 1 ? "" : "s"} for “${query}”`;
    }
  } catch (error) {
    console.error("Search failed:", error);
    searchResults.innerHTML = `
      <div class="loading-card">
        <h3 style="margin:0 0 8px;">Search failed</h3>
        <p class="muted" style="margin:0;">Something went wrong while searching.</p>
      </div>
    `;
  }
}

form?.addEventListener("submit", (e) => {
  e.preventDefault();
  runAiSearch(searchInput?.value);
});

suggestions.forEach((button) => {
  button.addEventListener("click", () => {
    if (!searchInput) return;
    searchInput.value = button.textContent.trim();
    runAiSearch(searchInput.value);
  });
});

filterInputs.forEach((input) => {
  input.addEventListener("change", () => {
    const all = document.querySelector('[data-filter="all"]');

    if (input.dataset.filter === "all" && input.checked) {
      filterInputs.forEach((item) => {
        if (item !== all) item.checked = false;
      });
    } else if (input.dataset.filter !== "all" && input.checked && all) {
      all.checked = false;
      const othersChecked = filterInputs.some(
        (item) => item.dataset.filter !== "all" && item.checked
      );
      if (!othersChecked) all.checked = true;
    }

    if (state.mode === "ai") {
      const visible = getVisibleDocuments();
      const aiCard = state.lastQuery
        ? buildAiAnswerCard({ answer: "Filtered search results", confidence: 1 }, state.lastQuery)
        : "";
      searchResults.innerHTML = `
        ${aiCard}
        ${
          visible.length
            ? `<div class="documents-grid">${visible.map((doc) => buildDocumentCard(doc)).join("")}</div>`
            : `
              <div class="loading-card">
                <h3 style="margin:0 0 8px;">No results in this filter</h3>
                <p class="muted" style="margin:0;">Change the filter selection or try a different query.</p>
              </div>
            `
        }
      `;
      setFilterCounts(state.currentDocuments);
    } else {
      renderDocuments(getVisibleDocuments());
    }
  });
});

document.addEventListener("DOMContentLoaded", async () => {
  await loadAllDocuments();
});