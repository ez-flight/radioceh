(function () {
  const republicToCountry = {
    РСФСР: "Россия",
    "Украинская ССР": "Украина",
    "Белорусская ССР": "Беларусь",
    "Узбекская ССР": "Узбекистан",
    "Казахская ССР": "Казахстан",
    "Грузинская ССР": "Грузия",
    "Азербайджанская ССР": "Азербайджан",
    "Литовская ССР": "Литва",
    "Молдавская ССР": "Молдова",
    "Латвийская ССР": "Латвия",
    "Киргизская ССР": "Кыргызстан",
    "Таджикская ССР": "Таджикистан",
    "Армянская ССР": "Армения",
    "Туркменская ССР": "Туркменистан",
    "Эстонская ССР": "Эстония",
  };

  function bind() {
    const republic = document.getElementById("id_republic");
    const country = document.getElementById("id_country_now");
    if (!republic || !country) return;
    republic.addEventListener("change", function () {
      const mapped = republicToCountry[republic.value];
      if (mapped) country.value = mapped;
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bind);
  } else {
    bind();
  }
})();
