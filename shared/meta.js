(function () {
  "use strict";

  var runtime = window.AIHIVE || {};
  var site = (runtime.config && runtime.config.site) || {};
  var funnel = runtime.funnel || {};

  function text(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function existing(selector) {
    var node = document.head.querySelector(selector);
    return node ? text(node.getAttribute("content")) : "";
  }

  function choose(override, current, fallback) {
    return text(override) || text(current) || text(fallback);
  }

  function upsertMeta(attribute, key, content) {
    var value = text(content);
    if (!value) return;
    var selector = "meta[" + attribute + "='" + CSS.escape(key) + "']";
    var node = document.head.querySelector(selector);
    if (!node) {
      node = document.createElement("meta");
      node.setAttribute(attribute, key);
      document.head.appendChild(node);
    }
    node.setAttribute("content", value);
  }

  function upsertCanonical(href) {
    var node = document.head.querySelector("link[rel='canonical']");
    if (!node) {
      node = document.createElement("link");
      node.rel = "canonical";
      document.head.appendChild(node);
    }
    node.href = href;
  }

  function absoluteImage(src) {
    var value = text(src);
    if (!value) return "";
    if (/^https?:\/\//i.test(value)) return value;
    var domain = text(site.domain).replace(/\/$/, "") || window.location.origin;
    if (value.charAt(0) !== "/") value = "/" + value;
    return domain + value;
  }

  var title = choose(funnel.title, document.title, site.title || site.name);
  var description = choose(funnel.description, existing("meta[name='description']"), site.description);
  var image = absoluteImage(funnel.image || site.image);
  var path = typeof runtime.publishedPath === "function" ? runtime.publishedPath() : "/";
  var domain = text(site.domain).replace(/\/$/, "") || window.location.origin;
  var canonical = domain + path;
  var robots = existing("meta[name='robots']").toLowerCase();
  var indexable = robots.indexOf("noindex") === -1;

  if (title) document.title = title;
  upsertMeta("name", "description", description);
  if (indexable) upsertCanonical(canonical);

  upsertMeta("property", "og:title", title);
  upsertMeta("property", "og:description", description);
  if (indexable) upsertMeta("property", "og:url", canonical);
  upsertMeta("property", "og:type", funnel.type || "website");
  upsertMeta("property", "og:site_name", site.name || "AIHive");
  upsertMeta("property", "og:locale", site.locale || "en_US");

  if (image) {
    upsertMeta("property", "og:image", image);
    upsertMeta("name", "twitter:image", image);
    upsertMeta("name", "twitter:card", "summary_large_image");
  } else if (!existing("meta[name='twitter:card']")) {
    upsertMeta("name", "twitter:card", "summary");
  }

  upsertMeta("name", "twitter:title", title);
  upsertMeta("name", "twitter:description", description);
  upsertMeta("name", "twitter:site", site.twitter);

  if (!document.querySelector("link[rel~='icon']")) {
    var icon = document.createElement("link");
    icon.rel = "icon";
    icon.href = "/shared/mark.svg";
    icon.type = "image/svg+xml";
    document.head.appendChild(icon);
  }
})();
