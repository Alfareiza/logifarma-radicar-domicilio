$(document).ready(function () {
    var KEY = 'sidebar-collapsed';
    var $navbar = $('.pcoded-navbar');

    if (localStorage.getItem(KEY) === '1') {
        $navbar.addClass('navbar-collapsed');
    } else if (localStorage.getItem(KEY) === '0') {
        $navbar.removeClass('navbar-collapsed');
    }

    $('#mobile-collapse').on('click.persist', function () {
        requestAnimationFrame(function () {
            localStorage.setItem(KEY, $navbar.hasClass('navbar-collapsed') ? '1' : '0');
        });
    });
});
