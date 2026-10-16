(function () {
  const root = document.querySelector("[data-lay-viewer]");
  if (!root) return;

  const stage = root.querySelector("[data-lay-stage]");
  const svg = stage.querySelector("svg");
  const board = svg.querySelector("g.board");
  const layersBox = root.querySelector("[data-lay-layers]");
  const groups = Array.from(board.querySelectorAll(":scope > g[data-layer]"));

  const fit = svg.viewBox.baseVal;
  const home = { x: fit.x, y: fit.y, w: fit.width, h: fit.height };
  let view = Object.assign({}, home);

  svg.removeAttribute("width");
  svg.removeAttribute("height");

  // Порядок слоёв: ближняя к зрителю сторона рисуется последней
  const ORDER = {
    top: ["C2", "S2", "I1", "I2", "C1", "S1", "O", "M", "D"],
    bottom: ["C1", "S1", "I2", "I1", "C2", "S2", "O", "M", "D"],
  };

  function applyView() {
    svg.setAttribute("viewBox", [view.x, view.y, view.w, view.h].join(" "));
  }

  function setSide(side) {
    ORDER[side].forEach(function (id) {
      const g = groups.find(function (item) { return item.dataset.layer === id; });
      if (g) board.appendChild(g);
    });
    // Вид снизу — зеркально относительно вертикальной оси платы
    board.setAttribute(
      "transform",
      side === "bottom" ? "translate(" + (2 * home.x + home.w) + " 0) scale(-1 1)" : ""
    );
    root.querySelectorAll("[data-lay-side]").forEach(function (btn) {
      btn.classList.toggle("active", btn.dataset.laySide === side);
    });
  }

  groups.forEach(function (g) {
    const label = document.createElement("label");
    label.className = "lay-layer";
    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = true;
    box.addEventListener("change", function () {
      g.style.display = box.checked ? "" : "none";
    });
    const swatch = document.createElement("span");
    swatch.className = "lay-swatch";
    swatch.style.background = g.dataset.color;
    label.append(box, swatch, document.createTextNode(g.dataset.label));
    layersBox.appendChild(label);
  });

  function toSvgPoint(clientX, clientY) {
    const pt = svg.createSVGPoint();
    pt.x = clientX;
    pt.y = clientY;
    return pt.matrixTransform(svg.getScreenCTM().inverse());
  }

  function zoomAt(factor, clientX, clientY) {
    const w = Math.min(Math.max(view.w / factor, home.w / 40), home.w * 4);
    const real = view.w / w;
    const p = toSvgPoint(clientX, clientY);
    view = {
      x: p.x - (p.x - view.x) / real,
      y: p.y - (p.y - view.y) / real,
      w: w,
      h: view.h / real,
    };
    applyView();
  }

  function zoomCenter(factor) {
    const rect = svg.getBoundingClientRect();
    zoomAt(factor, rect.left + rect.width / 2, rect.top + rect.height / 2);
  }

  svg.addEventListener("wheel", function (event) {
    event.preventDefault();
    zoomAt(event.deltaY < 0 ? 1.2 : 1 / 1.2, event.clientX, event.clientY);
  }, { passive: false });

  const pointers = new Map();
  let pinchDistance = 0;

  svg.addEventListener("pointerdown", function (event) {
    svg.setPointerCapture(event.pointerId);
    pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    stage.classList.add("dragging");
  });

  svg.addEventListener("pointermove", function (event) {
    const prev = pointers.get(event.pointerId);
    if (!prev) return;
    const current = { x: event.clientX, y: event.clientY };

    if (pointers.size === 2) {
      pointers.set(event.pointerId, current);
      const [a, b] = Array.from(pointers.values());
      const distance = Math.hypot(a.x - b.x, a.y - b.y);
      if (pinchDistance) zoomAt(distance / pinchDistance, (a.x + b.x) / 2, (a.y + b.y) / 2);
      pinchDistance = distance;
      return;
    }

    const from = toSvgPoint(prev.x, prev.y);
    const to = toSvgPoint(current.x, current.y);
    view.x -= to.x - from.x;
    view.y -= to.y - from.y;
    pointers.set(event.pointerId, current);
    applyView();
  });

  function release(event) {
    pointers.delete(event.pointerId);
    pinchDistance = 0;
    if (!pointers.size) stage.classList.remove("dragging");
  }
  svg.addEventListener("pointerup", release);
  svg.addEventListener("pointercancel", release);

  root.querySelectorAll("[data-lay-side]").forEach(function (btn) {
    btn.addEventListener("click", function () { setSide(btn.dataset.laySide); });
  });
  root.querySelectorAll("[data-lay-zoom]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const action = btn.dataset.layZoom;
      if (action === "fit") {
        view = Object.assign({}, home);
        applyView();
      } else {
        zoomCenter(action === "in" ? 1.5 : 1 / 1.5);
      }
    });
  });

  setSide("top");
})();
