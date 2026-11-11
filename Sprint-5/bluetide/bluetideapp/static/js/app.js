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

    /* Announcements and the undo snackbar ---------------------------------- */

    const liveRegion = document.querySelector("[data-live-region]");
    const announce = (text) => {
        if (!liveRegion) return;
        liveRegion.textContent = "";
        window.setTimeout(() => {
            liveRegion.textContent = text;
        }, 50);
    };

    const snackbar = document.querySelector("[data-snackbar]");
    const snackbarText = snackbar?.querySelector("[data-snackbar-text]");
    const snackbarUndo = snackbar?.querySelector("[data-snackbar-undo]");
    const snackbarProgress = snackbar?.querySelector("[data-snackbar-progress]");
    let undoAction = null;

    const hideSnackbar = () => {
        if (!snackbar) return;
        const hadFocus = snackbar.contains(document.activeElement);
        snackbar.classList.remove("is-visible", "is-static", "has-undo");
        undoAction = null;
        if (hadFocus) document.getElementById("conteudo")?.focus();
    };

    // The progress bar is a CSS animation, so hovering or keyboard focus pauses
    // the countdown and the undo offer only expires when the bar actually ends.
    const showSnackbar = (text, { onUndo = null } = {}) => {
        if (!snackbar) return;
        snackbar.classList.remove("is-visible", "is-static");
        snackbarText.textContent = text;
        undoAction = onUndo;
        snackbarUndo.hidden = !onUndo;
        snackbar.classList.toggle("has-undo", Boolean(onUndo));
        void snackbar.offsetWidth;
        snackbar.classList.add("is-visible");
        announce(onUndo ? `${text} Use Desfazer para restaurar.` : text);
    };

    snackbarProgress?.addEventListener("animationend", hideSnackbar);
    snackbar?.querySelector("[data-snackbar-close]")?.addEventListener("click", hideSnackbar);
    snackbarUndo?.addEventListener("submit", (event) => {
        if (!undoAction) return;
        event.preventDefault();
        const action = undoAction;
        hideSnackbar();
        action();
    });

    /* Favorites -------------------------------------------------------------- */

    const csrfToken = () => document.querySelector("[name=csrfmiddlewaretoken]")?.value ?? "";

    const postFavorite = async (url) => {
        const response = await fetch(url, {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken(), "X-Requested-With": "XMLHttpRequest" },
            credentials: "same-origin",
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
    };

    const favoritesGrid = document.querySelector("[data-favorites-grid]");
    const favoritesEmpty = document.querySelector("[data-favorites-empty]");
    const compareFavorites = document.querySelector("[data-compare-favorites]");

    const syncFavoritesPage = () => {
        if (!favoritesGrid) return;
        const visible = [...favoritesGrid.querySelectorAll("[data-favorite-card]")].filter((card) => !card.hidden);
        if (favoritesEmpty) favoritesEmpty.hidden = visible.length > 0;
        if (compareFavorites) {
            compareFavorites.hidden = visible.length === 0;
            const points = visible.map((card) => `&ponto=${encodeURIComponent(card.dataset.slug)}`).join("");
            compareFavorites.href = `${compareFavorites.dataset.compareBase}${points}`;
        }
    };

    const setFavoriteState = (form, favorite) => {
        const button = form.querySelector(".heart");
        const name = form.dataset.name;
        form.dataset.favorite = String(favorite);
        form.action = favorite ? form.dataset.removeUrl : form.dataset.restoreUrl;
        button.classList.toggle("is-favorite", favorite);
        button.setAttribute("aria-label", favorite ? `Remover ${name} dos favoritos` : `Adicionar ${name} aos favoritos`);
        button.title = favorite ? "Remover dos favoritos" : "Adicionar aos favoritos";
    };

    const failure = () => showSnackbar("Não foi possível atualizar os favoritos. Verifique a conexão e tente de novo.");

    const restoreFavorite = async (form, card) => {
        try {
            await postFavorite(form.dataset.restoreUrl);
        } catch {
            failure();
            return;
        }
        setFavoriteState(form, true);
        if (card) card.hidden = false;
        syncFavoritesPage();
        form.querySelector(".heart")?.focus({ preventScroll: false });
        showSnackbar(`${form.dataset.name} voltou para os favoritos.`);
    };

    document.addEventListener("submit", async (event) => {
        const form = event.target.closest("[data-favorite-form]");
        if (!form) return;
        event.preventDefault();
        if (form.dataset.busy === "true") return;
        form.dataset.busy = "true";
        const removing = form.dataset.favorite === "true";
        const card = favoritesGrid?.contains(form) ? form.closest("[data-favorite-card]") : null;
        try {
            await postFavorite(removing ? form.dataset.removeUrl : form.dataset.restoreUrl);
        } catch {
            failure();
            return;
        } finally {
            form.dataset.busy = "false";
        }
        setFavoriteState(form, !removing);
        if (!removing) {
            showSnackbar(`${form.dataset.name} entrou nos favoritos.`);
            return;
        }
        if (card) {
            card.hidden = true;
            syncFavoritesPage();
        }
        showSnackbar(`${form.dataset.name} saiu dos favoritos.`, {
            onUndo: () => restoreFavorite(form, card),
        });
        if (card) snackbar?.querySelector(".snackbar-action")?.focus();
    });

    /* Dialogs ---------------------------------------------------------------- */

    document.querySelectorAll("[data-dialog-open]").forEach((trigger) => {
        const dialog = document.getElementById(trigger.dataset.dialogOpen);
        if (!dialog || typeof dialog.showModal !== "function") return;
        trigger.addEventListener("click", (event) => {
            event.preventDefault();
            dialog.showModal();
        });
        dialog.addEventListener("click", (event) => {
            if (event.target === dialog) dialog.close();
        });
        dialog.querySelectorAll("[data-dialog-close]").forEach((button) => {
            button.addEventListener("click", () => dialog.close());
        });
    });

    /* Forms ------------------------------------------------------------------ */

    /* Long forms list their errors in a summary at the top. Short forms, like
       the 6-digit code, may sit below the fold on a phone, so the first invalid
       field is brought to the middle of the screen and focused instead. */
    const errorSummary = document.querySelector("[data-error-summary]");
    const firstInvalid = document.querySelector("[aria-invalid='true']");
    if (errorSummary) {
        errorSummary.focus();
    } else if (firstInvalid) {
        firstInvalid.closest(".field")?.scrollIntoView({ block: "center" });
        firstInvalid.focus({ preventScroll: true });
        // A rejected code is replaced by typing the next one.
        if (firstInvalid.closest(".field-code")) firstInvalid.select();
    }

    const emailConfirm = document.querySelector("[data-email-confirm]");
    const emailInput = document.querySelector("input[name=email]");
    if (emailConfirm && emailInput && !emailConfirm.querySelector(".has-error")) {
        const original = emailInput.value.trim().toLowerCase();
        const sync = () => {
            emailConfirm.hidden = emailInput.value.trim().toLowerCase() === original;
        };
        emailInput.addEventListener("input", sync);
        sync();
    }

    const photoInput = document.querySelector("[data-photo-input]");
    const photoPreview = document.querySelector("[data-photo-preview]");
    const photoName = document.querySelector("[data-photo-name]");
    photoInput?.addEventListener("change", () => {
        const [file] = photoInput.files;
        if (photoName) photoName.textContent = file ? file.name : "";
        // The "pick the photo again" notice is answered once a file is chosen.
        if (file) document.querySelector("[data-photo-notice]")?.remove();
        if (!file || !file.type.startsWith("image/")) return;
        const image = document.createElement("img");
        image.alt = "";
        image.src = URL.createObjectURL(file);
        photoPreview.replaceChildren(image);
    });

    const copyText = async (button, text) => {
        try {
            await navigator.clipboard.writeText(text);
            const label = button.textContent;
            button.textContent = button.dataset.copyFeedback || "Copiado";
            announce(button.textContent);
            window.setTimeout(() => {
                button.textContent = label;
            }, 2000);
        } catch {
            announce("Não foi possível copiar. Selecione o texto e copie manualmente.");
        }
    };

    const recoveryCodes = () =>
        [...document.querySelectorAll("[data-recovery-codes] code")].map((code) => code.textContent.trim());

    document.querySelectorAll("[data-copy-value]").forEach((button) => {
        button.addEventListener("click", () => copyText(button, button.dataset.copyValue));
    });
    document.querySelectorAll("[data-copy-codes]").forEach((button) => {
        button.addEventListener("click", () => copyText(button, recoveryCodes().join("\n")));
    });
    document.querySelectorAll("[data-download-codes]").forEach((button) => {
        button.addEventListener("click", () => {
            const content = `Códigos de recuperação BlueTide\nCada código funciona uma única vez.\n\n${recoveryCodes().join("\n")}\n`;
            const link = document.createElement("a");
            link.href = URL.createObjectURL(new Blob([content], { type: "text/plain" }));
            link.download = "bluetide-codigos-de-recuperacao.txt";
            link.click();
            window.setTimeout(() => URL.revokeObjectURL(link.href), 1000);
        });
    });
})();
