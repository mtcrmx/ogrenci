(function () {
  var KEY = "eco-renk";
  var IZIN = ["leylak", "pembe", "seftali", "nane", "gok", "limon"];
  var META = {
    leylak: "#c9b4f0",
    pembe: "#f7b7d4",
    seftali: "#ffd6a8",
    nane: "#bde9d8",
    gok: "#b8d8ff",
    limon: "#ffe08a"
  };

  function oku() {
    try {
      var v = localStorage.getItem(KEY);
      if (IZIN.indexOf(v) >= 0) return v;
    } catch (e) {}
    return "leylak";
  }

  function uygula(ad) {
    if (IZIN.indexOf(ad) < 0) ad = "leylak";
    document.documentElement.setAttribute("data-renk", ad);
    try { localStorage.setItem(KEY, ad); } catch (e) {}
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta && META[ad]) meta.setAttribute("content", META[ad]);
    document.querySelectorAll("[data-renk-secenek]").forEach(function (btn) {
      btn.classList.toggle("is-active", btn.getAttribute("data-renk-secenek") === ad);
    });
  }

  uygula(oku());
  window.ecoRenk = { uygula: uygula, oku: oku, liste: IZIN };

  window.ecoRenkAc = function () {
    var p = document.getElementById("renk-ayari");
    if (!p) return;
    p.hidden = false;
    uygula(oku());
  };

  window.ecoRenkKapat = function () {
    var p = document.getElementById("renk-ayari");
    if (p) p.hidden = true;
  };

  document.addEventListener("click", function (ev) {
    var sec = ev.target.closest("[data-renk-secenek]");
    if (sec) {
      uygula(sec.getAttribute("data-renk-secenek"));
      return;
    }
    if (ev.target.closest("[data-renk-ac]")) {
      if (typeof closeTeacherMenu === "function") closeTeacherMenu();
      window.ecoRenkAc();
      return;
    }
    if (ev.target.id === "renk-ayari" || ev.target.closest("[data-renk-kapat]")) {
      window.ecoRenkKapat();
    }
  });

  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape") window.ecoRenkKapat();
  });
})();
