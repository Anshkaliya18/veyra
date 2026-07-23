console.log("upload.js loaded");

const zone = document.querySelector("#dropzone");
const input = document.querySelector("#file-input");
const list = document.querySelector("#file-list");

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
  let toast = document.querySelector("#upload-toast");

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

function addFiles(files) {
  [...files].forEach((file, index) => {
    const row = document.createElement("div");
    row.className = "file-row";
    row.innerHTML = `
      <div class="file-main">
        <span class="file-icon">${iconFor(file)}</span>
        <div>
          <b>${file.name}</b>
          <span>${(file.size / 1024 / 1024).toFixed(1)} MB · Just now</span>
        </div>
      </div>
      <span class="badge">Analyzing</span>
      <div class="progress-line"><i style="--p:8%"></i></div>
      <span class="status">8%</span>
    `;

    list.prepend(row);

    const bar = row.querySelector("i");
    const status = row.querySelector(".status");
    let p = 8;

    const timer = setInterval(() => {
      p = Math.min(p + Math.ceil(Math.random() * 14), 100);
      bar.style.setProperty("--p", p + "%");
      status.textContent = p < 100 ? p + "%" : "✓ Ready";

      if (p === 100) {
        row.querySelector(".badge").textContent = "Understood";
        clearInterval(timer);
      }
    }, 170 + index * 50);
  });
}

async function uploadFiles(files) {
  console.log("uploadFiles called");
  const rows = document.querySelectorAll("#file-list .file-row");

  for (let index = 0; index < files.length; index++) {
    const file = files[index];
    const row = rows[index];

    if (!row) continue;

    const badge = row.querySelector(".badge");
    const status = row.querySelector(".status");
    const progress = row.querySelector(".progress-line i");

    badge.textContent = "Uploading";
    status.innerHTML = `<span class="spinner"></span> Uploading...`;
    progress.style.setProperty("--p", "25%");

    const formData = new FormData();
    formData.append("file", file);

    try {
      console.log("Sending request...");
      const response = await fetch("/upload", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();
      console.log("Response:", data);

      if (!response.ok || !data.success) {
        badge.textContent = "Failed";
        status.textContent = "✗ Failed";
        continue;
      }

      badge.textContent = "Uploaded";
      status.textContent = "✓ Ready";
      progress.style.setProperty("--p", "100%");
    } catch (err) {
      console.error(err);
      badge.textContent = "Failed";
      status.textContent = "✗ Failed";
    }
  }

  await loadFiles();
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

    const files = Array.isArray(data)
      ? data
      : Array.isArray(data.files)
      ? data.files
      : [];

    const container = document.getElementById("file-list");
    if (!container) {
      console.error("file-list container not found");
      return;
    }

    container.innerHTML = "";

    if (files.length === 0) {
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
      return;
    }

    files.forEach((file) => {
      const ext = (file.original_filename || "FILE")
        .split(".")
        .pop()
        .slice(0, 3)
        .toUpperCase();

      const sizeText = file.file_size
        ? `${(file.file_size / 1024).toFixed(1)} KB`
        : "Unknown size";

      const createdText = file.created_at
        ? new Date(file.created_at).toLocaleString()
        : "Recently";

      const row = document.createElement("div");
      row.className = "file-row";
      row.innerHTML = `
        <div class="file-main">
          <span class="file-icon">${ext}</span>
          <div>
            <b>${file.original_filename || "Unnamed file"}</b>
            <span>${sizeText} · ${createdText}</span>
          </div>
        </div>
        <span class="badge">${file.upload_status || "uploaded"}</span>
        <div class="progress-line"><i style="--p:100%"></i></div>
        <span class="status">✓ Ready</span>
        <div class="file-actions">
          <a href="${file.file_url}" target="_blank" rel="noopener noreferrer">Open</a>
        </div>
      `;

      container.appendChild(row);
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
    addFiles(valid);
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
    addFiles(valid);
    await uploadFiles(valid);
  }
});

document.querySelector("#clear-files")?.addEventListener("click", () => {
  document.querySelectorAll("#file-list .file-row").forEach((row) => {
    if (row.querySelector(".status")?.textContent.includes("Ready")) {
      row.style.opacity = ".25";
    }
  });
});

document.addEventListener("DOMContentLoaded", () => {
  loadFiles();
});