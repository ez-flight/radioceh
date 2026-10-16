(function () {
  function boxes() {
    return Array.prototype.slice.call(
      document.querySelectorAll('#result_list input[type="checkbox"][name$="-is_hidden"]')
    );
  }

  function sync(master) {
    const all = boxes();
    const checked = all.filter(function (box) {
      return box.checked;
    }).length;
    master.indeterminate = checked > 0 && checked < all.length;
    master.checked = all.length > 0 && checked === all.length;
  }

  function bind() {
    const header = document.querySelector("#result_list th.column-is_hidden .text");
    if (!header || document.getElementById("toggle-is-hidden")) return;

    const label = document.createElement("label");
    label.className = "toggle-is-hidden";
    label.setAttribute("for", "toggle-is-hidden");

    const master = document.createElement("input");
    master.type = "checkbox";
    master.id = "toggle-is-hidden";
    master.title = "Выбрать/Сбросить все";

    const text = document.createElement("span");
    text.textContent = "Выбрать/Сбросить все";

    label.appendChild(master);
    label.appendChild(text);
    header.appendChild(label);

    master.addEventListener("change", function () {
      const value = master.checked;
      boxes().forEach(function (box) {
        box.checked = value;
      });
      sync(master);
    });
    boxes().forEach(function (box) {
      box.addEventListener("change", function () {
        sync(master);
      });
    });
    sync(master);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bind);
  } else {
    bind();
  }
})();
