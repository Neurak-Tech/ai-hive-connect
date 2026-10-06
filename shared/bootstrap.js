(function () {
  "use strict";

  function scriptSrc() {
    if (document.currentScript && document.currentScript.src) return document.currentScript.src;
    var nodes = document.scripts;
    var index;
    for (index = nodes.length - 1; index >= 0; index -= 1) {
      if (nodes[index].src && nodes[index].src.indexOf("bootstrap.js") !== -1) {
        return nodes[index].src;
      }
    }
    return "";
  }

  var SHARED_ROOT = (function () {
    var src = scriptSrc();
    if (!src) return "/shared/";
    return new URL("./", src).pathname;
  })();

  var SITE_BASE = SHARED_ROOT.replace(/\/shared\/?$/, "");

  var RUNTIME_SCRIPTS = [
    "meta.js",
    "analytics.js",
    "pixels.js",
    "conversion-tracker.js"
  ];

  var runtime = window.AIHIVE || {};
  window.AIHIVE = runtime;
  runtime.version = "1.0.0";
  runtime.events = runtime.events || [];
  runtime.sharedRoot = SHARED_ROOT;
  runtime.siteBase = SITE_BASE;

  runtime.publishedPath = function () {
    var path = window.location.pathname || "/";
    if (SITE_BASE && path.indexOf(SITE_BASE + "/") === 0) path = path.slice(SITE_BASE.length);
    else if (SITE_BASE && path === SITE_BASE) path = "/";
    if (path.indexOf("/funnels/") === 0) path = path.slice("/funnels".length);
    path = path.replace(/index\.html$/, "");
    if (!path || path === "/") return "/";
    if (path.charAt(0) !== "/") path = "/" + path;
    if (path.charAt(path.length - 1) !== "/") path += "/";
    return path;
  };

  runtime.funnelSlug = function () {
    var parts = runtime.publishedPath().split("/").filter(Boolean);
    return parts.length ? parts[0] : "home";
  };

  function readJson(url, required) {
    return fetch(url, { credentials: "same-origin" }).then(function (response) {
      if (!response.ok) {
        if (required) throw new Error(url + " HTTP " + response.status);
        return {};
      }
      return response.json();
    });
  }

  function loadScript(src) {
    return new Promise(function (resolve) {
      var script = document.createElement("script");
      script.src = src;
      script.onload = function () { resolve(); };
      script.onerror = function () {
        console.error("[AIHive] Failed to load " + src);
        resolve();
      };
      document.head.appendChild(script);
    });
  }

  function loadSequential(urls) {
    return urls.reduce(function (chain, url) {
      return chain.then(function () { return loadScript(url); });
    }, Promise.resolve());
  }

  var funnelUrl = new URL("funnel.json", window.location.href).href;

  runtime.ready = readJson(SHARED_ROOT + "config.json", true)
    .then(function (config) {
      runtime.config = config;
      return readJson(funnelUrl, false);
    })
    .then(function (funnel) {
      runtime.funnel = funnel && typeof funnel === "object" ? funnel : {};
      var urls = RUNTIME_SCRIPTS.map(function (name) {
        return SHARED_ROOT + name;
      });
      return loadSequential(urls);
    })
    .catch(function (error) {
      console.error("[AIHive] Bootstrap failed", error);
    });
})();
