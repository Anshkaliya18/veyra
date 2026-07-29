document.querySelector("[data-auth]")?.addEventListener("submit", async (e) => {
  e.preventDefault();

  const form = e.currentTarget;
  const button = form.querySelector("[type=submit]");

  let errorBox = form.querySelector("[data-error]");

  if (!errorBox) {
    errorBox = document.createElement("p");
    errorBox.setAttribute("data-error", "true");
    errorBox.style.color = "#ff6b6b";
    errorBox.style.marginTop = "0.75rem";
    form.appendChild(errorBox);
  }

  errorBox.textContent = "";

  const originalText = button.innerHTML;

  button.innerHTML = "Opening your workspace...";
  button.disabled = true;

  const formData = new FormData(form);

  try {
    const response = await fetch("/login", {
      method: "POST",
      body: formData,
      headers: {
        "X-Requested-With": "XMLHttpRequest",
      },
    });

    const data = await response.json();

    if (data.success) {
    window.location.href = data.redirect;
    } else {
        alert(data.error);
    }

    if (!response.ok) {
      throw new Error(data.error || "Login failed");
    }

    window.location.href = data.redirect || "/dashboard";

  } catch (error) {

    button.innerHTML = originalText;
    button.disabled = false;

    errorBox.textContent = error.message;
  }
});