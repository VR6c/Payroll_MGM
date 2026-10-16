/**
 * Payroll MGM - Executive Custom Time Picker Component
 * Replaces the native browser time popup with a modern, beautifully styled executive time picker.
 */
(function ($) {
  'use strict';

  var $timePopover = null;
  var activeTimeInput = null;

  var currentHour12 = 8;
  var currentMinute = 0;
  var currentPeriod = 'AM';

  function pad(n) {
    return n < 10 ? '0' + n : '' + n;
  }

  // Parse time string (supports "17:00", "05:00 PM", "5:00 PM", "8:30")
  function parseTime(val) {
    if (!val || typeof val !== 'string') return null;
    val = val.trim();

    // Match 12h format: e.g. "05:00 PM" or "5:00PM"
    var m12 = val.match(/^(\d{1,2}):(\d{2})\s*(AM|PM)?$/i);
    if (m12) {
      var h = parseInt(m12[1], 10);
      var m = parseInt(m12[2], 10);
      var p = m12[3] ? m12[3].toUpperCase() : null;

      if (p) {
        if (h === 12) h = (p === 'AM') ? 0 : 12;
        else if (p === 'PM') h += 12;
      }
      return { hour24: h, minute: m };
    }
    return null;
  }

  function formatTime24(h12, min, period) {
    var h24 = h12;
    if (period === 'AM') {
      if (h24 === 12) h24 = 0;
    } else {
      if (h24 !== 12) h24 += 12;
    }
    return pad(h24) + ':' + pad(min);
  }

  function formatTimeDisplay(h12, min, period) {
    return pad(h12) + ':' + pad(min) + ' ' + period;
  }

  function createTimePopover() {
    if ($timePopover) return;

    var html = [
      '<div class="custom-time-popover" id="customTimePopover" style="display: none;">',
      '  <div class="time-header">',
      '    <div class="time-header-title"><i class="mdi mdi-clock-outline me-1 text-primary"></i> Select Time</div>',
      '    <div class="time-display-badge"><span class="time-badge-text">08:00 AM</span></div>',
      '  </div>',
      '  <div class="time-presets-bar">',
      '    <button type="button" class="time-preset-chip" data-time="08:00">08:00 AM</button>',
      '    <button type="button" class="time-preset-chip" data-time="12:00">12:00 PM</button>',
      '    <button type="button" class="time-preset-chip" data-time="13:00">01:00 PM</button>',
      '    <button type="button" class="time-preset-chip" data-time="17:00">05:00 PM</button>',
      '  </div>',
      '  <div class="time-columns-wrap">',
      '    <div class="time-col time-col-hours" title="Hour">',
      '      <div class="time-col-header">Hour</div>',
      '      <div class="time-col-list time-hours-list"></div>',
      '    </div>',
      '    <div class="time-col-sep">:</div>',
      '    <div class="time-col time-col-minutes" title="Minute">',
      '      <div class="time-col-header">Min</div>',
      '      <div class="time-col-list time-minutes-list"></div>',
      '    </div>',
      '    <div class="time-col time-col-period" title="AM/PM">',
      '      <div class="time-col-header">Period</div>',
      '      <div class="time-period-selector">',
      '        <button type="button" class="time-period-btn" data-period="AM">AM</button>',
      '        <button type="button" class="time-period-btn" data-period="PM">PM</button>',
      '      </div>',
      '    </div>',
      '  </div>',
      '  <div class="time-footer">',
      '    <button type="button" class="time-footer-btn time-btn-clear">Clear</button>',
      '    <div class="d-flex gap-2">',
      '      <button type="button" class="time-footer-btn time-btn-now">Now</button>',
      '      <button type="button" class="time-footer-btn time-btn-apply btn btn-primary btn-sm text-white px-3">Done</button>',
      '    </div>',
      '  </div>',
      '</div>'
    ].join('');

    $timePopover = $(html).appendTo('body');

    // Populate Hours (01 - 12)
    var $hoursList = $timePopover.find('.time-hours-list');
    for (var h = 1; h <= 12; h++) {
      $hoursList.append(
        $('<button type="button" class="time-item-btn time-hour-item">')
          .text(pad(h))
          .attr('data-hour', h)
      );
    }

    // Populate Minutes (00, 05, 10, ... 55)
    var $minsList = $timePopover.find('.time-minutes-list');
    for (var m = 0; m < 60; m += 5) {
      $minsList.append(
        $('<button type="button" class="time-item-btn time-min-item">')
          .text(pad(m))
          .attr('data-min', m)
      );
    }

    // Click Hour
    $timePopover.on('click', '.time-hour-item', function (e) {
      e.stopPropagation();
      currentHour12 = parseInt($(this).attr('data-hour'), 10);
      updateTimeDisplay();
      scrollToActiveItems();
    });

    // Click Minute
    $timePopover.on('click', '.time-min-item', function (e) {
      e.stopPropagation();
      currentMinute = parseInt($(this).attr('data-min'), 10);
      updateTimeDisplay();
      scrollToActiveItems();
    });

    // Click AM/PM
    $timePopover.on('click', '.time-period-btn', function (e) {
      e.stopPropagation();
      currentPeriod = $(this).attr('data-period');
      updateTimeDisplay();
    });

    // Click Preset Chip
    $timePopover.on('click', '.time-preset-chip', function (e) {
      e.stopPropagation();
      var tStr = $(this).attr('data-time');
      if (tStr) {
        applyTimeToInput(tStr);
        hideTimePopover();
      }
    });

    // Clear Button
    $timePopover.on('click', '.time-btn-clear', function (e) {
      e.stopPropagation();
      if (activeTimeInput) {
        $(activeTimeInput).val('');
        try { activeTimeInput.value = ''; } catch (err) {}
        $(activeTimeInput).trigger('change').trigger('input');
        if (typeof Event === 'function') {
          activeTimeInput.dispatchEvent(new Event('change', { bubbles: true }));
          activeTimeInput.dispatchEvent(new Event('input', { bubbles: true }));
        }
      }
      hideTimePopover();
    });

    // Now Button
    $timePopover.on('click', '.time-btn-now', function (e) {
      e.stopPropagation();
      var now = new Date();
      var h24 = now.getHours();
      var min = now.getMinutes();
      // Round to nearest 5 for smooth display
      min = Math.round(min / 5) * 5;
      if (min === 60) {
        min = 0;
        h24 = (h24 + 1) % 24;
      }
      currentPeriod = h24 >= 12 ? 'PM' : 'AM';
      currentHour12 = h24 % 12 || 12;
      currentMinute = min;
      updateTimeDisplay();
      scrollToActiveItems();
    });

    // Done / Apply Button
    $timePopover.on('click', '.time-btn-apply', function (e) {
      e.stopPropagation();
      var t24 = formatTime24(currentHour12, currentMinute, currentPeriod);
      applyTimeToInput(t24);
      hideTimePopover();
    });

    // Prevent clicks inside popover from closing it
    $timePopover.on('click mousedown', function (e) {
      e.stopPropagation();
    });
  }

  function updateTimeDisplay() {
    if (!$timePopover) return;

    var displayStr = formatTimeDisplay(currentHour12, currentMinute, currentPeriod);
    $timePopover.find('.time-badge-text').text(displayStr);

    // Update active Hour
    $timePopover.find('.time-hour-item').removeClass('is-selected');
    $timePopover.find('.time-hour-item[data-hour="' + currentHour12 + '"]').addClass('is-selected');

    // Update active Minute
    $timePopover.find('.time-min-item').removeClass('is-selected');
    $timePopover.find('.time-min-item[data-min="' + currentMinute + '"]').addClass('is-selected');

    // Update active Period
    $timePopover.find('.time-period-btn').removeClass('is-selected');
    $timePopover.find('.time-period-btn[data-period="' + currentPeriod + '"]').addClass('is-selected');
  }

  function scrollToActiveItems() {
    if (!$timePopover || !$timePopover.is(':visible')) return;

    var $hList = $timePopover.find('.time-hours-list');
    var $activeH = $hList.find('.time-hour-item.is-selected');
    if ($activeH.length) {
      $hList.scrollTop($activeH.position().top + $hList.scrollTop() - 40);
    }

    var $mList = $timePopover.find('.time-minutes-list');
    var $activeM = $mList.find('.time-min-item.is-selected');
    if ($activeM.length) {
      $mList.scrollTop($activeM.position().top + $mList.scrollTop() - 40);
    }
  }

  function applyTimeToInput(timeStr24) {
    if (!activeTimeInput) return;

    $(activeTimeInput).val(timeStr24);
    try {
      activeTimeInput.value = timeStr24;
    } catch (err) {}

    $(activeTimeInput).trigger('change').trigger('input');
    if (typeof Event === 'function') {
      activeTimeInput.dispatchEvent(new Event('change', { bubbles: true }));
      activeTimeInput.dispatchEvent(new Event('input', { bubbles: true }));
    }
  }

  function positionTimePopover() {
    if (!$timePopover || !$timePopover.is(':visible') || !activeTimeInput) return;

    var $container = $(activeTimeInput).closest('.component-select-time, .period-date-wrap, .input-group');
    if (!$container.length) $container = $(activeTimeInput);

    var domEl = $container[0];
    if (!domEl) {
      hideTimePopover();
      return;
    }

    var rect = domEl.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0 || (rect.top === 0 && rect.bottom === 0 && rect.left === 0)) {
      hideTimePopover();
      return;
    }

    var viewportWidth = window.innerWidth || document.documentElement.clientWidth;
    var viewportHeight = window.innerHeight || document.documentElement.clientHeight;
    var popoverWidth = Math.min(280, viewportWidth - 20);
    var popoverHeight = 330;

    var top = rect.bottom + 6;
    var left = rect.left;

    // Center on mobile viewports (< 576px like iPhone SE)
    if (viewportWidth < 576) {
      left = Math.max(10, Math.floor((viewportWidth - popoverWidth) / 2));
    } else {
      // Right bounds check
      if (left + popoverWidth > viewportWidth - 16) {
        left = Math.max(16, viewportWidth - popoverWidth - 16);
      }
      if (left < 16) {
        left = 16;
      }
    }

    // Bottom bounds check (flip above)
    if (top + popoverHeight > viewportHeight - 16) {
      if (rect.top - popoverHeight - 6 >= 16) {
        top = rect.top - popoverHeight - 6;
      } else {
        top = Math.max(16, viewportHeight - popoverHeight - 16);
      }
    }

    $timePopover.css({
      top: Math.round(top) + 'px',
      left: Math.round(left) + 'px'
    });
  }

  function showTimePopover(input) {
    if (!input) return;

    var $container = $(input).closest('.component-select-time, .input-group');
    if (!$container.length) $container = $(input);

    var domEl = $container[0];
    if (!domEl) return;

    var rect = domEl.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0 || (rect.top === 0 && rect.bottom === 0 && rect.left === 0)) {
      return;
    }

    // Hide date popover if open
    if (window.PayrollDatePicker && typeof window.PayrollDatePicker.hide === 'function') {
      window.PayrollDatePicker.hide();
    }

    createTimePopover();
    activeTimeInput = input;

    var val = $(input).val();
    var parsed = parseTime(val);

    if (parsed) {
      var h24 = parsed.hour24;
      currentPeriod = h24 >= 12 ? 'PM' : 'AM';
      currentHour12 = h24 % 12 || 12;
      currentMinute = parsed.minute;
    } else {
      var d = new Date();
      var nowH = d.getHours();
      currentPeriod = nowH >= 12 ? 'PM' : 'AM';
      currentHour12 = nowH % 12 || 12;
      currentMinute = Math.round(d.getMinutes() / 5) * 5;
      if (currentMinute === 60) {
        currentMinute = 0;
        currentHour12 = (currentHour12 % 12) + 1;
      }
    }

    updateTimeDisplay();
    $timePopover.addClass('is-open').show();
    positionTimePopover();
    scrollToActiveItems();
    $container.addClass('picker-active');
  }

  function hideTimePopover() {
    if ($timePopover && $timePopover.is(':visible')) {
      $timePopover.removeClass('is-open').hide();
    }
    $('.component-select-time, .input-group').removeClass('picker-active');
    activeTimeInput = null;
  }

  function enhanceTimeInputs(context) {
    var $root = context ? $(context) : $(document);
    $root.find('input[type="time"]').each(function () {
      var $el = $(this);

      // Skip if already has a trigger sibling (pre-built in template)
      if ($el.siblings('.select-time-trigger').length) {
        $el.attr('type', 'text');
        $el.attr('autocomplete', 'off');
        if (!$el.attr('placeholder')) {
          $el.attr('placeholder', 'HH:MM');
        }
        $el.addClass('select-time-input');
        return;
      }

      $el.attr('type', 'text');
      $el.attr('autocomplete', 'off');
      if (!$el.attr('placeholder')) {
        $el.attr('placeholder', 'HH:MM');
      }
      $el.addClass('select-time-input');

      // If not already inside an input-group, wrap with an input group and clock trigger
      if (!$el.closest('.input-group, .component-select-time').length) {
        $el.wrap('<div class="input-group component-select-time time-picker-group"></div>');
        $el.after(
          '<span class="input-group-text select-time-trigger text-muted" role="button" tabindex="0" title="Open time picker">' +
            '<i class="mdi mdi-clock-outline"></i>' +
          '</span>'
        );
      } else if (!$el.siblings('.select-time-trigger').length) {
        $el.parent().addClass('component-select-time');
        $el.after(
          '<span class="input-group-text select-time-trigger text-muted" role="button" tabindex="0" title="Open time picker">' +
            '<i class="mdi mdi-clock-outline"></i>' +
          '</span>'
        );
      }
    });
  }

  // Document Click & Keydown listeners
  $(document).on('click', function (e) {
    if ($timePopover && $timePopover.is(':visible')) {
      if (!$(e.target).closest('.component-select-time, .select-time-input, .select-time-trigger, .period-time-trigger, .period-date-wrap, .custom-time-popover').length) {
        hideTimePopover();
      }
    }
  });

  $(document).on('keydown', function (e) {
    if (e.key === 'Escape') {
      hideTimePopover();
    }
  });

  // Reposition on window resize or scroll
  $(window).on('resize', function () {
    if ($timePopover && $timePopover.is(':visible')) {
      positionTimePopover();
    }
  });

  document.addEventListener('scroll', function (e) {
    if ($timePopover && $timePopover.is(':visible')) {
      if (!e.target || !e.target.closest || !e.target.closest('.custom-time-popover')) {
        positionTimePopover();
      }
    }
  }, true);

  // Attach to select-time-input (click only)
  $(document).on('click', '.select-time-input', function (e) {
    e.preventDefault();
    if (activeTimeInput === this && $timePopover && $timePopover.is(':visible')) {
      hideTimePopover();
    } else {
      showTimePopover(this);
    }
  });

  // Attach to clock trigger icon
  $(document).on('click', '.select-time-trigger', function (e) {
    e.preventDefault();
    e.stopPropagation();
    $(this).blur();
    var input = $(this).siblings('.select-time-input')[0] || $(this).closest('.input-group').find('.select-time-input')[0];
    if (input) {
      if (activeTimeInput === input && $timePopover && $timePopover.is(':visible')) {
        hideTimePopover();
      } else {
        showTimePopover(input);
      }
    }
  });

  // Support keyboard trigger
  $(document).on('keydown', '.select-time-input, .select-time-trigger', function (e) {
    if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
      var input = $(this).hasClass('select-time-input') ? this : $(this).siblings('.select-time-input')[0];
      if (input && (!$timePopover || !$timePopover.is(':visible'))) {
        e.preventDefault();
        showTimePopover(input);
      }
    }
  });

  // Close immediately on modal close
  $(document).on('hide.bs.modal hidden.bs.modal', function () {
    hideTimePopover();
  });

  // Initialize and observe for dynamic additions
  $(function () {
    enhanceTimeInputs();

    if (typeof MutationObserver !== 'undefined') {
      var observer = new MutationObserver(function (mutations) {
        var shouldEnhance = false;
        for (var i = 0; i < mutations.length; i++) {
          if (mutations[i].addedNodes && mutations[i].addedNodes.length > 0) {
            shouldEnhance = true;
            break;
          }
        }
        if (shouldEnhance) {
          enhanceTimeInputs();
        }
      });
      if (document.body) {
        observer.observe(document.body, { childList: true, subtree: true });
      }
    }
  });

  // Global export
  window.PayrollTimePicker = {
    show: showTimePopover,
    hide: hideTimePopover,
    enhance: enhanceTimeInputs
  };

})(jQuery);
