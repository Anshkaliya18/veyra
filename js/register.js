document.querySelector("[data-auth]")?.addEventListener("submit", async (e) => {
  e.preventDefault();

  const form = e.currentTarget;
  const button = form.querySelector("[type=submit]");
  const errorBox = form.querySelector("[data-error]") || document.createElement("p");

  errorBox.setAttribute("data-error", "true");
  errorBox.style.color = "#ff6b6b";
  errorBox.style.marginTop = "0.75rem";

  if (!form.querySelector("[data-error]")) {
    form.appendChild(errorBox);
  }

  button.innerHTML = "Creating your identity…";
  button.disabled = true;

  const formData = new FormData(form);

  try {
    const response = await fetch("/signup", {
      method: "POST",
      body: formData,
      headers: {
        "X-Requested-With": "XMLHttpRequest",
      },
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(data.error || "Signup failed");
    }

    window.location.href = data.redirect || "/dashboard";
  } catch (error) {
    button.innerHTML = "Create my identity <span>→</span>";
    button.disabled = false;
    errorBox.textContent = error.message;
  }
});
