/**
 * Payroll MGM - Global Application JavaScript (app-main.js)
 * Manages UI interactions, Select2 dropdowns, sidebar drawer controls, and animations.
 */

(function ($) {
  'use strict';

  $(document).ready(function () {
    // 1. Initialize Animated Counters
    if (window.initCounterAnimations) {
      window.initCounterAnimations();
    }

    // 2. Initialize Select2 with Modal & Bounds Handling
    if ($.fn.select2) {
      function initSelect2(container) {
        var $scope = container ? $(container) : $(document);
        $scope.find('select:not(.no-select2)').each(function () {
          var $select = $(this);
          var $modal = $select.closest('.modal');
          var options = {
            width: '100%',
            minimumResultsForSearch: 10
          };
          if ($modal.length) {
            options.dropdownParent = $modal;
          }
          $select.select2(options);
        });
      }

      initSelect2();

      $(document).on('shown.bs.modal', '.modal', function () {
        var $modal = $(this);
        $modal.find('select').each(function () {
          if ($(this).hasClass('select2-hidden-accessible')) {
            $(this).select2('destroy');
          }
        });
        initSelect2($modal);
      });
    }

    // 3. Responsive Sidebar Controller
    var $sidebar = $('#sidebar');
    var $backdrop = $('#sidebarBackdrop');
    var $body = $('body');

    // Default to fully expanded sidebar on desktop screens
    if ($(window).width() >= 992) {
      $body.removeClass('sidebar-icon-only');
    }

    // Desktop minimize / icon-only toggle
    $('[data-bs-toggle="minimize"]').off('click').on('click', function (e) {
      e.preventDefault();
      $body.toggleClass('sidebar-icon-only');
      if ($body.hasClass('sidebar-icon-only')) {
        $('.sidebar .collapse.show').removeClass('show');
        $('.sidebar [data-bs-toggle="collapse"]').attr('aria-expanded', 'false');
      }
    });

    function openSidebar() {
      $sidebar.addClass('active');
      $backdrop.addClass('active');
      $body.addClass('sidebar-open');
    }

    function closeSidebar() {
      $sidebar.removeClass('active');
      $backdrop.removeClass('active');
      $body.removeClass('sidebar-open');
    }

    // Mobile offcanvas drawer toggler
    $('[data-bs-toggle="offcanvas"]').off('click').on('click', function (e) {
      e.preventDefault();
      if ($sidebar.hasClass('active')) {
        closeSidebar();
      } else {
        openSidebar();
      }
    });

    // Dismiss on backdrop click
    $backdrop.on('click', function () {
      closeSidebar();
    });

    // Dismiss on mobile header close button click
    $(document).on('click', '.btn-close-sidebar', function (e) {
      e.preventDefault();
      closeSidebar();
    });

    // Dismiss on Escape key
    $(document).on('keydown', function (e) {
      if (e.key === 'Escape' && $sidebar.hasClass('active')) {
        closeSidebar();
      }
    });

    // Auto-close mobile drawer when non-collapsing nav link is clicked
    $('.sidebar .nav-link:not([data-bs-toggle="collapse"])').on('click', function () {
      if ($(window).width() < 992) {
        closeSidebar();
      }
    });

    // 4. Reusable Select Date Component Interactions
    $(document).on('click', '.component-select-date .select-date-trigger', function (e) {
      e.preventDefault();
      var $input = $(this).siblings('input[type="date"]');
      if ($input.length && $input[0]) {
        if (typeof $input[0].showPicker === 'function') {
          try {
            $input[0].showPicker();
          } catch (err) {
            $input[0].focus();
          }
        } else {
          $input[0].focus();
        }
      }
    });

    $(document).on('keydown', '.component-select-date .select-date-trigger', function (e) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        var $input = $(this).siblings('input[type="date"]');
        if ($input.length && $input[0]) {
          if (typeof $input[0].showPicker === 'function') {
            try {
              $input[0].showPicker();
            } catch (err) {
              $input[0].focus();
            }
          } else {
            $input[0].focus();
          }
        }
      }
    });

    // 5. Ultrawide Canvas View Mode Controller (for 24", 27", 34", 39", 49" Monitors)
    var $ultrawideBtn = $('#ultrawideToggleBtn');
    var savedUltrawideMode = localStorage.getItem('payroll_ultrawide_mode');
    
    if (savedUltrawideMode === 'full') {
      $('body').addClass('layout-ultrawide-full');
      $ultrawideBtn.find('i').removeClass('mdi-arrow-expand-horizontal').addClass('mdi-arrow-collapse-horizontal');
      $ultrawideBtn.find('span').text('Focused');
    }

    $ultrawideBtn.on('click', function (e) {
      e.preventDefault();
      $('body').toggleClass('layout-ultrawide-full');
      var isFull = $('body').hasClass('layout-ultrawide-full');
      localStorage.setItem('payroll_ultrawide_mode', isFull ? 'full' : 'focused');
      
      $ultrawideBtn.find('i')
        .toggleClass('mdi-arrow-expand-horizontal', !isFull)
        .toggleClass('mdi-arrow-collapse-horizontal', isFull);
      $ultrawideBtn.find('span').text(isFull ? 'Focused' : 'Full Width');
    });

    // 6. Mobile Responsive Data Table: Automatic Card View Label Mapping
    function initMobileDataTableLabels() {
      // Remove any previously injected toolbars
      $('.table-mobile-toolbar').remove();

      $('.table-responsive').each(function () {
        var $wrapper = $(this);
        var $table = $wrapper.find('table.table');
        if (!$table.length) return;

        // Populate data-label attributes on each td for mobile card view
        var headers = [];
        $table.find('thead th').each(function () {
          var txt = $(this).text().trim();
          headers.push(txt.toLowerCase() === 'actions' ? 'Actions' : txt);
        });

        $table.find('tbody tr').each(function () {
          var $row = $(this);
          if ($row.find('td[colspan]').length) return;

          $row.find('td').each(function (idx) {
            if (headers[idx] && !$(this).attr('data-label')) {
              $(this).attr('data-label', headers[idx]);
            }
          });
        });
      });
    }

    initMobileDataTableLabels();
    $(document).ajaxComplete(function () {
      initMobileDataTableLabels();
    });
  });
})(jQuery);

