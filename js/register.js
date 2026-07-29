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

  const formData = new FormData(form);

  // The form only collects a single "name" field, but the backend
  // expects separate firstName / lastName values. Split it here.
  const fullName = (formData.get("name") || "").toString().trim();
  const [firstName, ...rest] = fullName.split(/\s+/);
  const lastName = rest.join(" ");

  if (!firstName) {
    errorBox.textContent = "Please enter your name";
    return;
  }

  const password = formData.get("password");
  const confirmPassword = formData.get("confirmPassword");
  if (password !== confirmPassword) {
    errorBox.textContent = "Passwords do not match.";
    return;
  }

  formData.set("firstName", firstName);
  formData.set("lastName", lastName);

  button.innerHTML = "Creating your identity…";
  button.disabled = true;

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
      throw new Error(data.message || data.error || "Signup failed");
    }

    window.location.href = data.redirect || "/dashboard";
  } catch (error) {
    button.innerHTML = "Create my identity <span>→</span>";
    button.disabled = false;
    errorBox.textContent = error.message;
  }
});