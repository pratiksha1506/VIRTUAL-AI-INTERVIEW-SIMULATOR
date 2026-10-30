(function () {
  document.addEventListener("DOMContentLoaded", () => {
    const btn = document.createElement("button");
    btn.className = "theme-toggle";
    btn.type = "button";
    btn.title = "Toggle dark mode";
    btn.textContent = "🌙";
    btn.addEventListener("click", () => {
      const isDark = document.documentElement.getAttribute("data-theme") === "dark";
      document.documentElement.setAttribute("data-theme", isDark ? "light" : "dark");
      btn.textContent = isDark ? "🌙" : "☀️";
    });
    document.body.appendChild(btn);
  });
})();
