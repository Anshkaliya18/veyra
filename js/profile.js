document.querySelectorAll(".profile-header .btn").forEach((button) =>
  button.addEventListener("click", (e) => {
    e.preventDefault();
    button.innerHTML = "Link copied <span>✓</span>";
    setTimeout(
      () => (button.innerHTML = "Share profile <span>↗</span>"),
      1600,
    );
  }),
);
