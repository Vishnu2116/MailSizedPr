document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("loginForm");
  const email = document.getElementById("email");
  const password = document.getElementById("password");
  const toggle = document.getElementById("passwordToggle");
  const success = document.getElementById("successMessage");

  toggle.addEventListener("click", () => {
    const type =
      password.getAttribute("type") === "password" ? "text" : "password";
    password.setAttribute("type", type);
    toggle.querySelector(".eye-icon").classList.toggle("show-password");
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = form.querySelector(".login-btn");
    btn.classList.add("loading");

    const formData = new FormData();
    formData.append("email", email.value.trim());
    formData.append("password", password.value.trim());

    try {
      const res = await fetch("/login", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();

      if (data.ok) {
        form.style.display = "none";
        success.classList.add("show");
        setTimeout(() => (window.location.href = data.redirect), 1500);
      } else {
        alert(data.message || "Invalid credentials");
      }
    } catch (err) {
      alert("Server error");
    } finally {
      btn.classList.remove("loading");
    }
  });
});
