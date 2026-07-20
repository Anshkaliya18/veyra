console.log("upload.js loaded");

const zone = document.querySelector("#dropzone"),
  input = document.querySelector("#file-input"),
  list = document.querySelector("#file-list");
const iconFor = (file) => file.name.split(".").pop().slice(0, 3).toUpperCase();
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

    addFiles(e.target.files);

    await uploadFiles(e.target.files);

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

    addFiles(e.dataTransfer.files);

    await uploadFiles(e.dataTransfer.files);

});
document.querySelector("#clear-files")?.addEventListener("click", () =>
  document.querySelectorAll("#file-list .file-row").forEach((row) => {
    if (row.querySelector(".status")?.textContent.includes("Ready"))
      row.style.opacity = ".25";
  }),
);

async function uploadFiles(files) {

    for (const file of files) {

        const formData = new FormData();
        formData.append("file", file);

        try {

            const response = await fetch("/upload", {
                method: "POST",
                body: formData
            });

            if (!response.ok) {
                const text = await response.text();
                console.error("Upload failed:", response.status, text);
                alert("Upload failed. Check the console.");
                return;
            }

            const data = await response.json();

            console.log("Server Response:", data);

            if (data.success) {
                await loadFiles();
            } else {
                alert(data.error || data.message || "Upload failed");
            }

        } catch (err) {
            console.error("Upload Error:", err);
        }
    }
}

async function loadFiles() {

    try {

        const response = await fetch("/api/files");

        if (!response.ok) {
            const text = await response.text();
            console.error("API Error:", response.status, text);
            return;
        }

        const files = await response.json();

        list.innerHTML = "";

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
    }
}

document.addEventListener("DOMContentLoaded",()=>{

    loadFiles();

});
