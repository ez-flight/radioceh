document.querySelectorAll("[data-carousel]").forEach((root) => {
  const track = root.querySelector(".carousel-track");
  const slides = [...root.querySelectorAll(".carousel-slide")];
  const dots = [...root.querySelectorAll("[data-carousel-dot]")];
  if (!track || slides.length < 2) return;

  let index = 0;
  const show = (next) => {
    index = (next + slides.length) % slides.length;
    track.style.transform = `translateX(-${index * 100}%)`;
    dots.forEach((dot, i) => dot.classList.toggle("active", i === index));
  };

  root.querySelector("[data-carousel-prev]")?.addEventListener("click", (event) => {
    event.preventDefault();
    show(index - 1);
  });
  root.querySelector("[data-carousel-next]")?.addEventListener("click", (event) => {
    event.preventDefault();
    show(index + 1);
  });
  dots.forEach((dot) => {
    dot.addEventListener("click", (event) => {
      event.preventDefault();
      show(Number(dot.dataset.carouselDot));
    });
  });
});
