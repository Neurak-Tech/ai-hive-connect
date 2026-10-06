(function () {
  "use strict";

  var CHANNELS = [
    {
      eventName: "whatsapp_click",
      test: function (href) {
        return /wa\.me\/|api\.whatsapp\.com|whatsapp\.com\/send|whatsapp:/i.test(href);
      }
    },
    {
      eventName: "calendly_click",
      test: function (href) {
        return /calendly\.com/i.test(href);
      }
    },
    {
      eventName: "phone_click",
      test: function (href) {
        return /^tel:/i.test(href);
      }
    },
    {
      eventName: "email_click",
      test: function (href) {
        return /^mailto:/i.test(href);
      }
    }
  ];

  var lastFire = { key: "", at: 0 };

  function track(eventName, params) {
    var runtime = window.AIHIVE;
    if (!runtime || typeof runtime.track !== "function") {
      console.error("[AIHive] Conversion tracking is not available");
      return;
    }
    runtime.track(eventName, params);
  }

  function shouldFire(key) {
    var now = Date.now();
    if (lastFire.key === key && now - lastFire.at < 700) return false;
    lastFire.key = key;
    lastFire.at = now;
    return true;
  }

  function ignored(element) {
    return Boolean(element && element.closest("[data-track-ignore]"));
  }

  function honeypotFilled(form) {
    var field = form.querySelector("[data-honeypot]");
    return Boolean(field && String(field.value || "").trim());
  }

  function isSubmitControl(element) {
    var tag = element.tagName;
    if (tag === "INPUT") {
      var inputType = (element.getAttribute("type") || "").toLowerCase();
      return inputType === "submit" || inputType === "image";
    }
    if (tag === "BUTTON") {
      return (element.getAttribute("type") || "submit").toLowerCase() === "submit";
    }
    return false;
  }

  function isCta(element) {
    if (element.hasAttribute("data-cta")) return true;
    var className = element.getAttribute("class") || "";
    return /(^|[^A-Za-z0-9_])cta([^A-Za-z0-9_]|$)/.test(className);
  }

  function hrefOf(element) {
    return (element.getAttribute("href") || "").trim();
  }

  function channelFor(href) {
    var index;
    for (index = 0; index < CHANNELS.length; index += 1) {
      if (CHANNELS[index].test(href)) return CHANNELS[index].eventName;
    }
    return "";
  }

  function labelOf(element) {
    return (element.getAttribute("aria-label") || element.textContent || "")
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 80);
  }

  function fieldNames(form) {
    return Array.prototype.filter.call(form.elements, function (element) {
      return element.name && !element.hasAttribute("data-honeypot");
    }).map(function (element) {
      return element.name;
    });
  }

  function onActivate(event) {
    if (event.type === "click" && event.button !== 0) return;
    var element = event.target && event.target.closest
      ? event.target.closest("a, button, input")
      : null;
    if (!element || ignored(element) || isSubmitControl(element)) return;

    var href = hrefOf(element);
    var eventName = channelFor(href);
    if (!eventName && isCta(element)) eventName = "cta_click";
    if (!eventName) return;

    var key = eventName + ":" + (href || labelOf(element));
    if (!shouldFire(key)) return;
    track(eventName, {
      link_url: href,
      link_text: labelOf(element)
    });
  }

  function onSubmit(event) {
    var form = event.target;
    if (!form || form.tagName !== "FORM" || ignored(form)) return;
    if (honeypotFilled(form)) return;
    if (typeof form.checkValidity === "function" && !form.checkValidity()) return;

    var formId = form.id || form.getAttribute("name") || "form";
    if (!shouldFire("form:" + formId)) return;
    track("form_submit", {
      form_id: form.id || "",
      form_name: form.getAttribute("name") || "",
      field_names: fieldNames(form).join(",")
    });
  }

  document.addEventListener("click", onActivate, true);
  document.addEventListener("auxclick", onActivate, true);
  document.addEventListener("submit", onSubmit, true);
})();
