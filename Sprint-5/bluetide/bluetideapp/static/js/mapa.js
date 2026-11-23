(() => {
    const frame = document.querySelector("[data-coast-map]");
    const svg = frame?.querySelector("[data-map-svg]");
    if (!frame || !svg) return;

    const ART_W = 3900;
    const ART_H = 3000;
    const MAX_ZOOM = 6;
    const pins = [...svg.querySelectorAll(".map-pin")].map((link) => {
        const circle = link.querySelector(".map-pin-dot");
        const x = Number(circle.getAttribute("cx"));
        const y = Number(circle.getAttribute("cy"));
        link.style.transformOrigin = `${x}px ${y}px`;
        return { link, x, y };
    });

    const view = { x: 0, y: 0, w: ART_W, h: ART_H };
    let box = { w: 1, h: 1 };
    let baseW = ART_W;

    const pinPixels = () => (window.matchMedia("(max-width: 680px)").matches ? 15 : 22);

    const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

    const apply = () => {
        view.x = clamp(view.x, 0, ART_W - view.w);
        view.y = clamp(view.y, 0, ART_H - view.h);
        svg.setAttribute("viewBox", `${view.x} ${view.y} ${view.w} ${view.h}`);
        const unitsPerPixel = view.w / box.w;
        const scale = (pinPixels() * unitsPerPixel) / 125;
        pins.forEach(({ link }) => {
            link.style.transform = `scale(${scale})`;
        });
        frame.querySelector("[data-map-zoom-in]").disabled = view.w <= baseW / MAX_ZOOM + 1;
        frame.querySelector("[data-map-zoom-out]").disabled = view.w >= baseW - 1;
    };

    const setSize = (w) => {
        view.w = clamp(w, baseW / MAX_ZOOM, baseW);
        view.h = view.w * (box.h / box.w);
    };

    const zoomAt = (factor, px, py) => {
        const fx = view.x + (px / box.w) * view.w;
        const fy = view.y + (py / box.h) * view.h;
        setSize(view.w / factor);
        view.x = fx - (px / box.w) * view.w;
        view.y = fy - (py / box.h) * view.h;
        apply();
    };

    const fitPins = () => {
        const xs = pins.map((p) => p.x);
        const ys = pins.map((p) => p.y);
        const pad = 340;
        const minX = Math.min(...xs) - pad;
        const maxX = Math.max(...xs) + pad;
        const minY = Math.min(...ys) - pad;
        const maxY = Math.max(...ys) + pad;
        const aspect = box.w / box.h;
        const w = Math.max(maxX - minX, (maxY - minY) * aspect);
        setSize(w);
        view.x = (minX + maxX) / 2 - view.w / 2;
        view.y = (minY + maxY) / 2 - view.h / 2;
        apply();
    };

    const measure = () => {
        const rect = svg.getBoundingClientRect();
        box = { w: rect.width || 1, h: rect.height || 1 };
        baseW = Math.min(ART_W, ART_H * (box.w / box.h));
    };

    const reset = () => {
        measure();
        fitPins();
    };

    measure();
    fitPins();
    new ResizeObserver(() => {
        const centerX = view.x + view.w / 2;
        const centerY = view.y + view.h / 2;
        const ratio = view.w / baseW;
        measure();
        setSize(baseW * ratio);
        view.x = centerX - view.w / 2;
        view.y = centerY - view.h / 2;
        apply();
    }).observe(svg);

    frame.querySelector("[data-map-zoom-in]").addEventListener("click", () => zoomAt(1.6, box.w / 2, box.h / 2));
    frame.querySelector("[data-map-zoom-out]").addEventListener("click", () => zoomAt(1 / 1.6, box.w / 2, box.h / 2));
    frame.querySelector("[data-map-reset]").addEventListener("click", reset);

    svg.addEventListener(
        "wheel",
        (event) => {
            event.preventDefault();
            const rect = svg.getBoundingClientRect();
            zoomAt(Math.exp(-event.deltaY * 0.0018), event.clientX - rect.left, event.clientY - rect.top);
        },
        { passive: false },
    );

    const pointers = new Map();
    let dragged = false;
    let startPinch = null;

    svg.addEventListener("pointerdown", (event) => {
        pointers.set(event.pointerId, { x: event.clientX, y: event.clientY, startX: event.clientX, startY: event.clientY });
        dragged = false;
        if (pointers.size === 2) {
            const [a, b] = [...pointers.values()];
            startPinch = { distance: Math.hypot(a.x - b.x, a.y - b.y) };
        }
    });

    svg.addEventListener("pointermove", (event) => {
        const pointer = pointers.get(event.pointerId);
        if (!pointer) return;
        const dx = event.clientX - pointer.x;
        const dy = event.clientY - pointer.y;
        if (!dragged && Math.hypot(event.clientX - pointer.startX, event.clientY - pointer.startY) < 6) return;
        if (!dragged) {
            dragged = true;
            frame.classList.add("is-dragging");
            svg.setPointerCapture(event.pointerId);
        }
        pointer.x = event.clientX;
        pointer.y = event.clientY;
        if (pointers.size === 2 && startPinch) {
            const [a, b] = [...pointers.values()];
            const distance = Math.hypot(a.x - b.x, a.y - b.y);
            const rect = svg.getBoundingClientRect();
            zoomAt(distance / startPinch.distance, (a.x + b.x) / 2 - rect.left, (a.y + b.y) / 2 - rect.top);
            startPinch.distance = distance;
        } else if (pointers.size === 1) {
            view.x -= (dx / box.w) * view.w;
            view.y -= (dy / box.h) * view.h;
            apply();
        }
    });

    const endPointer = (event) => {
        pointers.delete(event.pointerId);
        startPinch = null;
        if (pointers.size === 0) frame.classList.remove("is-dragging");
    };
    svg.addEventListener("pointerup", endPointer);
    svg.addEventListener("pointercancel", endPointer);

    svg.addEventListener(
        "click",
        (event) => {
            if (dragged) {
                event.preventDefault();
                event.stopPropagation();
                dragged = false;
            }
        },
        true,
    );

    frame.addEventListener("keydown", (event) => {
        if (event.target !== frame) return;
        const step = view.w * 0.15;
        const keys = {
            ArrowLeft: () => ((view.x -= step), apply()),
            ArrowRight: () => ((view.x += step), apply()),
            ArrowUp: () => ((view.y -= step), apply()),
            ArrowDown: () => ((view.y += step), apply()),
            "+": () => zoomAt(1.6, box.w / 2, box.h / 2),
            "=": () => zoomAt(1.6, box.w / 2, box.h / 2),
            "-": () => zoomAt(1 / 1.6, box.w / 2, box.h / 2),
            0: reset,
        };
        if (keys[event.key]) {
            event.preventDefault();
            keys[event.key]();
        }
    });
})();
