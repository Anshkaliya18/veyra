document
  .querySelectorAll(".event")
  .forEach((event, i) => (event.style.transitionDelay = `${i * 60}ms`));
