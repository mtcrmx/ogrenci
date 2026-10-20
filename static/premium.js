(function () {
  var R = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var body = document.body;

  function sayiCoz(metin) {
    var m = /(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d+))?/.exec(metin);
    if (!m) return null;
    return { bas: metin.slice(0, m.index), son: metin.slice(m.index + m[0].length), hedef: parseFloat(m[1].replace(/\./g, "") + (m[2] ? "." + m[2] : "")), ondalik: m[2] ? m[2].length : 0 };
  }
  function say(el) {
    var p = sayiCoz(el.textContent);
    if (!p) return;
    var hedef = p.hedef;
    var yaz = function (v) { el.textContent = p.bas + v.toLocaleString("tr-TR", { minimumFractionDigits: p.ondalik, maximumFractionDigits: p.ondalik }) + p.son; };
    if (R) return;
    var s = performance.now();
    (function f(n) {
      var t = Math.max(0, Math.min((n - s) / 1100, 1)), e = 1 - Math.pow(1 - t, 3);
      yaz(hedef * e);
      if (t < 1) requestAnimationFrame(f); else yaz(hedef);
    })(s);
  }

  function kaydir(nav, aktif, pill, dikey) {
    if (!nav || !pill) return;
    if (!aktif) { pill.style.opacity = "0"; return; }
    pill.style.opacity = "1";
    var ilk = !pill.dataset.yerlesti;
    if (ilk) pill.style.transition = "none";
    if (dikey) {
      pill.style.height = aktif.offsetHeight + "px";
      pill.style.transform = "translateY(" + aktif.offsetTop + "px)";
    } else {
      pill.style.width = aktif.offsetWidth + "px";
      pill.style.transform = "translateX(" + aktif.offsetLeft + "px)";
    }
    if (ilk && aktif.offsetWidth) {
      pill.dataset.yerlesti = "1";
      pill.offsetHeight;
      pill.style.transition = "";
    }
  }

  function izle(el, fn) {
    if (window.ResizeObserver) new ResizeObserver(function () { fn(); }).observe(el);
    else window.addEventListener("resize", fn);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(fn);
    window.addEventListener("load", fn);
  }

  function menuPill() {
    var nav = document.querySelector(".app-sidebar .app-nav");
    if (!nav) return;
    var pill = document.createElement("span");
    pill.className = "pm-nav-pill";
    pill.setAttribute("aria-hidden", "true");
    nav.prepend(pill);
    nav.classList.add("pm-has-pill");
    var aktif = function () { return nav.querySelector("a.is-current"); };
    kaydir(nav, aktif(), pill, true);
    nav.addEventListener("click", function (e) {
      var a = e.target.closest("a");
      if (!a || a.target === "_blank") return;
      nav.querySelectorAll("a.is-current").forEach(function (x) { x.classList.remove("is-current"); });
      a.classList.add("is-current");
      kaydir(nav, a, pill, true);
    });
    new MutationObserver(function () { kaydir(nav, aktif(), pill, true); }).observe(nav, { attributes: true, subtree: true, attributeFilter: ["class"] });
    izle(nav, function () { kaydir(nav, aktif(), pill, true); });
  }

  function sekmePill(nav, secici) {
    var pill = document.createElement("span");
    pill.className = "pm-tab-pill";
    pill.setAttribute("aria-hidden", "true");
    nav.prepend(pill);
    nav.classList.add("pm-has-pill");
    var git = function () { kaydir(nav, nav.querySelector(secici), pill, false); };
    git();
    izle(nav, git);
    if (nav.classList.contains("tabs")) {
      nav.addEventListener("click", function (e) {
        var a = e.target.closest("a");
        if (!a) return;
        nav.querySelectorAll("a.on").forEach(function (x) { x.classList.remove("on"); });
        a.classList.add("on");
        git();
      });
    }
  }

  function dock() {
    var d = document.querySelector(".pm-dock");
    if (!d) return;
    var pill = d.querySelector(".pm-dock-pill");
    var konum = function () { kaydir(d, d.querySelector(".is-on"), pill, false); };
    var ayarla = function () {
      var h = location.hash.slice(1);
      var linkler = [].slice.call(d.querySelectorAll("a[data-parent-nav]"));
      if (linkler.length && h) {
        var eslesen = linkler.filter(function (a) { return a.getAttribute("data-parent-nav") === h; })[0];
        if (eslesen) {
          d.querySelectorAll(".is-on").forEach(function (x) { x.classList.remove("is-on"); x.removeAttribute("aria-current"); });
          eslesen.classList.add("is-on");
          eslesen.setAttribute("aria-current", "page");
        }
      }
      konum();
    };
    ayarla();
    window.addEventListener("hashchange", ayarla);
    izle(d, konum);
    d.addEventListener("click", function (e) {
      var m = e.target.closest("[data-pm-menu]");
      if (m) {
        var t = document.querySelector("[data-app-menu-toggle]");
        if (t) t.click();
        return;
      }
      var a = e.target.closest("a");
      if (!a) return;
      d.querySelectorAll(".is-on").forEach(function (x) { x.classList.remove("is-on"); });
      a.classList.add("is-on");
      konum();
    });
  }

  var tm;
  window.pmToast = function (metin, kotu) {
    var t = document.querySelector(".pm-toast");
    if (!t) {
      t = document.createElement("div");
      t.className = "pm-toast";
      t.setAttribute("role", "status");
      t.setAttribute("aria-live", "polite");
      t.innerHTML = '<span class="pm-toast-ic" aria-hidden="true"><svg class="pm-ic" style="width:14px;height:14px"><use href="#pm-i-check"/></svg></span><span class="pm-toast-t"></span>';
      body.appendChild(t);
    }
    t.classList.toggle("is-bad", !!kotu);
    t.querySelector(".pm-toast-t").textContent = metin;
    requestAnimationFrame(function () { t.classList.add("is-on"); });
    clearTimeout(tm);
    tm = setTimeout(function () { t.classList.remove("is-on"); }, 2600);
  };

  function kademe() {
    var kok = document.querySelector(".app-workspace main, main.vp-main, main.login-stage") || document.querySelector("main");
    if (!kok) return;
    var adaylar = kok.querySelectorAll(".pm-st, .dash-head, .pm-act, .dash-kpi, .dash-hero, .dash-card, .pm-hero, .card, details.sec, .insight, .app-card, .vp-card, .lm-card, .lm-band, :scope > section, :scope > header");
    var i = 0;
    adaylar.forEach(function (el) {
      if (el.closest(".pm-st") && el.closest(".pm-st") !== el) return;
      if (el.parentElement && el.parentElement.closest(".card, .app-card, .dash-card, details.sec, .vp-card, .lm-card")) return;
      if (i > 14) return;
      el.classList.add("pm-st");
      el.style.setProperty("--pm-i", i++);
    });
  }

  function halkalar() {
    document.querySelectorAll("[data-pm-ring]").forEach(function (c) {
      var r = +c.getAttribute("r"), cevre = 2 * Math.PI * r, v = Math.max(0, Math.min(100, +c.dataset.pmRing || 0));
      c.style.strokeDasharray = cevre;
      c.style.strokeDashoffset = R ? cevre * (1 - v / 100) : cevre;
      if (!R) requestAnimationFrame(function () { requestAnimationFrame(function () { c.style.strokeDashoffset = cevre * (1 - v / 100); }); });
    });
  }

  function iskelet() {
    var sk = document.querySelector(".pm-sk");
    if (!sk) return;
    if (R) { sk.remove(); return; }
    setTimeout(function () { sk.classList.add("is-off"); setTimeout(function () { sk.remove(); }, 380); }, 260);
  }

  function basla() {
    if (!R) body.classList.add("pm-anim");
    kademe();
    menuPill();
    document.querySelectorAll("nav.yt-tabs").forEach(function (n) { sekmePill(n, "a.is-current"); });
    document.querySelectorAll(".app-workspace nav.tabs").forEach(function (n) { sekmePill(n, "a.on"); });
    dock();
    halkalar();
    document.querySelectorAll("[data-pm-count]").forEach(say);
    iskelet();
  }
  document.addEventListener("click", function (e) {
    if (!e.target.closest("[data-pm-renk]")) return;
    if (window.appMenuClose) window.appMenuClose();
    if (window.ecoRenkAc) window.ecoRenkAc();
  });

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", basla); else basla();
})();
