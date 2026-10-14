/**
 * Payroll MGM - Executive Custom Date Picker Component
 * Replaces the native browser calendar popup with a modern, beautifully styled calendar.
 */
(function ($) {
  'use strict';

  var months = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  var shortMonths = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
  ];

  var weekdays = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

  var $popover = null;
  var activeInput = null;
  var viewYear = new Date().getFullYear();
  var viewMonth = new Date().getMonth();
  var isMonthPickerMode = false;

  function pad(n) {
    return n < 10 ? '0' + n : '' + n;
  }

  function formatDate(y, m, d) {
    return y + '-' + pad(m + 1) + '-' + pad(d);
  }

  function isMonthInput(input) {
    if (!input) return false;
    var $inp = $(input);
    return $inp.hasClass('select-month-input') ||
           $inp.hasClass('clean-month-input') ||
           $inp.attr('data-picker') === 'month' ||
           $inp.attr('name') === 'payroll_period' ||
           $inp.attr('id') === 'payrollPeriod';
  }

  function parseDate(str) {
    if (!str || typeof str !== 'string') return null;
    var parts = str.trim().split('-');
    if (parts.length === 3) {
      var y = parseInt(parts[0], 10);
      var m = parseInt(parts[1], 10) - 1;
      var d = parseInt(parts[2], 10);
      if (!isNaN(y) && !isNaN(m) && !isNaN(d)) {
        return new Date(y, m, d);
      }
    } else if (parts.length === 2) {
      var y2 = parseInt(parts[0], 10);
      var m2 = parseInt(parts[1], 10) - 1;
      if (!isNaN(y2) && !isNaN(m2)) {
        return new Date(y2, m2, 1);
      }
    }
    return null;
  }

  function createPopover() {
    if ($popover) return;

    var html = [
      '<div class="custom-calendar-popover" id="customCalendarPopover" style="display: none;">',
      '  <div class="cal-header">',
      '    <button type="button" class="cal-nav-btn cal-prev" title="Previous Month">',
      '      <i class="mdi mdi-chevron-left"></i>',
      '    </button>',
      '    <div class="cal-title-wrap" role="button" title="Click to change month/year">',
      '      <span class="cal-month-title"></span>',
      '      <span class="cal-year-title"></span>',
      '      <i class="mdi mdi-chevron-down cal-title-caret"></i>',
      '    </div>',
      '    <button type="button" class="cal-nav-btn cal-next" title="Next Month">',
      '      <i class="mdi mdi-chevron-right"></i>',
      '    </button>',
      '  </div>',
      '  <div class="cal-month-grid" style="display: none;"></div>',
      '  <div class="cal-calendar-view">',
      '    <div class="cal-weekdays">',
      '      <span>Su</span><span>Mo</span><span>Tu</span><span>We</span><span>Th</span><span>Fr</span><span>Sa</span>',
      '    </div>',
      '    <div class="cal-days-grid"></div>',
      '  </div>',
      '  <div class="cal-footer">',
      '    <button type="button" class="cal-footer-btn cal-btn-clear">Clear</button>',
      '    <button type="button" class="cal-footer-btn cal-btn-today">Today</button>',
      '  </div>',
      '</div>'
    ].join('');

    $popover = $(html).appendTo('body');

    // Navigation Events
    $popover.on('click', '.cal-prev', function (e) {
      e.stopPropagation();
      if (isMonthInput(activeInput) || isMonthPickerMode) {
        viewYear--;
        renderMonthGrid();
      } else {
        viewMonth--;
        if (viewMonth < 0) {
          viewMonth = 11;
          viewYear--;
        }
        renderDays();
      }
    });

    $popover.on('click', '.cal-next', function (e) {
      e.stopPropagation();
      if (isMonthInput(activeInput) || isMonthPickerMode) {
        viewYear++;
        renderMonthGrid();
      } else {
        viewMonth++;
        if (viewMonth > 11) {
          viewMonth = 0;
          viewYear++;
        }
        renderDays();
      }
    });

    // Toggle Month/Year fast selector
    $popover.on('click', '.cal-title-wrap', function (e) {
      e.stopPropagation();
      if (!isMonthInput(activeInput)) {
        isMonthPickerMode = !isMonthPickerMode;
        if (isMonthPickerMode) {
          renderMonthGrid();
        } else {
          renderDays();
        }
      }
    });

    // Select Month from fast selector or month picker
    $popover.on('click', '.cal-month-cell', function (e) {
      e.stopPropagation();
      var m = parseInt($(this).data('month'), 10);
      viewMonth = m;
      if (isMonthInput(activeInput)) {
        var ym = viewYear + '-' + pad(m + 1);
        selectDate(ym);
      } else {
        isMonthPickerMode = false;
        renderDays();
      }
    });

    // Click Day
    $popover.on('click', '.cal-day', function (e) {
      e.stopPropagation();
      var dateStr = $(this).data('date');
      if (dateStr && activeInput) {
        selectDate(dateStr);
      }
    });

    // Clear Button
    $popover.on('click', '.cal-btn-clear', function (e) {
      e.stopPropagation();
      if (activeInput) {
        $(activeInput).val('').trigger('change');
      }
      hidePopover();
    });

    // Today / This Month Button
    $popover.on('click', '.cal-btn-today', function (e) {
      e.stopPropagation();
      var today = new Date();
      if (isMonthInput(activeInput)) {
        var ym = today.getFullYear() + '-' + pad(today.getMonth() + 1);
        selectDate(ym);
      } else {
        var todayStr = formatDate(today.getFullYear(), today.getMonth(), today.getDate());
        if (activeInput) {
          selectDate(todayStr);
        }
      }
    });

    // Prevent popover clicks from bubbling to document (closing it)
    $popover.on('click mousedown', function (e) {
      e.stopPropagation();
    });
  }

  function selectDate(dateStr) {
    if (!activeInput) return;
    $(activeInput).val(dateStr);
    try {
      activeInput.value = dateStr;
    } catch (e) {}
    $(activeInput).trigger('change').trigger('input');
    if (typeof Event === 'function') {
      activeInput.dispatchEvent(new Event('change', { bubbles: true }));
      activeInput.dispatchEvent(new Event('input', { bubbles: true }));
    }
    hidePopover();
  }

  function renderDays() {
    isMonthPickerMode = false;
    $popover.removeClass('is-month-picker');
    $popover.find('.cal-calendar-view').show();
    $popover.find('.cal-month-grid').hide();
    $popover.find('.cal-month-title').text(months[viewMonth]);
    $popover.find('.cal-year-title').text(viewYear);
    $popover.find('.cal-btn-today').text('Today');
    $popover.find('.cal-title-caret').show();

    var $grid = $popover.find('.cal-days-grid').empty();
    var firstDayOfWeek = new Date(viewYear, viewMonth, 1).getDay(); // 0 is Sunday
    var daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
    var daysInPrevMonth = new Date(viewYear, viewMonth, 0).getDate();

    var selectedDate = activeInput ? parseDate($(activeInput).val()) : null;
    var today = new Date();
    var todayStr = formatDate(today.getFullYear(), today.getMonth(), today.getDate());

    var minDate = activeInput ? $(activeInput).data('min') : null;
    var maxDate = activeInput ? $(activeInput).data('max') : null;

    // Previous month filler days
    for (var i = firstDayOfWeek - 1; i >= 0; i--) {
      var prevDayNum = daysInPrevMonth - i;
      var prevMonthNum = viewMonth - 1;
      var prevYearNum = viewYear;
      if (prevMonthNum < 0) {
        prevMonthNum = 11;
        prevYearNum--;
      }
      var pDateStr = formatDate(prevYearNum, prevMonthNum, prevDayNum);
      $grid.append(
        $('<button type="button" class="cal-day cal-day-overflow">')
          .text(prevDayNum)
          .attr('data-date', pDateStr)
      );
    }

    // Current month days
    for (var d = 1; d <= daysInMonth; d++) {
      var dStr = formatDate(viewYear, viewMonth, d);
      var $dayBtn = $('<button type="button" class="cal-day">')
        .text(d)
        .attr('data-date', dStr);

      if (dStr === todayStr) {
        $dayBtn.addClass('cal-day-today');
      }

      if (selectedDate &&
          selectedDate.getFullYear() === viewYear &&
          selectedDate.getMonth() === viewMonth &&
          selectedDate.getDate() === d) {
        $dayBtn.addClass('cal-day-selected');
      }

      if ((minDate && dStr < minDate) || (maxDate && dStr > maxDate)) {
        $dayBtn.addClass('cal-day-disabled').prop('disabled', true);
      }

      $grid.append($dayBtn);
    }

    // Next month filler days (fill remainder of 42-cell or 35-cell grid)
    var totalCells = firstDayOfWeek + daysInMonth;
    var remainingCells = totalCells % 7 === 0 ? 0 : 7 - (totalCells % 7);
    for (var n = 1; n <= remainingCells; n++) {
      var nextMonthNum = viewMonth + 1;
      var nextYearNum = viewYear;
      if (nextMonthNum > 11) {
        nextMonthNum = 0;
        nextYearNum++;
      }
      var nDateStr = formatDate(nextYearNum, nextMonthNum, n);
      $grid.append(
        $('<button type="button" class="cal-day cal-day-overflow">')
          .text(n)
          .attr('data-date', nDateStr)
      );
    }
  }

  function renderMonthGrid() {
    $popover.find('.cal-calendar-view').hide();
    var $mGrid = $popover.find('.cal-month-grid').show().empty();

    if (isMonthInput(activeInput)) {
      $popover.find('.cal-month-title').text('Period:');
      $popover.find('.cal-year-title').text(viewYear);
      $popover.find('.cal-btn-today').text('This Month');
      $popover.find('.cal-title-caret').hide();
    } else {
      $popover.find('.cal-month-title').text('Select Month');
      $popover.find('.cal-year-title').text(viewYear);
      $popover.find('.cal-btn-today').text('Today');
      $popover.find('.cal-title-caret').show();
    }

    var selectedYm = null;
    if (activeInput && isMonthInput(activeInput)) {
      var curVal = $(activeInput).val();
      if (curVal && curVal.indexOf('-') !== -1) {
        selectedYm = curVal.trim();
      }
    }

    for (var m = 0; m < 12; m++) {
      var cellYm = viewYear + '-' + pad(m + 1);
      var $mBtn = $('<button type="button" class="cal-month-cell">')
        .text(shortMonths[m])
        .attr('data-month', m)
        .attr('data-period', cellYm);

      if (isMonthInput(activeInput)) {
        if (selectedYm === cellYm) {
          $mBtn.addClass('cal-month-selected');
        }
      } else if (m === viewMonth) {
        $mBtn.addClass('cal-month-selected');
      }
      $mGrid.append($mBtn);
    }
  }

  function positionPopover() {
    if (!$popover || !$popover.is(':visible') || !activeInput) return;

    var $container = $(activeInput).closest('.component-select-date, .component-select-month, .input-group');
    if (!$container.length) $container = $(activeInput);

    var domEl = $container[0];
    if (!domEl) {
      hidePopover();
      return;
    }

    var rect = domEl.getBoundingClientRect();

    // If container is invisible or has 0 dimensions, hide
    if (rect.width === 0 || rect.height === 0 || (rect.top === 0 && rect.bottom === 0 && rect.left === 0)) {
      hidePopover();
      return;
    }

    var popoverWidth = 300;
    var popoverHeight = isMonthInput(activeInput) ? 260 : 330;
    var viewportWidth = window.innerWidth || document.documentElement.clientWidth;
    var viewportHeight = window.innerHeight || document.documentElement.clientHeight;

    // Default: directly below input
    var top = rect.bottom + 6;
    var left = rect.left;

    // Right viewport collision check
    if (left + popoverWidth > viewportWidth - 16) {
      left = Math.max(16, viewportWidth - popoverWidth - 16);
    }
    if (left < 16) {
      left = 16;
    }

    // Bottom viewport collision check: flip upward if space allows
    if (top + popoverHeight > viewportHeight - 16) {
      if (rect.top - popoverHeight - 6 >= 16) {
        top = rect.top - popoverHeight - 6;
      } else {
        top = Math.max(16, viewportHeight - popoverHeight - 16);
      }
    }

    $popover.css({
      top: Math.round(top) + 'px',
      left: Math.round(left) + 'px'
    });
  }

  function showPopover(input) {
    if (!input) return;

    var $container = $(input).closest('.component-select-date, .component-select-month, .input-group');
    if (!$container.length) $container = $(input);

    var domEl = $container[0];
    if (!domEl) return;

    var rect = domEl.getBoundingClientRect();
    // NEVER show popover if target element is hidden, detached, or has 0 dimensions
    if (rect.width === 0 || rect.height === 0 || (rect.top === 0 && rect.bottom === 0 && rect.left === 0)) {
      return;
    }

    // Hide time popover if open
    if (window.PayrollTimePicker && typeof window.PayrollTimePicker.hide === 'function') {
      window.PayrollTimePicker.hide();
    }

    createPopover();
    activeInput = input;

    var val = $(input).val();
    var d = parseDate(val) || new Date();
    viewYear = d.getFullYear();
    viewMonth = d.getMonth();

    if (isMonthInput(input)) {
      $popover.addClass('is-month-picker');
      renderMonthGrid();
    } else {
      $popover.removeClass('is-month-picker');
      renderDays();
    }

    $popover.addClass('is-open').show();
    positionPopover();
    $container.addClass('picker-active');
  }

  function hidePopover() {
    if ($popover && $popover.is(':visible')) {
      $popover.removeClass('is-open is-month-picker').hide();
    }
    $('.component-select-date, .component-select-month, .input-group').removeClass('picker-active');
    activeInput = null;
    isMonthPickerMode = false;
  }

  function enhanceDateInputs(context) {
    var $root = context ? $(context) : $(document);

    // Enhance date inputs
    $root.find('input[type="date"]').each(function () {
      var $el = $(this);
      $el.attr('type', 'text');
      $el.attr('autocomplete', 'off');
      if (!$el.attr('placeholder')) {
        $el.attr('placeholder', 'YYYY-MM-DD');
      }
      $el.addClass('select-date-input');

      // If not already inside an input-group, wrap with an input group and trigger
      if (!$el.closest('.input-group, .component-select-date').length) {
        $el.wrap('<div class="input-group component-select-date date-picker-group"></div>');
        $el.after(
          '<span class="input-group-text select-date-trigger text-muted" role="button" tabindex="0" title="Open calendar">' +
            '<i class="mdi mdi-calendar"></i>' +
          '</span>'
        );
      } else if (!$el.siblings('.select-date-trigger').length) {
        $el.parent().addClass('component-select-date');
        $el.after(
          '<span class="input-group-text select-date-trigger text-muted" role="button" tabindex="0" title="Open calendar">' +
            '<i class="mdi mdi-calendar"></i>' +
          '</span>'
        );
      }
    });

    // Enhance month inputs
    $root.find('input[type="month"], input.clean-month-input, input[data-picker="month"]').each(function () {
      var $el = $(this);
      $el.attr('type', 'text');
      $el.attr('autocomplete', 'off');
      if (!$el.attr('placeholder')) {
        $el.attr('placeholder', 'YYYY-MM');
      }
      $el.addClass('select-month-input');

      if (!$el.closest('.input-group, .component-select-month').length) {
        $el.wrap('<div class="input-group component-select-month month-picker-group"></div>');
        $el.after(
          '<span class="input-group-text select-month-trigger text-muted" role="button" tabindex="0" title="Select month/period">' +
            '<i class="mdi mdi-calendar-month"></i>' +
          '</span>'
        );
      } else if (!$el.siblings('.select-month-trigger').length) {
        $el.parent().addClass('component-select-month');
        $el.after(
          '<span class="input-group-text select-month-trigger text-muted" role="button" tabindex="0" title="Select month/period">' +
            '<i class="mdi mdi-calendar-month"></i>' +
          '</span>'
        );
      }
    });
  }

  // Document Click & Keydown listeners
  $(document).on('click', function (e) {
    if ($popover && $popover.is(':visible')) {
      if (!$(e.target).closest('.component-select-date, .component-select-month, .select-date-input, .select-date-trigger, .select-month-input, .select-month-trigger, .custom-calendar-popover, .component-select-date-wrap, .component-select-month-wrap').length) {
        hidePopover();
      }
    }
  });

  $(document).on('keydown', function (e) {
    if (e.key === 'Escape') {
      hidePopover();
    }
  });

  // Reposition on window resize or scroll
  $(window).on('resize', function () {
    if ($popover && $popover.is(':visible')) {
      positionPopover();
    }
  });

  document.addEventListener('scroll', function (e) {
    if ($popover && $popover.is(':visible')) {
      if (!e.target || !e.target.closest || !e.target.closest('.custom-calendar-popover')) {
        positionPopover();
      }
    }
  }, true);

  // Attach to select-date-input (click only)
  $(document).on('click', '.select-date-input', function (e) {
    e.preventDefault();
    if (activeInput === this && $popover && $popover.is(':visible')) {
      hidePopover();
    } else {
      showPopover(this);
    }
  });

  // Attach to calendar trigger icon
  $(document).on('click', '.select-date-trigger', function (e) {
    e.preventDefault();
    e.stopPropagation();
    $(this).blur();
    var input = $(this).siblings('.select-date-input')[0] || $(this).closest('.input-group').find('.select-date-input')[0];
    if (input) {
      if (activeInput === input && $popover && $popover.is(':visible')) {
        hidePopover();
      } else {
        showPopover(input);
      }
    }
  });

  // Allow clicking on date label
  $(document).on('click', '.component-select-date-wrap > label', function () {
    var input = $(this).siblings('.component-select-date').find('.select-date-input')[0];
    if (input) {
      showPopover(input);
    }
  });

  // Support keyboard trigger on date input (Enter, Space, ArrowDown)
  $(document).on('keydown', '.select-date-input, .select-date-trigger', function (e) {
    if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
      var input = $(this).hasClass('select-date-input') ? this : $(this).siblings('.select-date-input')[0];
      if (input && (!$popover || !$popover.is(':visible'))) {
        e.preventDefault();
        showPopover(input);
      }
    }
  });

  // Attach to select-month-input (click only)
  $(document).on('click', '.select-month-input', function (e) {
    e.preventDefault();
    if (activeInput === this && $popover && $popover.is(':visible')) {
      hidePopover();
    } else {
      showPopover(this);
    }
  });

  // Attach to month trigger icon
  $(document).on('click', '.select-month-trigger', function (e) {
    e.preventDefault();
    e.stopPropagation();
    var input = $(this).siblings('.select-month-input')[0] || $(this).closest('.input-group').find('.select-month-input')[0];
    if (input) {
      if (activeInput === input && $popover && $popover.is(':visible')) {
        hidePopover();
      } else {
        showPopover(input);
      }
    }
  });

  // Allow clicking on month label
  $(document).on('click', '.component-select-month-wrap > label', function () {
    var input = $(this).siblings('.component-select-month').find('.select-month-input')[0];
    if (input) {
      showPopover(input);
    }
  });

  // Support keyboard trigger on month input
  $(document).on('keydown', '.select-month-input, .select-month-trigger', function (e) {
    if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
      var input = $(this).hasClass('select-month-input') ? this : $(this).siblings('.select-month-input')[0];
      if (input && (!$popover || !$popover.is(':visible'))) {
        e.preventDefault();
        showPopover(input);
      }
    }
  });

  // Close immediately when any Bootstrap modal starts to hide or is hidden
  $(document).on('hide.bs.modal hidden.bs.modal', function () {
    hidePopover();
  });

  // Initialize and observe for dynamically added elements
  $(function () {
    enhanceDateInputs();

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
          enhanceDateInputs();
        }
      });
      if (document.body) {
        observer.observe(document.body, { childList: true, subtree: true });
      }
    }
  });

  // Export to global scope
  window.PayrollDatePicker = {
    show: showPopover,
    hide: hidePopover,
    enhance: enhanceDateInputs
  };

})(jQuery);


