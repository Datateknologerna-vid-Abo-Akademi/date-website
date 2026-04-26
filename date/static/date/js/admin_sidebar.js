(function () {
    const KEY = 'admin_sidebar_width';
    const MIN = 180;
    const MAX = 520;

    function load() {
        try { return parseInt(localStorage.getItem(KEY)) || null; }
        catch { return null; }
    }

    function save(w) {
        try { localStorage.setItem(KEY, String(w)); } catch {}
    }

    function applyWidth(w) {
        const sidebar = document.getElementById('nav-sidebar');
        if (!sidebar) return;
        // parentElement.parentElement is the flex layout spacer (w-[288px] xl:relative)
        const layoutHolder = sidebar.parentElement?.parentElement;
        sidebar.style.width = w + 'px';
        if (layoutHolder) layoutHolder.style.width = w + 'px';
        save(w);
    }

    function autoFit() {
        const sidebar = document.getElementById('nav-sidebar');
        if (!sidebar) return;
        sidebar.style.width = 'max-content';
        const fitted = Math.min(MAX, Math.max(MIN, sidebar.offsetWidth));
        applyWidth(fitted);
    }

    function init() {
        const sidebar = document.getElementById('nav-sidebar');
        if (!sidebar) return;

        const saved = load();
        if (saved) {
            applyWidth(saved);
        } else {
            autoFit();
        }

        const handle = document.createElement('div');
        handle.id = 'sidebar-resize-handle';
        sidebar.appendChild(handle);

        handle.addEventListener('mousedown', e => {
            e.preventDefault();
            const startX = e.clientX;
            const startW = sidebar.offsetWidth;
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';

            function onMove(e) {
                applyWidth(Math.min(MAX, Math.max(MIN, startW + (e.clientX - startX))));
            }
            function onUp() {
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
                document.removeEventListener('mousemove', onMove);
                document.removeEventListener('mouseup', onUp);
            }
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        });

        // Double-click to re-fit to content
        handle.addEventListener('dblclick', () => {
            localStorage.removeItem(KEY);
            autoFit();
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();

// Keep Unfold's filter sheet open when filter actions reload the changelist.
(function () {
    const KEY = 'admin_reopen_filter_sheet';
    const hasOwn = (object, key) => Object.prototype.hasOwnProperty.call(object, key);

    function markFilterSheetForReopen() {
        try { sessionStorage.setItem(KEY, '1'); } catch {}
    }

    function rememberFilterSheet(event) {
        const link = event.target.closest('#changelist-filter a[href]');
        if (!link) return;

        markFilterSheetForReopen();
    }

    function rememberFilterForm(event) {
        if (event.target && event.target.id === 'filter-form') {
            markFilterSheetForReopen();
        }
    }

    function reopenFilterSheet() {
        let shouldReopen = false;
        try {
            shouldReopen = sessionStorage.getItem(KEY) === '1';
            sessionStorage.removeItem(KEY);
        } catch {}

        if (!shouldReopen || !document.body.classList.contains('change-list')) return;

        const contentMain = document.getElementById('content-main');
        if (!contentMain) return;

        function openWithAlpine(attempt = 0) {
            if (window.Alpine && typeof window.Alpine.$data === 'function') {
                const data = window.Alpine.$data(contentMain);
                if (data && hasOwn(data, 'filterOpen')) {
                    data.filterOpen = true;
                    return true;
                }
            }

            // _x_dataStack is an Alpine.js internal — coupling risk on upgrades.
            const dataStack = contentMain._x_dataStack;
            if (dataStack && dataStack[0] && hasOwn(dataStack[0], 'filterOpen')) {
                dataStack[0].filterOpen = true;
                return true;
            }

            if (attempt < 10) {
                window.setTimeout(() => openWithAlpine(attempt + 1), 50);
            }

            return false;
        }

        openWithAlpine();
    }

    document.addEventListener('click', rememberFilterSheet);
    document.addEventListener('submit', rememberFilterForm);

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', reopenFilterSheet);
    } else {
        reopenFilterSheet();
    }
})();

// Modeltranslation master language switcher for Unfold admin.
// Unfold has no <h1> in #content so modeltranslation never inserts its own select.
// Instead we read the jQuery UI tab groups directly and build our own pill switcher.
(function () {
    const SWITCHER_CLASS = 'mt-lang-switcher';
    const BUTTON_CLASS = 'mt-lang-btn';

    function getTabLanguage(link) {
        return (link.getAttribute('lang') || link.textContent || '')
            .trim()
            .replace('_', '-')
            .toLowerCase();
    }

    function getTabGroups() {
        return Array.from(document.querySelectorAll('#content-main .ui-tabs'))
            .filter(group => group.querySelector('.ui-tabs-nav a[href^="#tab_"]'));
    }

    function getLanguages() {
        const languages = [];
        getTabGroups().forEach(function (group) {
            group.querySelectorAll('.ui-tabs-nav a[href^="#tab_"]').forEach(function (link) {
                const language = getTabLanguage(link);
                if (language && !languages.includes(language)) {
                    languages.push(language);
                }
            });
        });
        return languages;
    }

    function getActiveLanguage() {
        const activeLink = document.querySelector(
            '#content-main .ui-tabs-nav .ui-tabs-active a[href^="#tab_"], ' +
            '#content-main .ui-tabs-nav .ui-tabs-selected a[href^="#tab_"]'
        );
        return activeLink ? getTabLanguage(activeLink) : '';
    }

    function setButtonState(language) {
        document.querySelectorAll('.' + BUTTON_CLASS).forEach(function (button) {
            const active = button.dataset.language === language;
            button.classList.toggle('active', active);
            button.setAttribute('aria-pressed', active ? 'true' : 'false');
        });
    }

    function activateGroupLanguage(group, language) {
        const links = Array.from(group.querySelectorAll('.ui-tabs-nav a[href^="#tab_"]'));
        const index = links.findIndex(link => getTabLanguage(link) === language);
        if (index < 0) return;

        const jq = window.django && window.django.jQuery ? window.django.jQuery : window.jQuery;
        if (jq && typeof jq.fn.tabs === 'function') {
            jq(group).tabs('option', 'active', index);
        } else {
            links[index].click();
        }
    }

    function activateLanguage(language) {
        getTabGroups().forEach(group => activateGroupLanguage(group, language));
        setButtonState(language);
    }

    function initLangSwitcher() {
        if (!document.body.classList.contains('change-form')) return;

        function enhance() {
            if (document.querySelector('.' + SWITCHER_CLASS)) return true;

            const languages = getLanguages();
            if (!languages.length) return false;
            if (languages.length < 2) return true; // nothing to switch

            const activeLanguage = getActiveLanguage() || languages[0];

            const container = document.createElement('div');
            container.className = SWITCHER_CLASS;
            container.setAttribute('aria-label', 'Translation language');

            languages.forEach(function (language) {
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.textContent = language.toUpperCase();
                btn.dataset.language = language;
                btn.className = BUTTON_CLASS + (language === activeLanguage ? ' active' : '');
                btn.setAttribute('aria-pressed', language === activeLanguage ? 'true' : 'false');
                btn.addEventListener('click', () => activateLanguage(language));

                container.appendChild(btn);
            });

            const anchor = document.querySelector('#content-main');
            if (anchor) anchor.insertAdjacentElement('afterbegin', container);
            return true;
        }

        document.addEventListener('click', function (event) {
            if (!event.target.closest('#content-main .ui-tabs-nav a[href^="#tab_"]')) return;
            window.setTimeout(function () {
                const activeLanguage = getActiveLanguage();
                if (activeLanguage) setButtonState(activeLanguage);
            }, 0);
        });

        // modeltranslation runs in jQuery ready which fires at DOMContentLoaded.
        // Use MutationObserver to detect when jQuery UI tabs are initialised.
        if (!enhance()) {
            const observer = new MutationObserver(function (_, obs) {
                if (getLanguages().length) {
                    obs.disconnect();
                    enhance();
                }
            });
            observer.observe(document.getElementById('content-main') || document.body,
                { childList: true, subtree: true });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initLangSwitcher);
    } else {
        initLangSwitcher();
    }
})();
