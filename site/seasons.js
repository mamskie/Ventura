// Trend Desk — seasonal themes + share helpers.
//
// The theme is picked from the current date (no build step, no cookies):
//   Christmas: Dec 1 – Dec 25   (green + deep red, greeting ribbon)
//   New Year:  Dec 26 – Jan 7   (navy + gold, greeting ribbon)
//   anything else: the normal Newsroom Bold look, no ribbon.
//
// Preview any season with a query override, e.g. ?season=christmas,
// ?season=newyear, or ?season=none to force the default look.
// New seasons are added by appending one entry to SEASONS below —
// the CSS for a new season lives in editorial.css.
(function () {
  var SEASONS = [
    {
      id: "christmas",
      start: [12, 1],
      end: [12, 25],
      greeting: "Season's Greetings from Trend Desk — Merry Christmas",
    },
    {
      id: "newyear",
      start: [12, 26],
      end: [1, 7],
      greeting: "Happy New Year from Trend Desk",
    },
  ];

  function inRange(month, day, start, end) {
    var from = start[0] * 100 + start[1];
    var to = end[0] * 100 + end[1];
    var now = month * 100 + day;
    // A season that wraps the year boundary (Dec -> Jan) matches either side.
    return from <= to ? now >= from && now <= to : now >= from || now <= to;
  }

  function detectSeason() {
    var override = null;
    try {
      override = new URLSearchParams(window.location.search).get("season");
    } catch (e) {
      override = null;
    }
    if (override) {
      if (override === "none") return null;
      for (var i = 0; i < SEASONS.length; i++) {
        if (SEASONS[i].id === override) return SEASONS[i];
      }
      return null;
    }
    var today = new Date();
    for (var j = 0; j < SEASONS.length; j++) {
      if (
        inRange(
          today.getMonth() + 1,
          today.getDate(),
          SEASONS[j].start,
          SEASONS[j].end
        )
      ) {
        return SEASONS[j];
      }
    }
    return null;
  }

  // Copy-link button used by the share rows (works in every season).
  window.copyPageLink = function (btn) {
    var url = btn.getAttribute("data-url") || window.location.href;
    function done() {
      btn.textContent = "✓ Link copied";
      setTimeout(function () {
        btn.textContent = "Copy link";
      }, 2000);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(done, function () {
        fallbackCopy(url, done);
      });
    } else {
      fallbackCopy(url, done);
    }
  };

  function fallbackCopy(text, done) {
    var input = document.createElement("input");
    input.value = text;
    input.style.position = "fixed";
    input.style.opacity = "0";
    document.body.appendChild(input);
    input.select();
    try {
      document.execCommand("copy");
    } catch (e) {
      /* clipboard unavailable; the button still reports the attempt */
    }
    document.body.removeChild(input);
    done();
  }

  var season = detectSeason();
  if (!season) return;
  document.body.classList.add("season-" + season.id);
  var ribbon = document.createElement("div");
  ribbon.className = "season-ribbon";
  var bold = document.createElement("b");
  bold.textContent = season.greeting;
  ribbon.appendChild(document.createTextNode("✳ "));
  ribbon.appendChild(bold);
  ribbon.appendChild(document.createTextNode(" ✳"));
  document.body.insertBefore(ribbon, document.body.firstChild);
})();
