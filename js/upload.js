function $(selector, root = document) {
  return root.querySelector(selector);
}

function $all(selector, root = document) {
  return Array.from(root.querySelectorAll(selector));
}

const zone = $("#dropzone");
const input = $("#file-input");
const list = $("#file-list");

const ALLOWED_EXTENSIONS = [
  "pdf",
  "doc",
  "docx",
  "txt",
  "csv",
  "xlsx",
  "xls",
  "png",
  "jpg",
  "jpeg",
];

function getExtension(filename) {
  if (!filename || !filename.includes(".")) return "";
  return filename.split(".").pop().toLowerCase().trim();
}

function isHiddenFile(filename) {
  return filename.startsWith(".") && filename.indexOf(".", 1) === -1;
}

function isAllowedFile(file) {
  if (isHiddenFile(file.name)) return false;
  const ext = getExtension(file.name);
  return ext !== "" && ALLOWED_EXTENSIONS.includes(ext);
}

function partitionFiles(files) {
  const valid = [];
  const invalid = [];

  [...files].forEach((file) => {
    if (isHiddenFile(file.name)) return;
    (isAllowedFile(file) ? valid : invalid).push(file);
  });

  return { valid, invalid };
}

function showUploadError(message) {
  let toast = $("#upload-toast");

  if (!toast) {
    toast = document.createElement("div");
    toast.id = "upload-toast";
    toast.className = "upload-toast";
    document.body.appendChild(toast);
  }

  toast.textContent = message;
  toast.classList.add("show");

  clearTimeout(toast._hideTimer);
  toast._hideTimer = setTimeout(() => toast.classList.remove("show"), 4500);
}

function describeInvalidFiles(invalidFiles) {
  const names = invalidFiles.map((f) => f.name).join(", ");
  const noun = invalidFiles.length === 1 ? "file" : "files";
  return `Unsupported ${noun}: ${names}. Allowed types: ${ALLOWED_EXTENSIONS.join(", ").toUpperCase()}.`;
}

function iconFor(file) {
  return file.name.split(".").pop().slice(0, 3).toUpperCase();
}

function formatFileSize(bytes) {
  if (!bytes || Number.isNaN(bytes)) return "Unknown size";
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

function formatDate(value) {
  if (!value) return "Recently";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Recently";
  return date.toLocaleString();
}

function safeText(value, fallback = "") {
  return value == null || value === "" ? fallback : String(value);
}

function createFileRowFromUpload(file) {
  const row = document.createElement("div");
  row.className = "file-row";
  row.dataset.tempRow = "true";

  row.innerHTML = `
    <div class="file-main">
      <span class="file-icon">${iconFor(file)}</span>
      <div>
        <b>${safeText(file.name, "Unnamed file")}</b>
        <span>${formatFileSize(file.size)} · Just now</span>
      </div>
    </div>
    <span class="badge">Analyzing</span>
    <div class="progress-line"><i style="--p:8%"></i></div>
    <span class="status">8%</span>
  `;

  return row;
}

function createFileRowFromDb(file) {
  const ext = (safeText(file.original_filename, "FILE"))
    .split(".")
    .pop()
    .slice(0, 3)
    .toUpperCase();

  const row = document.createElement("div");
  row.className = "file-row";
  row.dataset.fileId = safeText(file.id, "");

  row.innerHTML = `
    <div class="file-main">
      <span class="file-icon">${ext}</span>
      <div>
        <b>${safeText(file.original_filename, "Unnamed file")}</b>
        <span>${formatFileSize(file.file_size)} · ${formatDate(file.created_at)}</span>
      </div>
    </div>

    <span class="badge">${safeText(file.upload_status, "uploaded")}</span>

    <div class="progress-line"><i style="--p:100%"></i></div>

    <span class="status">✓ Ready</span>

    <div class="file-actions">
      <a href="${safeText(file.file_url, "#")}" target="_blank" rel="noopener noreferrer">
        Open
      </a>
      <button type="button" class="delete-btn" data-delete-file-id="${safeText(file.id, "")}">
        Delete
      </button>
    </div>
  `;

  return row;
}

function ensureFileListEmptyState(container) {
  container.innerHTML = `
    <div class="file-row">
      <div class="file-main">
        <span class="file-icon">---</span>
        <div>
          <b>No uploaded files found</b>
          <span>Upload a document to see it here</span>
        </div>
      </div>
      <span class="badge">Empty</span>
      <div class="progress-line"><i style="--p:0%"></i></div>
      <span class="status">—</span>
    </div>
  `;
}

function getFilesFromApiResponse(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.files)) return data.files;
  return [];
}

