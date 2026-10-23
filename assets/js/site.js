// Respect reduced-motion preferences: pause autoplaying videos (WCAG 2.2.2 / 2.3.3).
(function () {
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    document.querySelectorAll('video[autoplay]').forEach(function (v) { v.removeAttribute('autoplay'); v.pause(); });
  }
})();

// Collapsible sections: "Expand all" / "Collapse all" buttons, and open any folded section
// that contains the target of a #link (e.g. publications.html#J49).
(function () {
  document.querySelectorAll('[data-fold]').forEach(function (b) {
    b.addEventListener('click', function () {
      var open = b.getAttribute('data-fold') === 'open';
      document.querySelectorAll('details.fold').forEach(function (d) { d.open = open; });
    });
  });
  function revealHash() {
    if (!location.hash) return;
    var el = document.getElementById(decodeURIComponent(location.hash.slice(1)));
    if (!el) return;
    for (var p = el.parentElement; p; p = p.parentElement) { if (p.tagName === 'DETAILS') p.open = true; }
    el.scrollIntoView();
  }
  window.addEventListener('hashchange', revealHash);
  revealHash();
})();
