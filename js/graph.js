const stage = document.querySelector("#graph-stage"),
  canvas = document.querySelector("#graph-canvas");
let scale = 1,
  x = 0,
  y = 0,
  dragging = false,
  startX,
  startY;
function render() {
  canvas.style.transform = `translate(${x}px,${y}px) scale(${scale})`;
}
function zoom(amount) {
  scale = Math.min(1.8, Math.max(0.65, scale + amount));
  render();
}
document.querySelector("#zoom-in")?.addEventListener("click", () => zoom(0.12));
document
  .querySelector("#zoom-out")
  ?.addEventListener("click", () => zoom(-0.12));
document.querySelector("#reset-graph")?.addEventListener("click", () => {
  scale = 1;
  x = 0;
  y = 0;
  render();
});
stage?.addEventListener(
  "wheel",
  (e) => {
    e.preventDefault();
    zoom(e.deltaY < 0 ? 0.08 : -0.08);
  },
  { passive: false },
);
stage?.addEventListener("pointerdown", (e) => {
  dragging = true;
  startX = e.clientX - x;
  startY = e.clientY - y;
  stage.classList.add("dragging");
  stage.setPointerCapture(e.pointerId);
});
stage?.addEventListener("pointermove", (e) => {
  if (!dragging) return;
  x = e.clientX - startX;
  y = e.clientY - startY;
  render();
});
stage?.addEventListener("pointerup", () => {
  dragging = false;
  stage.classList.remove("dragging");
});
