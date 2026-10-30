// Unfold hides the document with x-cloak until Alpine boots. If a script is
// blocked or delayed, reveal the page after a short grace period instead of
// leaving an indefinitely blank admin page.
window.setTimeout(function () {
    document.documentElement.removeAttribute('x-cloak');
}, 2500);

// Unfold binds the inline "add row" control once, at window load. Its paginated
// inline replaces the whole table, including that control, on every page
// change, so the replacement has no click listener. Rebind it after each swap.
document.addEventListener('htmx:afterSettle', function (event) {
    if (typeof window.addInlineTemplateHandler !== 'function') return;
    if (!event.target || !event.target.querySelectorAll) return;

    event.target.querySelectorAll('.add-row').forEach(function (button) {
        button.removeEventListener('click', window.addInlineTemplateHandler);
        button.addEventListener('click', window.addInlineTemplateHandler);
    });
});

// Unfold's collapsible inline blocks start collapsed, including a row added with
// "Add another", so a new block would look like nothing happened. Open the new
// block once Alpine has attached its data, and give any hidden select2 widget a
// width again, since it measured zero while the block was closed.
(function () {
    const hasOwn = (object, key) => Object.prototype.hasOwnProperty.call(object, key);

    function alpineData(element) {
        // Alpine.$data can return an empty proxy for a freshly cloned row; the
        // internal stack still holds the component that owns openRow.
        const candidates = [];
        if (window.Alpine && typeof window.Alpine.$data === 'function') {
            try {
                candidates.push(window.Alpine.$data(element));
            } catch {}
        }
        if (element._x_dataStack) {
            candidates.push(...element._x_dataStack);
        }
        return candidates.find((data) => data && typeof data === 'object' && hasOwn(data, 'openRow')) || null;
    }

    function refreshSelectWidths(root) {
        root.querySelectorAll('.select2-container').forEach(function (container) {
            if (container.getBoundingClientRect().width < 40) {
                container.style.width = '100%';
            }
        });
    }

    // The stylesheet draws the open/closed chevron from this attribute, so the
    // block has to say whether it is open.
    function syncOpenState(group) {
        if (!group || !group.hasAttribute('x-data')) return;
        if (!(group.getAttribute('x-data') || '').includes('openRow')) return;
        const open = [...group.querySelectorAll('input, select, textarea')].some(
            (field) => field.type !== 'hidden' && field.getBoundingClientRect().height > 0
        );
        group.dataset.open = open ? 'true' : 'false';
    }

    function syncAllOpenStates() {
        document.querySelectorAll('.form-group[x-data*="openRow"]').forEach(syncOpenState);
    }

    function openBlock(group, attempt = 0) {
        const data = alpineData(group);
        if (data) {
            data.openRow = true;
            window.setTimeout(function () {
                refreshSelectWidths(group);
                syncOpenState(group);
            }, 50);
            return;
        }
        if (attempt < 10) {
            window.setTimeout(function () {
                openBlock(group, attempt + 1);
            }, 50);
        }
    }

    document.addEventListener('formset:added', function (event) {
        const group = event.target.closest('.form-group');
        if (group) openBlock(group);
    });

    // Re-measure the widgets when a closed block is opened by hand.
    document.addEventListener('click', function (event) {
        const title = event.target.closest('.form-group h3');
        if (!title) return;
        window.setTimeout(function () {
            const group = title.closest('.form-group');
            refreshSelectWidths(group);
            syncOpenState(group);
        }, 50);
    });

    // Alpine applies the open state when it starts, which is after this script.
    if (document.readyState === 'complete') {
        syncAllOpenStates();
    } else {
        window.addEventListener('load', syncAllOpenStates);
    }
    window.setTimeout(syncAllOpenStates, 400);
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
