document.querySelector(".quick-search")?.addEventListener("submit", (e) => {
  e.preventDefault();
  const term = e.currentTarget.querySelector("input").value;
  location.href = "/search?q=" + encodeURIComponent(term);
});
