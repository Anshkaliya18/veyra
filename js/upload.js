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
input?.addEventListener("change", (e) => addFiles(e.target.files));
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
zone?.addEventListener("drop", (e) => addFiles(e.dataTransfer.files));
document.querySelector("#clear-files")?.addEventListener("click", () =>
  document.querySelectorAll("#file-list .file-row").forEach((row) => {
    if (row.querySelector(".status")?.textContent.includes("Ready"))
      row.style.opacity = ".25";
  }),
);