function setRowStatus(row, { badge, status, progress }) {
  const badgeEl = row.querySelector(".badge");
  const statusEl = row.querySelector(".status");
  const progressEl = row.querySelector(".progress-line i");

  if (badgeEl && badge) badgeEl.textContent = badge;
  if (statusEl && status) statusEl.textContent = status;
  if (progressEl && progress) progressEl.style.setProperty("--p", progress);
}

async function uploadFiles(files) {
  const rows = $all("#file-list .file-row").filter(
    (row) => row.dataset.tempRow === "true"
  );

  for (let index = 0; index < files.length; index++) {
    const file = files[index];
    const row = rows[index];
    if (!row) continue;

    setRowStatus(row, {
      badge: "Uploading",
      status: "Uploading...",
      progress: "25%",
    });

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("/upload", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        setRowStatus(row, {
          badge: "Failed",
          status: "✗ Failed",
          progress: "100%",
        });
        continue;
      }

      setRowStatus(row, {
        badge: "Uploaded",
        status: "✓ Ready",
        progress: "100%",
      });

      row.dataset.tempRow = "done";
    } catch (err) {
      console.error("Upload failed:", err);
      setRowStatus(row, {
        badge: "Failed",
        status: "✗ Failed",
        progress: "100%",
      });
    }
  }

  await loadFiles();
}

async function deleteFile(fileId) {
  if (!fileId) return;
  if (!confirm("Delete this file?")) return;

  try {
    const response = await fetch(`/delete-file/${fileId}`, {
      method: "DELETE",
    });

    const data = await response.json();

    if (data.success) {
      await loadFiles();
    } else {
      alert(data.message || "Delete failed.");
    }
  } catch (err) {
    console.error("Delete failed:", err);
    alert("Delete failed.");
  }
}

async function loadFiles() {
  try {
    const response = await fetch("/api/files", {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.message || "Failed to load files");
    }

    const files = getFilesFromApiResponse(data);
    const container = $("#file-list");

    if (!container) {
      console.error("file-list container not found");
      return;
    }

    container.innerHTML = "";

    if (files.length === 0) {
      ensureFileListEmptyState(container);
      return;
    }

    files.forEach((file) => {
      container.appendChild(createFileRowFromDb(file));
    });
  } catch (error) {
    console.error("Load Files Error:", error);
  }
}

input?.addEventListener("change", async (e) => {
  const { valid, invalid } = partitionFiles(e.target.files);

  if (invalid.length > 0) {
    showUploadError(describeInvalidFiles(invalid));
  }

  if (valid.length > 0) {
    // Add optimistic rows first so the user sees immediate feedback
    valid.forEach((file) => {
      list?.prepend(createFileRowFromUpload(file));
    });

    await uploadFiles(valid);
  }

  input.value = "";
});

["dragenter", "dragover"].forEach((type) =>
  zone?.addEventListener(type, (e) => {
    e.preventDefault();
    zone.classList.add("dragover");
  })
);

["dragleave", "drop"].forEach((type) =>
  zone?.addEventListener(type, (e) => {
    e.preventDefault();
    zone.classList.remove("dragover");
  })
);

zone?.addEventListener("drop", async (e) => {
  e.preventDefault();

  const { valid, invalid } = partitionFiles(e.dataTransfer.files);

  if (invalid.length > 0) {
    showUploadError(describeInvalidFiles(invalid));
  }

  if (valid.length > 0) {
    valid.forEach((file) => {
      list?.prepend(createFileRowFromUpload(file));
    });

    await uploadFiles(valid);
  }
});

$("#clear-files")?.addEventListener("click", () => {
  $all("#file-list .file-row").forEach((row) => {
    if (row.querySelector(".status")?.textContent.includes("Ready")) {
      row.style.opacity = ".25";
    }
  });
});

$("#file-list")?.addEventListener("click", async (e) => {
  const deleteButton = e.target.closest("[data-delete-file-id]");
  if (!deleteButton) return;

  const fileId = deleteButton.dataset.deleteFileId;
  await deleteFile(fileId);
});

document.addEventListener("DOMContentLoaded", () => {
  loadFiles();
});