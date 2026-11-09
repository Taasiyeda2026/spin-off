/* SPIN-OFF challenge-area language preference: synchronous head bootstrap.
   Separate pretranslated HTML pages ensure Arabic never flashes Hebrew text. */
(function () {
  "use strict";
  var KEY = "spin-off-challenges-language";
  var root = document.documentElement;
  var pageLanguage = root.getAttribute("lang") === "ar" ? "ar" : "he";
  var requested;
  try {
    var explicit = new URLSearchParams(window.location.search).get("lang");
    if (explicit === "he" || explicit === "ar") {
      requested = explicit;
      window.localStorage.setItem(KEY, explicit);
    } else {
      var saved = window.localStorage.getItem(KEY);
      requested = saved === "ar" || saved === "he" ? saved : pageLanguage;
    }
  } catch (_error) {
    requested = pageLanguage;
  }
  if (requested !== pageLanguage) {
    var filename = window.location.pathname.split("/").pop() || "challenges.html";
    var destination = new URL(pageLanguage === "he" ? "ar/" + filename : "../" + filename, window.location.href);
    destination.search = "?lang=" + encodeURIComponent(requested);
    destination.hash = window.location.hash;
    window.location.replace(destination.href);
  }
})();
