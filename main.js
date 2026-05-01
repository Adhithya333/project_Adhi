(function () {
    'use strict';

    var NAV_BREAKPOINT = 992;

    function initMessages() {
        document.querySelectorAll('.alert').forEach(function (message) {
            setTimeout(function () {
                message.style.transition = 'opacity 0.5s';
                message.style.opacity = '0';
                setTimeout(function () {
                    message.remove();
                }, 500);
            }, 5000);
        });
    }

    function initAlertClose() {
        document.querySelectorAll('.alert-close').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var alert = btn.closest('.alert');
                if (alert) {
                    alert.style.transition = 'opacity 0.25s';
                    alert.style.opacity = '0';
                    setTimeout(function () {
                        alert.remove();
                    }, 250);
                }
            });
        });
    }

    function initMobileNav() {
        var toggle = document.querySelector('.mobile-menu-toggle');
        var menu = document.getElementById('main-nav');
        var overlay = document.querySelector('.nav-overlay');
        if (!toggle || !menu) {
            return;
        }

        function closeNav() {
            toggle.setAttribute('aria-expanded', 'false');
            menu.classList.remove('is-open');
            if (overlay) {
                overlay.classList.remove('is-open');
            }
            document.body.classList.remove('nav-open');
        }

        function openNav() {
            toggle.setAttribute('aria-expanded', 'true');
            menu.classList.add('is-open');
            if (overlay) {
                overlay.classList.add('is-open');
            }
            document.body.classList.add('nav-open');
        }

        function isMobileNav() {
            return window.innerWidth <= NAV_BREAKPOINT;
        }

        toggle.addEventListener('click', function () {
            if (menu.classList.contains('is-open')) {
                closeNav();
            } else {
                openNav();
            }
        });

        if (overlay) {
            overlay.addEventListener('click', closeNav);
        }

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && menu.classList.contains('is-open')) {
                closeNav();
            }
        });

        window.addEventListener('resize', function () {
            if (!isMobileNav()) {
                closeNav();
            }
        });

        menu.querySelectorAll('a.nav-link[href]').forEach(function (link) {
            link.addEventListener('click', function () {
                if (isMobileNav()) {
                    closeNav();
                }
            });
        });

        var logoutForm = menu.querySelector('.nav-logout-form');
        if (logoutForm) {
            logoutForm.addEventListener('submit', function () {
                if (isMobileNav()) {
                    closeNav();
                }
            });
        }
    }

    function initFormBusyState() {
        document.querySelectorAll('form').forEach(function (form) {
            if (form.classList.contains('form--no-busy')) {
                return;
            }
            form.addEventListener('submit', function () {
                var submitButton = form.querySelector('button[type="submit"]');
                if (submitButton && !submitButton.disabled) {
                    submitButton.disabled = true;
                    submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
                }
            });
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        initMessages();
        initAlertClose();
        initMobileNav();
        initFormBusyState();
    });
})();
