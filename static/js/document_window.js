(function () {
  document.querySelectorAll(".js-doc-window").forEach(function (link) {
    link.addEventListener("click", function (event) {
      event.preventDefault();
      const viewer = window.open(
        link.href,
        "radiotsekhDocument_" + link.pathname.replace(/\W+/g, "_"),
        "popup=yes,width=1100,height=820,scrollbars=yes,resizable=yes"
      );
      if (viewer) viewer.focus();
      else window.open(link.href, "_blank", "noopener");
    });
  });
})();
