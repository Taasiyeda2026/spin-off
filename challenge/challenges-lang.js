/* SPIN-OFF challenge-area language preference: synchronous head bootstrap.
   Separate pretranslated HTML pages ensure Arabic never flashes Hebrew text. */
(function () {
  "use strict";
  var KEY = "spin-off-challenges-language";
  var root = document.documentElement;
  var pageLanguage = root.getAttribute("lang") === "ar" ? "ar" : "he";
  var explicit = new URLSearchParams(window.location.search).get("lang");
  var requested = pageLanguage;
  if (explicit === "he" || explicit === "ar") {
    requested = explicit;
    try { window.localStorage.setItem(KEY, explicit); } catch (_error) { /* Explicit links work without storage. */ }
  } else {
    try {
      var saved = window.localStorage.getItem(KEY);
      if (saved === "ar" || saved === "he") requested = saved;
    } catch (_error) { /* Direct pages remain usable without storage. */ }
  }
  if (requested !== pageLanguage) {
    var filename = window.location.pathname.split("/").pop() || "challenges.html";
    var destination = new URL(pageLanguage === "he" ? "ar/" + filename : "../" + filename, window.location.href);
    destination.search = "?lang=" + encodeURIComponent(requested);
    destination.hash = window.location.hash;
    window.location.replace(destination.href);
  }
})();
