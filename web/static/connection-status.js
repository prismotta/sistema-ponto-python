(() => {
  const ID = "connection-status-banner";

  function ensure() {
    let el = document.getElementById(ID);
    if (el) return el;

    el = document.createElement("div");
    el.id = ID;
    el.style.position = "fixed";
    el.style.left = "0";
    el.style.right = "0";
    el.style.top = "0";
    el.style.zIndex = "1090";
    el.style.display = "none";
    el.style.padding = "0.5rem 0.75rem";
    el.style.textAlign = "center";
    el.style.fontWeight = "600";
    el.style.fontSize = "0.95rem";

    document.body.appendChild(el);
    return el;
  }

  function show(message, bg, fg, autoHideMs) {
    const el = ensure();
    el.textContent = message;
    el.style.background = bg;
    el.style.color = fg;
    el.style.display = "block";

    if (autoHideMs) {
      window.clearTimeout(show._t);
      show._t = window.setTimeout(() => {
        el.style.display = "none";
      }, autoHideMs);
    }
  }

  function onOffline() {
    show("Você está offline", "#dc3545", "white");
  }

  function onOnline() {
    show("Conectado novamente", "#198754", "white", 3000);
  }

  window.addEventListener("offline", onOffline);
  window.addEventListener("online", onOnline);

  // Initial state
  if (navigator.onLine === false) onOffline();
})();

