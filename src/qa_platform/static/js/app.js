/* Mejoras progresivas de interfaz: navegación, filtros y visibilidad de clave */
document.documentElement.classList.add("has-js");

document.addEventListener("DOMContentLoaded", () => {
  /* 1. Separación visual del header transparente al hacer scroll en portada */
  const overlayHeader = document.querySelector(".header-nav--overlay");
  if (overlayHeader) {
    const syncHeaderState = () => {
      overlayHeader.classList.toggle("is-scrolled", window.scrollY > 24);
    };
    syncHeaderState();
    window.addEventListener("scroll", syncHeaderState, { passive: true });
  }

  /* 2. Menú móvil accesible */
  const navToggle = document.querySelector(".nav-toggle");
  const navLinks = document.getElementById("primary-nav");
  if (navToggle && navLinks) {
    navToggle.addEventListener("click", () => {
      const isOpen = navToggle.getAttribute("aria-expanded") === "true";
      navToggle.setAttribute("aria-expanded", String(!isOpen));
      navLinks.classList.toggle("is-open", !isOpen);
    });
  }

  /* 3. Alternar visibilidad de contraseña */
  document.querySelectorAll(".password-toggle").forEach((toggleBtn) => {
    const targetId = toggleBtn.getAttribute("data-target");
    const input = targetId ? document.getElementById(targetId) : null;
    if (!input) return;

    toggleBtn.addEventListener("click", () => {
      const showing = input.type === "text";
      input.type = showing ? "password" : "text";
      toggleBtn.setAttribute("aria-pressed", String(!showing));
      toggleBtn.setAttribute(
        "aria-label",
        showing ? "Mostrar contraseña" : "Ocultar contraseña",
      );
    });
  });

  /* 4. Filtro instantáneo en el listado de preguntas */
  const filterInput = document.getElementById("question-filter");
  const questionCards = Array.from(document.querySelectorAll(".question-card"));
  const filterStatus = document.getElementById("question-filter-status");
  const emptyFilterMsg = document.getElementById("question-filter-empty");

  if (filterInput && questionCards.length > 0) {
    const total = questionCards.length;
    filterInput.addEventListener("input", () => {
      const term = filterInput.value.trim().toLowerCase();
      let visibleCount = 0;

      questionCards.forEach((card) => {
        const text = card.textContent.toLowerCase();
        const matches = !term || text.includes(term);
        card.hidden = !matches;
        if (matches) visibleCount += 1;
      });

      if (filterStatus) {
        filterStatus.textContent = term
          ? `${visibleCount} de ${total} preguntas`
          : `${total} preguntas`;
      }
      if (emptyFilterMsg) {
        emptyFilterMsg.hidden = visibleCount > 0;
      }
    });
  }
});
