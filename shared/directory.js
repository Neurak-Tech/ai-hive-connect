(function () {
  "use strict";

  var list = document.getElementById("route-list");
  var status = document.getElementById("route-status");
  var origin = document.getElementById("origin");
  if (!list || !status) return;

  if (origin && window.location.protocol.indexOf("http") === 0) {
    origin.textContent = window.location.host;
  }

  function show(message) {
    status.hidden = false;
    status.textContent = message;
  }

  function line(className, text) {
    var node = document.createElement("p");
    node.className = className;
    node.textContent = text;
    return node;
  }

  function renderRoute(funnel, entry) {
    var item = document.createElement("li");
    item.className = "route";

    var link = document.createElement("a");
    link.href = "/" + funnel.slug + "/";
    link.textContent = funnel.title || funnel.slug;

    var path = "/" + funnel.slug + "/";
    var state = entry ? entry.status : "not scanned";
    if (entry && entry.events && entry.events.length) {
      state += " · " + entry.events.join(", ");
    }

    item.appendChild(link);
    item.appendChild(line("path", path));
    item.appendChild(line("state", state));
    return item;
  }

  function load(url) {
    return fetch(url, { credentials: "same-origin" }).then(function (response) {
      if (!response.ok) throw new Error(url);
      return response.json();
    });
  }

  Promise.all([
    load("/funnels.json"),
    load("/registry/conversion-status.json").catch(function () {
      return { funnels: [] };
    })
  ]).then(function (results) {
    var funnels = results[0];
    var registry = results[1].funnels || [];
    var bySlug = {};
    registry.forEach(function (entry) {
      bySlug[entry.funnel] = entry;
    });
    if (!funnels.length) {
      show("No funnels are published yet. Add a folder under funnels and push to main.");
      return;
    }
    funnels.forEach(function (funnel) {
      list.appendChild(renderRoute(funnel, bySlug[funnel.slug]));
    });
    list.hidden = false;
    status.hidden = true;
  }).catch(function () {
    show("The route list is built when the site is assembled. Run python3 scripts/assemble-site.py and open the _site folder.");
  });
})();
