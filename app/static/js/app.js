// Swarm AI — front-end behaviour (no framework required)
document.addEventListener("DOMContentLoaded", function () {

  // ---------------------------------------------------------------
  // Auto-dismiss flash messages after a few seconds
  // ---------------------------------------------------------------
  document.querySelectorAll(".flash").forEach(function (el) {
    // Don't auto-dismiss messages containing a link (e.g. a reset link) —
    // the user needs time to read and click it.
    if (el.querySelector("a")) return;

    var dismissAt = 6000;
    var timer;
    function schedule() {
      timer = setTimeout(function () {
        el.style.transition = "opacity .4s ease";
        el.style.opacity = "0";
        setTimeout(function () { el.remove(); }, 400);
      }, dismissAt);
    }
    // Pause on hover/focus so the person can finish reading.
    el.addEventListener("mouseenter", function () { clearTimeout(timer); });
    el.addEventListener("mouseleave", schedule);
    schedule();
  });

  // ---------------------------------------------------------------
  // Auto-linkify raw URLs inside flash messages (e.g. a password
  // reset link surfaced via flash while no mail server is wired up)
  // so the user has a clickable link instead of plain text.
  // ---------------------------------------------------------------
  document.querySelectorAll(".flash-text").forEach(function (el) {
    var urlPattern = /(https?:\/\/[^\s]+)/g;
    if (!urlPattern.test(el.textContent)) return;
    el.innerHTML = el.textContent.replace(urlPattern, function (url) {
      return '<a href="' + url + '">' + url + "</a>";
    });
  });

  // ---------------------------------------------------------------
  // Mobile nav toggle
  // ---------------------------------------------------------------
  var navToggle = document.querySelector(".nav-toggle");
  var navPanel = document.querySelector(".nav-panel");
  if (navToggle && navPanel) {
    function closeNav() {
      navToggle.classList.remove("is-open");
      navPanel.classList.remove("is-open");
      navToggle.setAttribute("aria-expanded", "false");
      document.body.style.overflow = "";
    }
    function openNav() {
      navToggle.classList.add("is-open");
      navPanel.classList.add("is-open");
      navToggle.setAttribute("aria-expanded", "true");
      document.body.style.overflow = "hidden"; // lock background scroll while the panel is open
    }
    navToggle.addEventListener("click", function (e) {
      e.stopPropagation();
      var open = navToggle.classList.contains("is-open");
      if (open) closeNav(); else openNav();
    });
    navPanel.querySelectorAll("a").forEach(function (a) {
      a.addEventListener("click", closeNav);
    });
    // Close on outside click/tap
    document.addEventListener("click", function (e) {
      if (!navToggle.classList.contains("is-open")) return;
      if (navPanel.contains(e.target) || navToggle.contains(e.target)) return;
      closeNav();
    });
    // Close on Escape
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeNav();
    });
    // Close (and unlock scroll) if the viewport is resized back to desktop
    window.addEventListener("resize", function () {
      if (window.innerWidth > 900) closeNav();
    });
  }

  // ---------------------------------------------------------------
  // Scroll-reveal animation: fade-in / slide-up when elements enter view
  // ---------------------------------------------------------------
  var reveals = document.querySelectorAll(".reveal");
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  if (reveals.length && !reduceMotion && "IntersectionObserver" in window) {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.15, rootMargin: "0px 0px -40px 0px" });

    reveals.forEach(function (el) { observer.observe(el); });
  } else {
    reveals.forEach(function (el) { el.classList.add("is-visible"); });
  }

  // ---------------------------------------------------------------
  // Hero network / swarm animation (lightweight canvas)
  // A handful of slowly-drifting nodes with connecting lines that
  // brighten with proximity — sophisticated but intentionally sparse.
  // ---------------------------------------------------------------
  var canvas = document.querySelector(".net-canvas");
  if (canvas && !reduceMotion) {
    var ctx = canvas.getContext("2d");
    var nodes = [];
    var NODE_COUNT = 26;
    var MAX_DIST = 130;
    var width, height, dpr;
    var rafId;
    var running = true;

    function resize() {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = canvas.clientWidth;
      height = canvas.clientHeight;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function makeNodes() {
      nodes = [];
      for (var i = 0; i < NODE_COUNT; i++) {
        nodes.push({
          x: Math.random() * width,
          y: Math.random() * height,
          vx: (Math.random() - 0.5) * 0.18,
          vy: (Math.random() - 0.5) * 0.18,
          r: 1.2 + Math.random() * 1.6
        });
      }
    }

    function step() {
      if (!running) return;
      ctx.clearRect(0, 0, width, height);

      for (var i = 0; i < nodes.length; i++) {
        var n = nodes[i];
        n.x += n.vx; n.y += n.vy;
        if (n.x < 0 || n.x > width) n.vx *= -1;
        if (n.y < 0 || n.y > height) n.vy *= -1;
      }

      for (var i = 0; i < nodes.length; i++) {
        for (var j = i + 1; j < nodes.length; j++) {
          var a = nodes[i], b = nodes[j];
          var dx = a.x - b.x, dy = a.y - b.y;
          var dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < MAX_DIST) {
            var alpha = (1 - dist / MAX_DIST) * 0.35;
            ctx.strokeStyle = "rgba(180,146,63," + alpha + ")";
            ctx.lineWidth = 0.7;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
          }
        }
      }

      for (var i = 0; i < nodes.length; i++) {
        var n = nodes[i];
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(138,108,27,0.55)";
        ctx.fill();
      }

      rafId = requestAnimationFrame(step);
    }

    resize();
    makeNodes();
    step();

    window.addEventListener("resize", function () {
      resize();
      makeNodes();
    });

    document.addEventListener("visibilitychange", function () {
      running = !document.hidden;
      if (running) { rafId = requestAnimationFrame(step); }
      else { cancelAnimationFrame(rafId); }
    });
  }

  // ---------------------------------------------------------------
  // Password visibility toggle
  // Wraps each password input in a .pw-field (if not already) and
  // inserts an eye/eye-off button that flips type="password" <-> "text".
  // ---------------------------------------------------------------
  var EYE_ICON =
    '<svg class="icon-eye" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">' +
    '<path d="M1.5 12s4-7.5 10.5-7.5S22.5 12 22.5 12s-4 7.5-10.5 7.5S1.5 12 1.5 12z" stroke-linecap="round" stroke-linejoin="round"/>' +
    '<circle cx="12" cy="12" r="3.2" stroke-linecap="round" stroke-linejoin="round"/></svg>' +
    '<svg class="icon-eye-off" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">' +
    '<path d="M3 3l18 18M10.6 5.2c.45-.06.92-.1 1.4-.1 6.5 0 10.5 7.5 10.5 7.5a20 20 0 0 1-3.6 4.7M6.6 6.6C3.4 8.6 1.5 12 1.5 12s4 7.5 10.5 7.5c1.8 0 3.4-.5 4.8-1.3M9.9 9.9a3.2 3.2 0 0 0 4.2 4.2" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  document.querySelectorAll('input[type="password"]').forEach(function (input) {
    var wrap = input.closest(".pw-field");
    if (!wrap) {
      wrap = document.createElement("div");
      wrap.className = "pw-field";
      input.parentNode.insertBefore(wrap, input);
      wrap.appendChild(input);
    }
    if (wrap.querySelector(".pw-toggle")) return;

    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "pw-toggle";
    btn.setAttribute("aria-label", "Show password");
    btn.setAttribute("aria-pressed", "false");
    btn.innerHTML = EYE_ICON;
    wrap.appendChild(btn);

    btn.addEventListener("click", function () {
      var showing = input.type === "text";
      input.type = showing ? "password" : "text";
      btn.classList.toggle("is-visible", !showing);
      btn.setAttribute("aria-pressed", showing ? "false" : "true");
      btn.setAttribute("aria-label", showing ? "Show password" : "Hide password");
    });
  });

  // ---------------------------------------------------------------
  // Live password requirement checklist (visual only — the server
  // still enforces the real rules; this just guides the user).
  // ---------------------------------------------------------------
  document.querySelectorAll(".pw-requirements").forEach(function (list) {
    var targetId = list.getAttribute("data-target");
    var input = targetId && document.getElementById(targetId);
    if (!input) return;
    var items = list.querySelectorAll("li[data-rule]");

    function evaluate() {
      var val = input.value || "";
      items.forEach(function (li) {
        var rule = li.getAttribute("data-rule");
        var met = false;
        if (rule === "length") met = val.length >= 8;
        else if (rule === "letter") met = /[A-Za-z]/.test(val);
        else if (rule === "number") met = /[0-9]/.test(val);
        li.classList.toggle("is-met", met);
      });
    }
    input.addEventListener("input", evaluate);
    evaluate();
  });

  // ---------------------------------------------------------------
  // Copy-to-clipboard buttons ([data-copy] holds the text, or
  // data-copy-target points to an element whose textContent is copied)
  // ---------------------------------------------------------------
  document.querySelectorAll(".copy-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var text = btn.getAttribute("data-copy");
      if (!text) {
        var targetSel = btn.getAttribute("data-copy-target");
        var target = targetSel && document.querySelector(targetSel);
        text = target ? target.textContent.trim() : "";
      }
      if (!text) return;

      var done = function () {
        var original = btn.querySelector(".copy-label");
        var originalText = original ? original.textContent : btn.textContent;
        btn.classList.add("is-copied");
        if (original) original.textContent = "Copied";
        setTimeout(function () {
          btn.classList.remove("is-copied");
          if (original) original.textContent = originalText;
        }, 1800);
      };

      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done).catch(function () {
          fallbackCopy(text); done();
        });
      } else {
        fallbackCopy(text); done();
      }
    });
  });

  function fallbackCopy(text) {
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); } catch (e) { /* no-op */ }
    document.body.removeChild(ta);
  }

  // ---------------------------------------------------------------
  // Accordion (FAQ)
  // ---------------------------------------------------------------
  document.querySelectorAll(".accordion-trigger").forEach(function (trigger) {
    trigger.addEventListener("click", function () {
      var item = trigger.closest(".accordion-item");
      item.classList.toggle("is-open");
      trigger.setAttribute("aria-expanded", item.classList.contains("is-open") ? "true" : "false");
    });
  });

  // ---------------------------------------------------------------
  // Button loading state on form submit — visual feedback while the
  // request is in flight, without interfering with normal submission
  // or client-side validation (re-enables if the form is invalid).
  // ---------------------------------------------------------------
  document.querySelectorAll("form").forEach(function (form) {
    form.addEventListener("submit", function () {
      if (typeof form.checkValidity === "function" && !form.checkValidity()) return;
      var submitBtn = form.querySelector('button[type="submit"], button:not([type])');
      if (!submitBtn || submitBtn.classList.contains("is-loading")) return;
      var labelSpan = submitBtn.querySelector(".btn-label");
      if (!labelSpan) {
        labelSpan = document.createElement("span");
        labelSpan.className = "btn-label";
        labelSpan.innerHTML = submitBtn.innerHTML;
        submitBtn.innerHTML = "";
        submitBtn.appendChild(labelSpan);
      }
      if (!submitBtn.querySelector(".btn-spinner")) {
        var spinner = document.createElement("span");
        spinner.className = "btn-spinner";
        submitBtn.appendChild(spinner);
      }
      submitBtn.classList.add("is-loading");
      submitBtn.disabled = true;
    });
  });
});
