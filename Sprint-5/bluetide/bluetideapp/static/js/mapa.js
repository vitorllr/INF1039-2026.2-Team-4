(() => {
    const canvas = document.querySelector("[data-map-canvas]");
    const notice = document.querySelector("[data-map-notice]");
    const dataNode = document.getElementById("map-points");
    if (!canvas || !dataNode) return;

    const showNotice = () => {
        if (notice) notice.hidden = false;
    };

    if (typeof L === "undefined") {
        showNotice();
        return;
    }

    const points = JSON.parse(dataNode.textContent);
    const map = L.map(canvas, { minZoom: 12, maxZoom: 18, zoomControl: true, zoomSnap: 0.25 });
    map.attributionControl.setPrefix(false);

    let tilesLoaded = false;
    let tileErrors = 0;
    const tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        referrerPolicy: "strict-origin-when-cross-origin",
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>',
    });
    tiles.on("tileload", () => {
        tilesLoaded = true;
        if (notice) notice.hidden = true;
    });
    tiles.on("tileerror", () => {
        tileErrors += 1;
        if (!tilesLoaded && tileErrors >= 3) showNotice();
    });
    tiles.addTo(map);
    window.setTimeout(() => {
        if (!tilesLoaded) showNotice();
    }, 8000);

    const size = window.matchMedia("(max-width: 680px)").matches ? 32 : 40;
    const bounds = L.latLngBounds();
    points.forEach((point) => {
        const icon = L.divIcon({
            className: "map-marker",
            html: `<span class="map-pin-dot map-pin-${point.tone}">${point.posto}</span>`,
            iconSize: [size, size],
            iconAnchor: [size / 2, size / 2],
        });
        const marker = L.marker([point.lat, point.lng], {
            icon,
            keyboard: true,
            title: `${point.name}: ${point.label}`,
            alt: `${point.name}: ${point.label}`,
            riseOnHover: true,
        }).addTo(map);
        marker.bindTooltip(`<strong>${point.name}</strong><br>${point.label}`, { direction: "top", offset: [0, -size / 2] });
        marker.on("click", () => {
            window.location.href = point.url;
        });
        marker.on("add", () => {
            const element = marker.getElement();
            element?.setAttribute("role", "link");
            element?.addEventListener("keydown", (event) => {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    window.location.href = point.url;
                }
            });
            element?.addEventListener("focus", () => marker.openTooltip());
            element?.addEventListener("blur", () => marker.closeTooltip());
        });
        bounds.extend([point.lat, point.lng]);
    });

    map.fitBounds(bounds, { padding: [32, 32], maxZoom: 16 });
})();
