(() => {
  const normalize = (pathname) => decodeURI(pathname)
    .replace(/\/index\.html$/i, "")
    .replace(/\/+$/, "");
  const currentPath = normalize(window.location.pathname);

  document.querySelectorAll('nav[aria-label="Main navigation"] a[href]').forEach((link) => {
    const url = new URL(link.href, window.location.href);
    if (url.origin !== window.location.origin) return;
    if (normalize(url.pathname) === currentPath) {
      link.setAttribute("aria-current", "page");
      const menu = link.closest("details[data-nav-menu]");
      if (menu) menu.querySelector(":scope > summary")?.setAttribute("aria-current", "location");
    }
  });

  document.querySelectorAll("details[data-nav-menu]").forEach((menu) => {
    menu.addEventListener("toggle", () => {
      if (!menu.open) return;
      menu.parentElement?.querySelectorAll(":scope > details[data-nav-menu]").forEach((other) => {
        if (other !== menu) other.open = false;
      });
    });
  });

  document.addEventListener("pointerdown", (event) => {
    document.querySelectorAll("details[data-nav-menu][open]").forEach((menu) => {
      if (!menu.contains(event.target)) menu.open = false;
    });
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    const openMenus = [...document.querySelectorAll("details[data-nav-menu][open]")];
    openMenus.forEach((menu) => { menu.open = false; });
    openMenus.at(-1)?.querySelector(":scope > summary")?.focus();
  });

  document.querySelectorAll('a[href^="http://"], a[href^="https://"]').forEach((link) => {
    const url = new URL(link.href, window.location.href);
    if (url.origin === window.location.origin) return;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
  });

  document.querySelectorAll(".faq-row").forEach((row) => {
    row.addEventListener("toggle", () => {
      if (!row.open) return;
      row.closest(".faq-accordion")?.querySelectorAll(".faq-row[open]").forEach((other) => {
        if (other !== row) other.open = false;
      });
    });
  });

  document.querySelectorAll(".open-peace-form").forEach((button) => {
    button.addEventListener("click", () => {
      const form = document.getElementById(button.getAttribute("aria-controls"));
      if (!form) return;
      form.hidden = !form.hidden;
      button.setAttribute("aria-expanded", String(!form.hidden));
      if (!form.hidden) form.querySelector("input, textarea")?.focus();
    });
  });

  document.querySelectorAll(".local-preview-form").forEach((form) => {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      const note = form.querySelector(".submission-note");
      if (note) note.textContent = "Your fields are valid. This form is not connected to a submission service, and nothing was sent.";
    });
  });
})();
