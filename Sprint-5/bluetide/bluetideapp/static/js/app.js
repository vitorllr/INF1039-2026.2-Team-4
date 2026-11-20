(() => {
    const body = document.body;
    const openButton = document.querySelector("[data-nav-open]");
    const closeButtons = document.querySelectorAll("[data-nav-close]");
    const sidebar = document.querySelector(".sidebar");
    const scrim = document.querySelector(".nav-scrim");
    const mobileQuery = window.matchMedia("(max-width: 980px)");

    const syncNavigationAccessibility = (open) => {
        if (mobileQuery.matches) {
            sidebar?.toggleAttribute("inert", !open);
            sidebar?.setAttribute("aria-hidden", String(!open));
            scrim?.setAttribute("aria-hidden", String(!open));
            if (scrim) scrim.tabIndex = open ? 0 : -1;
        } else {
            sidebar?.removeAttribute("inert");
            sidebar?.removeAttribute("aria-hidden");
            scrim?.setAttribute("aria-hidden", "true");
            if (scrim) scrim.tabIndex = -1;
        }
    };

    const setMenu = (open) => {
        body.classList.toggle("nav-open", open);
        openButton?.setAttribute("aria-expanded", String(open));
        syncNavigationAccessibility(open);
        if (open) {
            document.querySelector(".sidebar-close")?.focus();
        }
    };

    openButton?.addEventListener("click", () => setMenu(true));
    closeButtons.forEach((button) => button.addEventListener("click", () => setMenu(false)));
    mobileQuery.addEventListener("change", () => setMenu(false));
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && body.classList.contains("nav-open")) {
            setMenu(false);
            openButton?.focus();
        }
    });

    document.querySelectorAll("[data-toggle]").forEach((button) => {
        button.addEventListener("click", () => {
            const pressed = button.getAttribute("aria-pressed") === "true";
            button.setAttribute("aria-pressed", String(!pressed));
        });
    });

    syncNavigationAccessibility(false);
})();
