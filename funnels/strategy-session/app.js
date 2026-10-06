(function () {
  "use strict";

  var form = document.getElementById("session-form");
  if (!form) return;

  var status = document.getElementById("form-status");
  var submitButton = form.querySelector("button[type='submit']");

  var rules = {
    name: function (value) {
      return value.trim().length >= 2 ? "" : "Enter the name we should use in the session.";
    },
    email: function (value) {
      return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim())
        ? ""
        : "Enter a work email with a domain, such as name@company.com.";
    },
    phone: function (value) {
      var digits = value.replace(/\D/g, "");
      return digits.length >= 8 ? "" : "Enter a phone number with at least 8 digits.";
    },
    decision: function (value) {
      return value.trim().length >= 12
        ? ""
        : "Write the action this page should get, in one sentence.";
    }
  };

  function errorNode(input) {
    return document.getElementById(input.id + "-error");
  }

  function setFieldError(input, message) {
    var node = errorNode(input);
    input.setAttribute("aria-invalid", message ? "true" : "false");
    if (node) node.textContent = message;
  }

  function validate() {
    var valid = true;
    Object.keys(rules).forEach(function (name) {
      var input = form.elements[name];
      var message = rules[name](input.value);
      setFieldError(input, message);
      if (message) valid = false;
    });
    return valid;
  }

  function showStatus(message) {
    if (!status) return;
    status.hidden = false;
    status.textContent = message;
  }

  function runtimeReady() {
    if (window.AIHIVE && window.AIHIVE.ready) return window.AIHIVE.ready;
    return Promise.resolve();
  }

  function deliver() {
    var funnel = (window.AIHIVE && window.AIHIVE.funnel) || {};
    var action = String(funnel.formAction || "").trim();
    if (!action) {
      showStatus("Recorded in this browser only. Set formAction in funnel.json to deliver it. To reach a person now, use WhatsApp, phone, or the calendar.");
      if (submitButton) submitButton.disabled = false;
      return;
    }
    form.action = action;
    form.method = funnel.formMethod || "POST";
    showStatus("Sending the request.");
    window.setTimeout(function () {
      form.submit();
    }, 400);
  }

  Array.prototype.forEach.call(form.elements, function (input) {
    if (!input.id || !rules[input.name]) return;
    input.addEventListener("input", function () {
      if (input.getAttribute("aria-invalid") === "true") setFieldError(input, "");
    });
  });

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    if (!validate()) {
      var firstInvalid = form.querySelector("[aria-invalid='true']");
      if (firstInvalid) firstInvalid.focus();
      return;
    }
    var honeypot = form.querySelector("[data-honeypot]");
    if (honeypot && honeypot.value.trim()) {
      showStatus("Request recorded.");
      return;
    }
    if (submitButton) submitButton.disabled = true;
    runtimeReady().then(deliver).catch(function () {
      if (submitButton) submitButton.disabled = false;
      showStatus("The request did not send. Try again, or use WhatsApp, phone, or the calendar.");
    });
  });
})();
