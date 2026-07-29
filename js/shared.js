document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".reveal").forEach((el) =>
    new IntersectionObserver(
      ([entry], o) => {
        if (entry.isIntersecting) {
          el.classList.add("show");
          o.unobserve(el);
        }
      },
      { threshold: 0.12 },
    ).observe(el),
  );
  document.querySelectorAll(".tilt").forEach((card) => {
    card.addEventListener("mousemove", (e) => {
      const r = card.getBoundingClientRect(),
        x = (e.clientX - r.left) / r.width - 0.5,
        y = (e.clientY - r.top) / r.height - 0.5;
      card.style.transform = `perspective(800px) rotateX(${y * -5}deg) rotateY(${x * 7}deg) translateY(-3px)`;
    });
    card.addEventListener("mouseleave", () => (card.style.transform = ""));
  });
  document.querySelectorAll("[data-magnetic]").forEach((btn) => {
    btn.addEventListener("mousemove", (e) => {
      const r = btn.getBoundingClientRect();
      btn.style.transform = `translate(${(e.clientX - r.left - r.width / 2) * 0.12}px,${(e.clientY - r.top - r.height / 2) * 0.18}px)`;
    });
    btn.addEventListener("mouseleave", () => (btn.style.transform = ""));
  });
  const menu = document.querySelector(".mobile-menu");
  if (menu)
    menu.addEventListener("click", () =>
      document.querySelector(".nav-links").classList.toggle("mobile-open"),
    );
});
