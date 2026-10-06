(function () {
  "use strict";

  var runtime = window.AIHIVE || {};
  var config = runtime.config || {};
  var ids = config.analytics || {};
  var tracking = config.tracking || {};

  var PATTERNS = {
    ga4: /^G-[A-Z0-9]+$/,
    gtm: /^GTM-[A-Z0-9]+$/,
    clarity: /^[a-z0-9]+$/i
  };

  function activeId(name) {
    var value = String(ids[name] || "").trim();
    if (!value) return "";
    var pattern = PATTERNS[name];
    if (pattern && !pattern.test(value)) {
      console.warn("[AIHive] Ignoring invalid " + name + " id");
      return "";
    }
    return value;
  }

  function appendScript(src) {
    var script = document.createElement("script");
    script.async = true;
    script.src = src;
    document.head.appendChild(script);
  }

  function installGa4(measurementId) {
    window.dataLayer = window.dataLayer || [];
    window.gtag = window.gtag || function () {
      window.dataLayer.push(arguments);
    };
    window.gtag("js", new Date());
    window.gtag("config", measurementId);
    appendScript("https://www.googletagmanager.com/gtag/js?id=" + encodeURIComponent(measurementId));
  }

  function installGtm(containerId) {
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({ "gtm.start": Date.now(), event: "gtm.js" });
    appendScript("https://www.googletagmanager.com/gtm.js?id=" + encodeURIComponent(containerId));
    var frame = document.createElement("iframe");
    frame.src = "https://www.googletagmanager.com/ns.html?id=" + encodeURIComponent(containerId);
    frame.height = "0";
    frame.width = "0";
    frame.style.display = "none";
    frame.style.visibility = "hidden";
    frame.title = "Google Tag Manager";
    var noscript = document.createElement("noscript");
    noscript.appendChild(frame);
    document.body.insertBefore(noscript, document.body.firstChild);
  }

  function installClarity(projectId) {
    window.clarity = window.clarity || function () {
      (window.clarity.q = window.clarity.q || []).push(arguments);
    };
    appendScript("https://www.clarity.ms/tag/" + encodeURIComponent(projectId));
  }

  function funnelSlug() {
    return typeof runtime.funnelSlug === "function" ? runtime.funnelSlug() : "home";
  }

  function payloadFor(params) {
    var payload = {
      funnel: funnelSlug(),
      page_path: window.location.pathname
    };
    var key;
    var source = params || {};
    for (key in source) {
      if (Object.prototype.hasOwnProperty.call(source, key)) payload[key] = source[key];
    }
    return payload;
  }

  runtime.track = function (eventName, params) {
    var payload = payloadFor(params);
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push(Object.assign({ event: eventName }, payload));
    if (typeof window.gtag === "function") window.gtag("event", eventName, payload);
    if (typeof window.clarity === "function") window.clarity("event", eventName);
    runtime.events = runtime.events || [];
    runtime.events.push({
      event: eventName,
      params: payload,
      at: new Date().toISOString()
    });
    if (runtime.events.length > 50) runtime.events.shift();
    if (tracking.debug) console.info("[AIHive]", eventName, payload);
  };

  var ga4 = activeId("ga4");
  var gtm = activeId("gtm");
  var clarity = activeId("clarity");
  if (ga4) installGa4(ga4);
  if (gtm) installGtm(gtm);
  if (clarity) installClarity(clarity);
})();
