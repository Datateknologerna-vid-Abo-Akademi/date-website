// The "show more" pager for a table of attendance changes.
//
// The server renders the newest rows of the table and hides all but the first page
// of them; a click reveals the next page, and once none are left the button gives
// way to the line naming where the rest of the record lives. Two pages use this:
// the live feed on the staff overview page and the log on the event page, so the
// pager keys everything off ids and leaves the wording to the templates.

const CHANGES_PAGE_SIZE_FALLBACK = 20;

/**
 * @param {string} tbodyId
 * @param {string} buttonId
 * @param {string} endId
 */
const wireChangesTablePager = (tbodyId, buttonId, endId) => {
    const tbody = document.getElementById(tbodyId);
    const button = document.getElementById(buttonId);
    const end = document.getElementById(endId);

    if (!tbody || !button) {
        return;
    }

    button.addEventListener("click", () => {
        const pageSize = Number(button.dataset.pageSize) || CHANGES_PAGE_SIZE_FALLBACK;
        let revealed = 0;

        for (const row of tbody.querySelectorAll("tr[hidden]")) {
            if (revealed >= pageSize) {
                break;
            }
            row.hidden = false;
            revealed += 1;
        }

        if (!tbody.querySelector("tr[hidden]")) {
            button.hidden = true;
            if (end) {
                end.hidden = false;
            }
        }
    });
};

wireChangesTablePager("change-feed", "feed-more", "feed-end");
wireChangesTablePager("change-log", "log-more", "log-end");
