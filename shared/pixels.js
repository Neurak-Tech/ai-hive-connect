(function () {
  "use strict";

  var runtime = window.AIHIVE || {};
  var config = runtime.config || {};
  var ids = config.analytics || {};
  var linkedinConversions = config.linkedinConversions || {};
  var funnel = runtime.funnel || {};
  var metaEvents = funnel.metaEvents || {};

  var META_EVENTS = {
    form_submit: "Lead",
    cta_click: "Contact",
    whatsapp_click: "Contact",
    calendly_click: "Schedule",
    phone_click: "Contact",
    email_click: "Contact"
  };

  function trimmed(value) {
    return String(value || "").trim();
  }

  function appendScript(src) {
    var script = document.createElement("script");
    script.async = true;
    script.src = src;
    document.head.appendChild(script);
  }

  function metaPayload(spec) {
    var payload = {};
    if (!spec) return payload;
    if (spec.content_name) payload.content_name = spec.content_name;
    if (spec.value != null && spec.value !== "") payload.value = Number(spec.value);
    if (spec.currency) payload.currency = spec.currency;
    return payload;
  }

  function fireMeta(spec) {
    if (!spec || !spec.event || typeof window.fbq !== "function") return;
    window.fbq("track", spec.event, metaPayload(spec));
  }

  function isCheckoutLink(params) {
    var href = params && params.link_url ? String(params.link_url) : "";
    return /whatsapp\.theaihive\.io\/checkout/i.test(href);
  }

  function installMeta(pixelId) {
    if (window.fbq) return;
    var fbq = function () {
      if (fbq.callMethod) fbq.callMethod.apply(fbq, arguments);
      else fbq.queue.push(arguments);
    };
    window.fbq = fbq;
    if (!window._fbq) window._fbq = fbq;
    fbq.push = fbq;
    fbq.loaded = true;
    fbq.version = "2.0";
    fbq.queue = [];
    appendScript("https://connect.facebook.net/en_US/fbevents.js");
    window.fbq("init", pixelId);
    window.fbq("track", "PageView");

    var image = document.createElement("img");
    image.height = "1";
    image.width = "1";
    image.alt = "";
    image.style.display = "none";
    image.src = "https://www.facebook.com/tr?id=" + encodeURIComponent(pixelId) + "&ev=PageView&noscript=1";
    var noscript = document.createElement("noscript");
    noscript.appendChild(image);
    document.body.insertBefore(noscript, document.body.firstChild);
  }

  function installLinkedIn(partnerId) {
    window._linkedin_partner_id = partnerId;
    window._linkedin_data_partner_ids = window._linkedin_data_partner_ids || [];
    window._linkedin_data_partner_ids.push(partnerId);
    if (!window.lintrk) {
      window.lintrk = function (action, data) {
        window.lintrk.q.push([action, data]);
      };
      window.lintrk.q = [];
    }
    appendScript("https://snap.licdn.com/li.lms-analytics/insight.min.js");
  }

  var previousTrack = runtime.track;
  runtime.track = function (eventName, params) {
    if (typeof previousTrack === "function") previousTrack(eventName, params);
    if (typeof window.fbq === "function") {
      if (eventName === "cta_click" && metaEvents.checkout && isCheckoutLink(params)) {
        fireMeta(metaEvents.checkout);
      } else {
        var metaEvent = META_EVENTS[eventName];
        if (metaEvent) window.fbq("track", metaEvent, params || {});
        else window.fbq("trackCustom", eventName, params || {});
      }
    }
    var conversionId = trimmed(linkedinConversions[eventName]);
    if (typeof window.lintrk === "function" && /^\d+$/.test(conversionId)) {
      window.lintrk("track", { conversion_id: Number(conversionId) });
    }
  };

  var metaPixel = trimmed(ids.metaPixel);
  var linkedinPartnerId = trimmed(ids.linkedinPartnerId);
  if (metaPixel && !/^\d{5,20}$/.test(metaPixel)) {
    console.warn("[AIHive] Ignoring invalid metaPixel id");
    metaPixel = "";
  }
  if (linkedinPartnerId && !/^\d{5,12}$/.test(linkedinPartnerId)) {
    console.warn("[AIHive] Ignoring invalid linkedinPartnerId");
    linkedinPartnerId = "";
  }
  if (metaPixel) installMeta(metaPixel);
  if (linkedinPartnerId) installLinkedIn(linkedinPartnerId);
  if (metaPixel) fireMeta(metaEvents.load);
})();
