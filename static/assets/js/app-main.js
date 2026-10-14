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
  });
})(jQuery);

