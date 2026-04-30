(() => {
  if (!("serviceWorker" in navigator)) return;

  const BANNER_ID = "pwa-update-banner";
  let newWorker = null;
  let refreshing = false;

  function ensureBanner() {
    let banner = document.getElementById(BANNER_ID);
    if (banner) return banner;

    banner = document.createElement("div");
    banner.id = BANNER_ID;
    banner.style.position = "fixed";
    banner.style.left = "0";
    banner.style.right = "0";
    banner.style.bottom = "0";
    banner.style.zIndex = "1080";
    banner.style.padding = "0.75rem";
    banner.style.background = "#212529";
    banner.style.color = "white";
    banner.style.display = "none";

    const container = document.createElement("div");
    container.style.maxWidth = "960px";
    container.style.margin = "0 auto";
    container.style.display = "flex";
    container.style.gap = "0.75rem";
    container.style.alignItems = "center";
    container.style.justifyContent = "space-between";
    container.style.flexWrap = "wrap";

    const text = document.createElement("div");
    text.textContent = "Nova versão disponível";
    text.style.fontWeight = "600";

    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = "Atualizar";
    btn.className = "btn btn-light btn-sm";
    btn.id = `${BANNER_ID}-btn`;

    container.appendChild(text);
    container.appendChild(btn);
    banner.appendChild(container);
    document.body.appendChild(banner);

    return banner;
  }

  function showBanner() {
    const banner = ensureBanner();
    const btn = document.getElementById(`${BANNER_ID}-btn`);
    if (btn) {
      btn.onclick = () => {
        if (!newWorker) return;
        newWorker.postMessage({ type: "SKIP_WAITING" });
      };
    }
    banner.style.display = "block";
  }

  window.addEventListener("load", async () => {
    try {
      const registration = await navigator.serviceWorker.register("/service-worker.js");

      function promptUpdate() {
        if (!newWorker && registration.waiting) {
          newWorker = registration.waiting;
        }
        if (!newWorker) return;
        showBanner();
      }

      if (registration.waiting && navigator.serviceWorker.controller) {
        newWorker = registration.waiting;
        promptUpdate();
      }

      registration.addEventListener("updatefound", () => {
        const installingWorker = registration.installing;
        if (!installingWorker) return;

        installingWorker.addEventListener("statechange", () => {
          if (installingWorker.state === "installed" && navigator.serviceWorker.controller) {
            newWorker = installingWorker;
            promptUpdate();
          }
        });
      });

      navigator.serviceWorker.addEventListener("controllerchange", () => {
        if (refreshing) return;
        refreshing = true;
        window.location.reload();
      });
    } catch {
      // ignore SW registration errors
    }
  });
})();
