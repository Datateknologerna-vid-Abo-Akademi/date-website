// The "show more" pager for attendance changes, and for the roster.
//
// The server renders the whole list and hides all but the first page of it; a
// click reveals the next page, and once none are left the button gives way to the
// line naming where the rest of the record lives. Three places use this: the live
// feed on the staff overview page, the log on the event page, and the event page's
// roster of present names, which is a list rather than a table. Everything is
// keyed off ids, so the wording and the markup stay with the templates.

const CHANGES_PAGE_SIZE_FALLBACK = 20;

/**
 * Reveal one page of whatever the button is paging.
 *
 * @param {HTMLElement} container
 * @param {string} itemSelector
 * @param {HTMLElement} button
 * @returns {boolean} true when nothing is left hidden
 */
const revealNextPage = (container, itemSelector, button) => {
    const pageSize = Number(button.dataset.pageSize) || CHANGES_PAGE_SIZE_FALLBACK;
    let revealed = 0;

    for (const item of container.querySelectorAll(itemSelector)) {
        if (revealed >= pageSize) {
            break;
        }
        item.hidden = false;
        revealed += 1;
    }

    return !container.querySelector(itemSelector);
};

/**
 * @param {string} containerId
 * @param {string} buttonId
 * @param {string} itemSelector
 * @param {string|null} endId
 */
const wireMorePager = (containerId, buttonId, itemSelector, endId = null) => {
    const container = document.getElementById(containerId);
    const button = document.getElementById(buttonId);
    const end = endId ? document.getElementById(endId) : null;

    if (!container || !button) {
        return;
    }

    button.addEventListener("click", () => {
        if (!revealNextPage(container, itemSelector, button)) {
            return;
        }

        button.hidden = true;
        if (end) {
            end.hidden = false;
        }
    });
};

wireMorePager("change-feed", "feed-more", "tr[hidden]", "feed-end");
wireMorePager("change-log", "log-more", "tr[hidden]", "log-end");
wireMorePager("present-roster", "roster-more", "li[hidden]");
