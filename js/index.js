document.querySelectorAll(".faq-question").forEach((button) =>
  button.addEventListener("click", () => {
    const item = button.closest(".faq-item");
    document.querySelectorAll(".faq-item").forEach((x) => {
      if (x !== item) x.classList.remove("open");
    });
    item.classList.toggle("open");
  }),
);
const counts = document.querySelectorAll(".count");
const countObserver = new IntersectionObserver(
  (entries) =>
    entries.forEach(({ isIntersecting, target }) => {
      if (!isIntersecting) return;
      const end = +target.dataset.count,
        start = performance.now();
      const tick = (now) => {
        const p = Math.min((now - start) / 1100, 1);
        target.textContent =
          Math.floor(end * (1 - Math.pow(1 - p, 3))) + (end === 100 ? "%" : "");
        if (p < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
      countObserver.unobserve(target);
    }),
  { threshold: 0.5 },
);
counts.forEach((x) => countObserver.observe(x));
