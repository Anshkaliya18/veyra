const search = document.querySelector("#search-input"),
  form = document.querySelector("#search-form"),
  copy = document.querySelector("#results-copy");
function runSearch(term) {
  if (!term.trim()) return;
  copy.textContent = "Veyra is connecting the relevant parts of your journey…";
  document
    .querySelectorAll(".result")
    .forEach((x) => (x.style.opacity = ".35"));
  setTimeout(() => {
    copy.textContent = `Veyra found 4 connected results for “${term}”`;
    document.querySelectorAll(".result").forEach((x, i) => {
      x.style.opacity = "1";
      x.style.transition = `opacity .4s ${i * 0.1}s`;
    });
  }, 450);
}
form?.addEventListener("submit", (e) => {
  e.preventDefault();
  runSearch(search.value);
});
document.querySelectorAll(".suggestion").forEach((button) =>
  button.addEventListener("click", () => {
    search.value = button.textContent;
    runSearch(search.value);
  }),
);
const q = new URLSearchParams(location.search).get("q");
if (q) {
  search.value = q;
  runSearch(q);
}
