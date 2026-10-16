(function () {
  const nodes = document.querySelectorAll(".djvu-frame[data-djvu-url]");
  if (!nodes.length || !window.DjVu || !DjVu.Viewer) return;

  nodes.forEach(function (el) {
    const viewer = new DjVu.Viewer();
    viewer.render(el);
    viewer.loadDocumentByUrl(el.dataset.djvuUrl, {
      name: el.dataset.djvuName || "document.djvu",
      language: "ru",
      viewMode: "continuous",
      uiOptions: {
        hideOpenAndCloseButtons: true,
      },
    });
  });
})();
