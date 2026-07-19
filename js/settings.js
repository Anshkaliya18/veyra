document
  .querySelectorAll(".switch")
  .forEach((s) => s.addEventListener("click", () => s.classList.toggle("on")));
document.querySelectorAll("[data-panel]").forEach((link) =>
  link.addEventListener("click", (e) => {
    e.preventDefault();
    const id = link.dataset.panel;
    document
      .querySelectorAll("[data-panel]")
      .forEach((x) => x.classList.toggle("active", x === link));
    document
      .querySelectorAll(".setting-panel")
      .forEach((panel) => (panel.hidden = panel.id !== id));
  }),
);
document.querySelector("#delete-workspace")?.addEventListener("click", () => {
  const button = document.querySelector("#delete-workspace");
  button.textContent = "Deletion requires confirmation";
  setTimeout(() => (button.textContent = "Delete workspace"), 2000);
});
