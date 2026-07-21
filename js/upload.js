console.log("upload.js loaded");

const zone = document.querySelector("#dropzone"),
  input = document.querySelector("#file-input"),
  list = document.querySelector("#file-list");
const iconFor = (file) => file.name.split(".").pop().slice(0, 3).toUpperCase();

// --- File type validation ---------------------------------------------------
// Keep this in sync with ALLOWED_EXTENSIONS in the Flask backend (main.py).
// This is a UX convenience layer only — the server re-validates every file,
// so this list being out of sync is not a security issue, just a UX one.
const ALLOWED_EXTENSIONS = ["pdf", "doc", "docx", "txt", "png", "jpg", "jpeg"];

// Pull the extension out of a filename, lowercase, no dot.
// Returns "" if there's no extension (e.g. "README").
function getExtension(filename) {
  if (!filename || !filename.includes(".")) return "";
  return filename.split(".").pop().toLowerCase().trim();
}

// True for dotfiles / OS metadata files like ".DS_Store" or ".gitignore" —
// these have a "." but no real name before it, so we skip them silently
// rather than flagging them as an "unsupported type" error.
function isHiddenFile(filename) {
  return filename.startsWith(".") && filename.indexOf(".", 1) === -1;
}

function isAllowedFile(file) {
  if (isHiddenFile(file.name)) return false;
  const ext = getExtension(file.name);
  return ext !== "" && ALLOWED_EXTENSIONS.includes(ext);
}

// Splits a FileList/array into { valid, invalid } based on extension.
function partitionFiles(files) {
  const valid = [];
  const invalid = [];
  [...files].forEach((file) => {
    if (isHiddenFile(file.name)) return; // ignore silently, not an error
    (isAllowedFile(file) ? valid : invalid).push(file);
  });
  return { valid, invalid };
}

// Lightweight toast for validation errors. Reuses the app's existing color
// tokens (see shared.css) so it matches the rest of the UI without needing
// a dedicated modal/alert component.
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
// -----------------------------------------------------------------------------

function addFiles(files) {
  [...files].forEach((file, index) => {
    const row = document.createElement("div");
    row.className = "file-row";
    row.innerHTML = `<div class="file-main"><span class="file-icon">${iconFor(file)}</span><div><b>${file.name}</b><span>${(file.size / 1024 / 1024).toFixed(1)} MB · Just now</span></div></div><span class="badge">Analyzing</span><div class="progress-line"><i style="--p:8%"></i></div><span class="status">8%</span>`;
    list.prepend(row);
    const bar = row.querySelector("i"),
      status = row.querySelector(".status");
    let p = 8;
    const timer = setInterval(
      () => {
        p = Math.min(p + Math.ceil(Math.random() * 14), 100);
        bar.style.setProperty("--p", p + "%");
        status.textContent = p < 100 ? p + "%" : "✓ Ready";
        if (p === 100) {
          row.querySelector(".badge").textContent = "Understood";
          clearInterval(timer);
        }
      },
      170 + index * 50,
    );
  });
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

    // Reset so selecting the same (rejected) file again re-triggers "change"
    input.value = "";

});
["dragenter", "dragover"].forEach((type) =>
  zone?.addEventListener(type, (e) => {
    e.preventDefault();
    zone.classList.add("dragover");
  }),
);
["dragleave", "drop"].forEach((type) =>
  zone?.addEventListener(type, (e) => {
    e.preventDefault();
    zone.classList.remove("dragover");
  }),
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
document.querySelector("#clear-files")?.addEventListener("click", () =>
  document.querySelectorAll("#file-list .file-row").forEach((row) => {
    if (row.querySelector(".status")?.textContent.includes("Ready"))
      row.style.opacity = ".25";
  }),
);

async function uploadFiles(files) {

    const rows = document.querySelectorAll("#file-list .file-row");

    for (let index = 0; index < files.length; index++) {

        const file = files[index];
        const row = rows[index];

        const badge = row.querySelector(".badge");
        const status = row.querySelector(".status");
        const progress = row.querySelector(".progress-line i");

        badge.textContent = "Uploading";
        status.innerHTML = `<span class="spinner"></span> Uploading...`;
        progress.style.setProperty("--p", "25%");

        const formData = new FormData();
        formData.append("file", file);

        try {

            const response = await fetch("/upload", {
                method: "POST",
                body: formData
            });

            const data = await response.json();

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

    await loadFiles(false);
}

async function loadFiles(showLoading = true) {

    if (showLoading) {
        list.innerHTML = `
            <div id="loading-row" class="loading-row">
                <div class="loader"></div>
                <span>Loading documents...</span>
            </div>`;
    }

    try {

        const response = await fetch("/api/files");

        if (!response.ok) {
            const text = await response.text();
            console.error("API Error:", response.status, text);
            list.innerHTML = `
                <div class="loading-row">
                    <span>Couldn't load your documents. Please try again.</span>
                </div>`;
            return;
        }

        const files = await response.json();

        list.innerHTML = "";

        if (files.length === 0) {
            list.innerHTML = `
                <div class="loading-row">
                    <span>No documents yet — upload your first one above.</span>
                </div>`;
            return;
        }

        files.forEach(file => {

            list.innerHTML += `
            <div class="file-row">
                <div class="file-main">
                    <span class="file-icon">${iconFor({ name: file.name })}</span>
                    <div>
                        <b>${file.name}</b>
                        <span>${(file.size / 1024 / 1024).toFixed(2)} MB</span>
                    </div>
                </div>

                <span class="badge">Uploaded</span>

                <div class="progress-line">
                    <i style="--p:100%"></i>
                </div>

                <span class="status">✓ Ready</span>
            </div>`;
        });

    } catch (err) {
        console.error("Load Files Error:", err);
        list.innerHTML = `
            <div class="loading-row">
                <span>Couldn't load your documents. Please try again.</span>
            </div>`;
    }
}

document.addEventListener("DOMContentLoaded",()=>{

    loadFiles();

});