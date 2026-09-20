/**
 * Universal Number Counter Animation Engine for Payroll MGM
 * Animates numerical values from 0 (or start value) to their target value smoothly.
 * Supports integers, decimals, currencies ($), suffixes (hrs, Days, %, / max),
 * thousands separators (commas), IntersectionObserver, and prefers-reduced-motion.
 */

(function () {
  'use strict';

  // Easing function: easeOutCubic for smooth, natural deceleration
  function easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3);
  }

  // Format a number with optional decimal places and thousands commas
  function formatNumber(value, decimals, hasCommas) {
    var fixed = value.toFixed(decimals);
    if (hasCommas) {
      var parts = fixed.split('.');
      parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
      return parts.join('.');
    }
    return fixed;
  }

  // Parse text or element content into prefix, number, suffix, and formatting rules
  function parseCounterContent(element) {
    // If element contains children that are marked as counters, yield to children
    if (element.querySelectorAll('.counter-value, [data-counter]').length > 0) {
      return null;
    }

    var explicitTarget = element.getAttribute('data-target') || element.getAttribute('data-count');
    var rawText = (element.textContent || '').trim();

    // Check for explicit target attribute
    if (explicitTarget !== null && !isNaN(parseFloat(explicitTarget))) {
      var targetNum = parseFloat(explicitTarget);
      var prefix = element.getAttribute('data-prefix') || '';
      var suffix = element.getAttribute('data-suffix') || '';
      var decimals = parseInt(element.getAttribute('data-decimals') || '0', 10);
      var hasCommas = element.hasAttribute('data-commas') || targetNum >= 1000;
      return {
        target: targetNum,
        prefix: prefix,
        suffix: suffix,
        decimals: decimals,
        hasCommas: hasCommas,
        originalText: rawText || (prefix + formatNumber(targetNum, decimals, hasCommas) + suffix)
      };
    }

    // Skip non-numeric values like "N/A", "-", "None", "Not Checked In"
    if (!rawText || /^(N\/A|-|--|None|null|undefined)$/i.test(rawText)) {
      return null;
    }

    // Regex to extract prefix, number (including commas and optional decimal part), and suffix
    // Examples matched:
    // "24" -> prefix: "", num: "24", suffix: ""
    // "$1,250.50" -> prefix: "$", num: "1,250.50", suffix: ""
    // "15 Days" -> prefix: "", num: "15", suffix: " Days"
    // "42.5 hrs" -> prefix: "", num: "42.5", suffix: " hrs"
    // "18 / 24" -> prefix: "", num: "18", suffix: " / 24"
    // "-$500.00" -> prefix: "-$", num: "500.00", suffix: ""
    var match = rawText.match(/^([^0-9]*?)([\+\-]?\d[\d,]*(?:\.\d+)?)([\s\S]*)$/);
    if (!match) {
      return null;
    }

    var prefixStr = match[1] || '';
    var numStr = match[2];
    var suffixStr = match[3] || '';

    var cleanNumStr = numStr.replace(/,/g, '');
    var parsedValue = parseFloat(cleanNumStr);
    if (isNaN(parsedValue)) {
      return null;
    }

    // Determine decimal precision from the matched number
    var decMatch = numStr.match(/\.(\d+)/);
    var decPlaces = decMatch ? decMatch[1].length : 0;
    var commaSeparated = numStr.indexOf(',') !== -1 || Math.abs(parsedValue) >= 1000;

    return {
      target: parsedValue,
      prefix: prefixStr,
      suffix: suffixStr,
      decimals: decPlaces,
      hasCommas: commaSeparated,
      originalText: rawText
    };
  }

  // Animate a single counter element
  function animateCounter(element, options) {
    if (!element) return;

    // Check if already processed unless force option is passed
    if (element.dataset.counterDone === 'true' && (!options || !options.force)) {
      return;
    }

    var parsed = parseCounterContent(element);
    if (!parsed) {
      return;
    }

    // Mark as handled to avoid duplicate animations
    element.dataset.counterDone = 'true';

    // Respect reduced motion preference
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      element.textContent = parsed.originalText;
      return;
    }

    var duration = parseInt(element.getAttribute('data-duration') || (options && options.duration) || '1200', 10);
    var startVal = parseFloat(element.getAttribute('data-start') || '0');
    var targetVal = parsed.target;

    // If target is 0, give a short snappy animation
    if (targetVal === 0 && startVal === 0) {
      element.textContent = parsed.prefix + formatNumber(0, parsed.decimals, parsed.hasCommas) + parsed.suffix;
      element.classList.add('counter-finished');
      return;
    }

    if (duration <= 0) duration = 1200;

    // Add animating state class
    element.classList.add('counter-animating');

    // Set initial rendered frame
    var initialDisplay = (parsed.prefix.indexOf('-') !== -1 && startVal < 0) ? Math.abs(startVal) : startVal;
    element.textContent = parsed.prefix + formatNumber(initialDisplay, parsed.decimals, parsed.hasCommas) + parsed.suffix;

    var startTime = null;

    function step(timestamp) {
      if (!startTime) startTime = timestamp;
      var elapsed = timestamp - startTime;
      var progress = Math.min(elapsed / duration, 1);
      var easeProgress = easeOutCubic(progress);

      var current = startVal + (targetVal - startVal) * easeProgress;
      var displayVal = (parsed.prefix.indexOf('-') !== -1 && current < 0) ? Math.abs(current) : current;
      element.textContent = parsed.prefix + formatNumber(displayVal, parsed.decimals, parsed.hasCommas) + parsed.suffix;

      if (progress < 1) {
        window.requestAnimationFrame(step);
      } else {
        // Guarantee clean exact target value at completion
        var finalDisplay = (parsed.prefix.indexOf('-') !== -1 && targetVal < 0) ? Math.abs(targetVal) : targetVal;
        element.textContent = parsed.prefix + formatNumber(finalDisplay, parsed.decimals, parsed.hasCommas) + parsed.suffix;
        element.classList.remove('counter-animating');
        element.classList.add('counter-finished');

        if (options && typeof options.onComplete === 'function') {
          options.onComplete(element);
        }
      }
    }

    window.requestAnimationFrame(step);
  }

  // Find and observe/animate all eligible counter elements
  function initCounters(container) {
    var root = container || document;

    // Target elements explicitly marked or typical metric headings
    var selectors = [
      '.counter-value',
      '[data-counter]',
      '.stat-counter',
      '.rate-percentage',
      '.statistics-details h3',
      '.stat-card h4',
      '.stat-card h3',
      '.card-tale h3',
      '.card-dark-blue h3',
      '.card-light-blue h3'
    ];

    var elements = root.querySelectorAll(selectors.join(', '));
    if (!elements || elements.length === 0) {
      return;
    }

    if ('IntersectionObserver' in window) {
      var observer = new IntersectionObserver(function (entries, obs) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            animateCounter(entry.target);
            obs.unobserve(entry.target);
          }
        });
      }, {
        root: null,
        threshold: 0.1,
        rootMargin: '0px 0px -10px 0px'
      });

      elements.forEach(function (el) {
        if (el.dataset.counterDone !== 'true') {
          observer.observe(el);
        }
      });
    } else {
      // Fallback for environments without IntersectionObserver
      elements.forEach(function (el) {
        animateCounter(el);
      });
    }
  }

  // Export globally
  window.animateCounter = animateCounter;
  window.initCounterAnimations = initCounters;

  // Auto-init on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      initCounters();
    });
  } else {
    initCounters();
  }
})();
