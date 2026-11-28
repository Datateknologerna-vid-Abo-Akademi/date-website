// Header submenus (core/header_nav_items.html) open through CSS: hover, keyboard
// focus, or always in the collapsed mobile navbar. This keeps each toggle's
// aria-expanded true to what is on screen, and lets a parent without a url open
// its submenu on click or tap, where the CSS alone has nothing to react to.
function initNavSubmenus() {
    const submenus = [];

    document.querySelectorAll('[data-nav-submenu]').forEach((item) => {
        const toggle = item.querySelector('[data-nav-submenu-toggle]');
        const list = toggle && document.getElementById(toggle.getAttribute('aria-controls'));
        if (!list) return;

        // :focus-within and :hover settle after the event that changes them.
        const sync = () => requestAnimationFrame(() => {
            // data-open only bridges a click or tap. Drop it once pointer and focus
            // have both left: a dropdown opened by CSS hover never fires
            // hide.bs.dropdown, so the submenu would otherwise stay open for good.
            if (!item.matches(':hover, :focus-within')) item.removeAttribute('data-open');
            toggle.setAttribute('aria-expanded', String(getComputedStyle(list).display !== 'none'));
        });
        submenus.push({ item, sync });

        ['mouseenter', 'mouseleave', 'focusin', 'focusout'].forEach((type) => item.addEventListener(type, sync));

        if (toggle.hasAttribute('data-nav-submenu-button')) {
            toggle.addEventListener('click', (event) => {
                // Bootstrap closes the whole dropdown on any click that reaches the document.
                event.stopPropagation();
                item.toggleAttribute('data-open');
                sync();
            });
        }
        sync();
    });

    if (!submenus.length) return;

    const syncAll = () => submenus.forEach(({ sync }) => sync());
    document.addEventListener('hide.bs.dropdown', () => {
        submenus.forEach(({ item }) => item.removeAttribute('data-open'));
        syncAll();
    });
    window.matchMedia('(max-width: 991.98px)').addEventListener('change', syncAll);
}

initNavSubmenus();
