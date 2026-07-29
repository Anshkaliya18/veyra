const searchInput = document.querySelector("#search-input");
const form = document.querySelector("#search-form");
const resultsCopy = document.querySelector("#results-copy");
const searchResults = document.querySelector("#search-results");
const suggestions = document.querySelectorAll(".suggestion");
const filterInputs = Array.from(document.querySelectorAll("[data-filter]"));
const filterCountEls = Array.from(document.querySelectorAll("[data-filter-count]"));

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setLoading(term) {
  if (resultsCopy) {
    resultsCopy.textContent = `Veyra is searching for “${term}”…`;
  }

  if (searchResults) {
    searchResults.innerHTML = `
      <div class="loading-card">
        <div class="loading-spinner"></div>
        <h3 style="margin:0 0 8px;">Searching your documents</h3>
        <p class="muted" style="margin:0;">
          Veyra is connecting the relevant parts of your journey.
        </p>
      </div>
    `;
  }
}

function renderNoResults(message) {
  if (!searchResults) return;

  searchResults.innerHTML = `
    <div class="loading-card">
      <h3 style="margin:0 0 8px;">No results</h3>
      <p class="muted" style="margin:0;">
        ${escapeHtml(message || "No matching documents found.")}
      </p>
    </div>
  `;
}

function formatKeywords(keywords) {
  if (!Array.isArray(keywords) || keywords.length === 0) return "";
  return keywords
    .slice(0, 6)
    .map((k) => `<span class="doc-chip">${escapeHtml(k)}</span>`)
    .join("");
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

function setFilterCounts(counts) {
  const total = counts.documents + counts.projects + counts.credentials;
  const values = {
    all: total,
    documents: counts.documents,
    projects: counts.projects,
    credentials: counts.credentials,
  };

  filterCountEls.forEach((el) => {
    const key = el.dataset.filterCount;
    if (key && key in values) {
      el.textContent = String(values[key]);
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

function applySearchFilters(data, term) {
  const documents = Array.isArray(data?.documents) ? data.documents : [];
  const counts = { documents: 0, projects: 0, credentials: 0 };

  const annotated = documents.map((doc) => {
    const type = inferResultType(doc);
    if (type in counts) counts[type] += 1;
    return { ...doc, __type: type };
  });

  setFilterCounts(counts);

  const active = getActiveFilters();
  const filtered = active.has("all")
    ? annotated
    : annotated.filter((doc) => active.has(doc.__type));

  if (resultsCopy) {
    resultsCopy.textContent = `Veyra found ${filtered.length} connected result${filtered.length === 1 ? "" : "s"} for “${term}”`;
  }

  return filtered;
}

function buildDocumentCard(doc) {
  const title = escapeHtml(getDocTitle(doc));
  const summary = escapeHtml(getDocSummary(doc));
  const category = escapeHtml(getDocCategory(doc));
  const filename = escapeHtml(doc?.original_filename || doc?.filename || "Untitled");
  const score = getScorePercent(doc);
  const keywords = formatKeywords(doc?.keywords || doc?.content?.keywords || doc?.metadata?.content?.keywords || []);

  return `
    <article class="document-card">
      <div class="doc-icon">DOC</div>

      <div class="doc-content">
        <h3>${title}</h3>
        <div class="doc-summary">${summary}</div>

        <div class="doc-meta">
          <span class="doc-chip">${category}</span>
          <span class="doc-chip">${filename}</span>
          ${keywords}
        </div>
      </div>

      <div class="doc-score">${score}% match</div>
    </article>
  `;
}

function buildAiAnswerCard(data, term) {
  const answer = marked.parse(data?.answer || "No answer returned.");
  const confidenceValue = Number(data?.confidence || 0);
  const confidence = Math.round(Math.max(0, Math.min(confidenceValue, 1)) * 100);

  const matched = Array.isArray(data?.matched_documents)
    ? data.matched_documents
    : [];

  const matchedHtml = matched.length
    ? `
      <div class="doc-meta" style="margin-top:16px;">
        ${matched
          .map((doc) => {
            const filename = escapeHtml(doc?.filename || doc?.original_filename || "Untitled");
            const reason = escapeHtml(doc?.reason || "Matched document");
            return `
              <span class="doc-chip">📄 ${filename}</span>
              <span class="doc-chip">${reason}</span>
            `;
          })
          .join("")}
      </div>
    `
    : "";

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
      ${matchedHtml}
    </article>
  `;
}

function renderResults(data, term) {
  if (!searchResults) return;

  const filteredDocs = applySearchFilters(data, term);
  const aiCard = buildAiAnswerCard(data, term);

  const documentCards = filteredDocs.length
    ? `
      <div class="documents-grid">
        ${filteredDocs
          .map(
            (doc) => `<div data-source-type="${escapeHtml(doc.__type || "documents")}">${buildDocumentCard(doc)}</div>`
          )
          .join("")}
      </div>
    `
    : `
      <div class="loading-card">
        <h3 style="margin:0 0 8px;">No results in this filter</h3>
        <p class="muted" style="margin:0;">
          Change the filter selection or try a different query.
        </p>
      </div>
    `;

  searchResults.innerHTML = `
    ${aiCard}
    ${documentCards}
  `;

  const mode = data?.mode || "ai";
  if (mode === "empty") {
    resultsCopy.textContent = "No documents are stored in your workspace yet.";
  }
}

async function runSearch(term) {
  const query = (term || "").trim();
  if (!query) return;

  setLoading(query);

  try {
    const response = await fetch("/api/search", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ query }),
    });

    const data = await response.json();

    if (!response.ok || !data.success) {
      renderNoResults(data.message || "Search failed.");
      return;
    }

    window.__veyraLastSearchData = data;
    renderResults(data, query);
  } catch (error) {
    console.error("Search failed:", error);
    renderNoResults("Something went wrong while searching.");
  }
}

form?.addEventListener("submit", (e) => {
  e.preventDefault();
  runSearch(searchInput?.value);
});

suggestions.forEach((button) => {
  button.addEventListener("click", () => {
    if (!searchInput) return;
    searchInput.value = button.textContent.trim();
    runSearch(searchInput.value);
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

    if (window.__veyraLastSearchData) {
      renderResults(window.__veyraLastSearchData, searchInput?.value || "");
    }
  });
});

const q = new URLSearchParams(location.search).get("q");
if (q && searchInput) {
  searchInput.value = q;
  runSearch(q);
}
