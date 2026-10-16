/** @type {(text: string) => string} */
const _ = gettext;

/**
 * @param {string} url
 */
const stripLastSeparator = (url) => {
    const lastSeparatorIdx = url.lastIndexOf('/');
    return lastSeparatorIdx < 1 ? url : url.slice(0, lastSeparatorIdx);
};

const codeDisplay = document.getElementById("current-code");
const codeCountdown = document.getElementById("code-countdown");
const statusMessage = document.getElementById("status-message")

const attendeeList = document.getElementById("present-attendees");
const attendeeEmptyState = document.getElementById("no-present-attendees");
const attendeeCount = document.getElementById("present-count");

const changeFeed = document.getElementById("change-feed");
const changeEmptyState = document.getElementById("no-changes");
const feedMore = document.getElementById("feed-more");
const feedEnd = document.getElementById("feed-end");

// The server renders the stretch of the log up to the page load and hides all but
// the first page of it; the socket appends what happens next. The table is trimmed
// so a long meeting cannot grow the page without bound, oldest rows first, which
// are the hidden ones.
const FEED_MAX_ENTRIES = 120;
const FEED_PAGE_SIZE = 20;

const qrDiv = document.getElementById("qrcode");
const qrCanvas = document.createElement("canvas");
qrDiv.appendChild(qrCanvas);

// The canvas is an image to a screen reader and the caption beside it is a
// separate paragraph, so the image carries its own name.
qrCanvas.setAttribute("role", "img");
qrCanvas.setAttribute("aria-label", _("QR-kod som leder till incheckningssidan"));

const qrOptions = {
    scale: 8,
};

const updateQrCode = (code) => {
    // The event page's absolute URL comes from the view, so what the QR holds is a
    // link any camera app will open, and the check-in page's own scanner can parse
    // it. The fallback covers a template override that leaves the attribute out.
    const eventUrl =
        qrDiv.dataset.eventUrl ||
        `${window.location.origin}${stripLastSeparator(window.location.pathname)}/`;

    // The QR code is a convenience for phones; the attendee list is the point of
    // the page. A failed CDN load leaves QRCode undefined, and without this guard
    // the throw would happen here and the websocket below would never open.
    try {
        // https://github.com/soldair/node-qrcode
        QRCode.toCanvas(qrCanvas, `${eventUrl}?code=${code}`, qrOptions);
    } catch (err) {
        console.warn("Could not draw the QR code:", err);
    }
    codeDisplay.innerText = code;
};

const setStatusMessage = (msg) => {
    statusMessage.innerText = msg;
}

// How long after a code should have rotated the page stops presenting it as
// current. A websocket that stalls without closing leaves the last code on
// screen, and a code that looks live but is not is worse than no code: the
// person reading it out would be reading a value the server rejects. The grace
// only has to cover the round trip of the request that was already sent.
const CODE_STALE_GRACE_MS = 3_000;
const COUNTDOWN_TICK_MS = 1_000;

let countdownTimer = null;
let codeDeadline = 0;
let codeIsStale = false;

// The wrapper both pages render around the code and the QR code, dimmed together
// when the code stops rotating: the QR carries the same expired code, so leaving
// it bright invites a scan the server will refuse.
const attendancePage = document.querySelector(".attendance-page");

const setStalePresentation = (stale) => {
    if (attendancePage) {
        attendancePage.classList.toggle("attendance-page--code-stale", stale);
    }
};

const renderCountdown = () => {
    // The page is a shared template and an association override could drop the
    // element. Only the writes are guarded: the deadline still has to expire, or
    // an override without a countdown line would keep presenting a stale code and
    // its QR code for ever.
    const remaining = codeDeadline - Date.now();

    if (remaining > 0) {
        if (codeCountdown) {
            const seconds = Math.ceil(remaining / COUNTDOWN_TICK_MS);
            codeCountdown.innerText = interpolate(_("Ny kod om %(seconds)s s"), {seconds}, true);
            codeCountdown.classList.remove("attendance-countdown--stale");
        }
    } else if (remaining > -CODE_STALE_GRACE_MS) {
        if (codeCountdown) {
            codeCountdown.innerText = _("Hämtar en ny kod...");
        }
    } else {
        markCodeStale();
    }
};

/**
 * Count down to the next rotation, when the reply says how long that is.
 *
 * A reply without usable timing must not start a countdown: the fallback delay
 * is how long until the page asks again, which is not how long the code stays
 * good for, and promising a rotation the page cannot know would be a lie.
 *
 * @param {number|null} untilNextMs
 */
const startCountdown = (untilNextMs) => {
    window.clearInterval(countdownTimer);
    countdownTimer = null;
    codeDeadline = 0;

    if (!Number.isFinite(untilNextMs) || untilNextMs <= 0) {
        if (codeCountdown) {
            codeCountdown.innerText = _("Hämtar en ny kod...");
            codeCountdown.classList.remove("attendance-countdown--stale");
        }
        return;
    }

    codeDeadline = Date.now() + untilNextMs;
    renderCountdown();
    countdownTimer = window.setInterval(renderCountdown, COUNTDOWN_TICK_MS);
};

const stopCountdown = () => {
    window.clearInterval(countdownTimer);
    countdownTimer = null;
}

const clearCodeStale = () => {
    if (!codeIsStale) {
        return;
    }

    codeIsStale = false;
    setStalePresentation(false);
    setStatusMessage("");
}

const markCodeStale = () => {
    stopCountdown();
    codeDeadline = 0;

    // Said once per stall, not on every tick of the interval that found it.
    if (codeIsStale) {
        return;
    }

    codeIsStale = true;
    setStalePresentation(true);

    if (codeCountdown) {
        codeCountdown.innerText = _("Koden uppdateras inte. Kontrollera anslutningen.");
        codeCountdown.classList.add("attendance-countdown--stale");
    }

    // The countdown line is aria-hidden because it ticks every second, so the
    // warning reaches a screen reader through the page's live status region.
    // A closed socket reports itself there too, and overwrites this.
    setStatusMessage(_("Koden uppdateras inte. Kontrollera anslutningen."));
}

/**
 * The headcount is read off the list rather than tracked beside it, so the
 * number and the rows cannot drift apart. Every path that changes the list
 * (the connect snapshot, an arrival, a departure) goes through
 * updateEmptyState, which is where this is called from.
 */
const updateCount = () => {
    attendeeCount.innerText = attendeeList.children.length;
}

const updateEmptyState = () => {
    attendeeEmptyState.hidden = attendeeList.children.length > 0;
    updateCount();
}

// A live delta and the connect snapshot may arrive out of order. Keep the
// highest (timestamp, primary key) seen for each attendee and ignore stale state.
const attendeeVersions = new Map();

/**
 * One row per attendee, matched on the key rather than the name: two members can
 * share a name, and a guest may type a name a member already has.
 *
 * @param {{key: string, name: string}} entry
 */
const addAttendee = (entry) => {
    const existing = Array.from(attendeeList.children).find((item) => item.dataset.attendee === entry.key);
    if (existing) {
        existing.innerText = entry.name;
        return;
    }

    const item = document.createElement("li");
    item.dataset.attendee = entry.key;
    item.innerText = entry.name;
    attendeeList.appendChild(item);

    updateEmptyState();
}

/**
 * @param {string} key
 */
const removeAttendee = (key) => {
    for (const item of Array.from(attendeeList.children)) {
        if (item.dataset.attendee === key) {
            item.remove();
        }
    }

    updateEmptyState();
}

/**
 * Apply a versioned current-state entry only if it is newer than the state
 * already received for this attendee.
 *
 * @param {{key: string, name: string, type: string, present: boolean, timestamp: string, change_id: number}} state
 */
const applyAttendanceState = (state) => {
    const changeId = Number(state.change_id);
    if (typeof state.key !== "string" || typeof state.timestamp !== "string" || !Number.isSafeInteger(changeId)) {
        return;
    }

    const previous = attendeeVersions.get(state.key);
    if (previous && (state.timestamp < previous.timestamp || (state.timestamp === previous.timestamp && changeId <= previous.changeId))) {
        return;
    }

    attendeeVersions.set(state.key, {timestamp: state.timestamp, changeId});
    if (state.present) {
        addAttendee(state);
    } else {
        removeAttendee(state.key);
    }
}

/**
 * Merge the versioned snapshot instead of replacing the list blindly. The
 * snapshot includes absent attendees as tombstones. Initial HTML rows missing
 * from it are removed, except when a newer live delta already arrived.
 *
 * @param {Array<{key: string, name: string, type: string, present: boolean, timestamp: string, change_id: number}>} states
 */
const replaceAttendees = (states) => {
    if (!Array.isArray(states)) {
        return;
    }

    const snapshotKeys = new Set(states.map((state) => state.key));
    for (const item of Array.from(attendeeList.children)) {
        const key = item.dataset.attendee;
        if (!snapshotKeys.has(key) && !attendeeVersions.has(key)) {
            item.remove();
        }
    }

    for (const state of states) {
        applyAttendanceState(state);
    }

    updateEmptyState();
}

/**
 * @param {{key: string, name: string, type: string, timestamp: string, change_id: number}} change
 */
const applyAttendanceChange = (change) => {
    if (change.type !== "ENTER" && change.type !== "LEAVE") {
        return;
    }

    applyAttendanceState({...change, present: change.type === "ENTER"});
}

/**
 * The time in the reader's own clock, in the 24 hour shape the server renders the
 * rows it sends with the page.
 *
 * @param {string} timestamp
 */
const formatFeedTime = (timestamp) => {
    const when = new Date(timestamp);
    if (Number.isNaN(when.getTime())) {
        return "";
    }

    return when.toLocaleTimeString(undefined, {hour: "2-digit", minute: "2-digit", hour12: false});
}

/**
 * Write the same change into the log the board follows, newest first.
 *
 * The server renders the log up to the page load, so anything already on the page
 * is left alone: a row is matched on its change id, which is also what keeps a
 * repeated frame from appearing twice.
 *
 * @param {{name: string, type: string, timestamp: string, change_id: number}} change
 */
const addChangeToFeed = (change) => {
    if (!changeFeed || (change.type !== "ENTER" && change.type !== "LEAVE")) {
        return;
    }

    const changeId = String(change.change_id);
    if (changeFeed.querySelector(`tr[data-change-id="${changeId}"]`)) {
        return;
    }

    const direction = change.type === "ENTER" ? "enter" : "leave";

    const item = document.createElement("tr");
    item.dataset.changeId = changeId;
    item.className = `attendance-changes__row--${direction}`;

    const timeCell = document.createElement("td");
    timeCell.className = "attendance-changes__time";
    const time = document.createElement("time");
    time.dateTime = typeof change.timestamp === "string" ? change.timestamp : "";
    time.innerText = formatFeedTime(change.timestamp);
    timeCell.append(time);

    const nameCell = document.createElement("td");
    nameCell.className = "attendance-changes__name";
    nameCell.innerText = change.name || "";

    const actionCell = document.createElement("td");
    actionCell.className = `attendance-changes__action attendance-changes__action--${direction}`;
    actionCell.innerText = change.type === "ENTER" ? _("Anlände") : _("Lämnade");

    item.append(timeCell, nameCell, actionCell);
    changeFeed.prepend(item);

    while (changeFeed.children.length > FEED_MAX_ENTRIES) {
        changeFeed.lastElementChild.remove();
    }

    if (changeEmptyState) {
        changeEmptyState.hidden = true;
    }
}

/**
 * Reveal the next page of the rows the server rendered, and point at the full log
 * once there are none left. The table is bounded, so the feed cannot run forever
 * and the rest of the history lives on the meeting's own page.
 */
const revealMoreFeedRows = () => {
    if (!changeFeed || !feedMore) {
        return;
    }

    const pageSize = Number(feedMore.dataset.pageSize) || FEED_PAGE_SIZE;
    let revealed = 0;
    for (const row of changeFeed.querySelectorAll("tr[hidden]")) {
        if (revealed >= pageSize) {
            break;
        }
        row.hidden = false;
        revealed += 1;
    }

    if (!changeFeed.querySelector("tr[hidden]")) {
        feedMore.hidden = true;
        if (feedEnd) {
            feedEnd.hidden = false;
        }
    }
}

if (feedMore) {
    feedMore.addEventListener("click", revealMoreFeedRows);
}

/**
 * @param {WebSocket} ws
 */
const requestNewCode = (ws) => {
    ws.send(JSON.stringify({
        "type": "get_code",
    }));
}

// How long to wait before asking again when the reply carries no usable delay.
const CODE_REQUEST_FALLBACK_MS = 5_000;

let codeFetcher = null;
const onMessage = (ws, msg) => {
    let data;
    try {
        data = JSON.parse(msg.data);
    } catch (err) {
        // One unreadable frame must not stop the rotation, which is the only
        // thing keeping the displayed code current.
        console.error("Ignoring an unreadable websocket frame:", err);
        return;
    }

    if (data.type == "code") {
        updateQrCode(data.code);
        clearCodeStale();

        const seconds = Number(data.until_next);
        // A renamed or missing field would make this NaN, and setTimeout treats
        // NaN as zero, which would turn the retry into a tight request loop. The
        // same value only becomes a countdown when it is usable.
        const knownWindow = Number.isFinite(seconds) && seconds > 0;
        startCountdown(knownWindow ? seconds * 1000 : null);

        const delay = knownWindow ? seconds * 1000 : CODE_REQUEST_FALLBACK_MS;
        window.clearTimeout(codeFetcher);
        codeFetcher = setTimeout(() => requestNewCode(ws), delay);
    } else if (data.type == "attendance_snapshot") {
        replaceAttendees(data.data);
    } else if (data.type == "attendance_change") {
        applyAttendanceChange(data.data);
        addChangeToFeed(data.data);
    }
};

const makeWebsocket = () => {
    // A reconnect gets a fresh authoritative snapshot; only versions received
    // on this connection may protect rows that are absent from that snapshot.
    attendeeVersions.clear();
    setStatusMessage(_("Ansluter till servern..."));

    let ws;
    try {
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/ws${stripLastSeparator(window.location.pathname)}`;
        ws = new WebSocket(wsUrl);
    } catch (err) {
        // A malformed URL or a synchronous constructor error must not leave the
        // status stuck at "connecting" without the normal retry.
        console.warn("Could not create the attendance websocket:", err);
        setStatusMessage(_("Anslutningen till servern bröts"));
        setTimeout(makeWebsocket, 5_000);
        return;
    }

    ws.addEventListener("message", (msg) => onMessage(ws, msg));
    ws.addEventListener("open", () => {
        // A stale warning stays until a fresh code actually arrives: a socket that
        // opens and then returns nothing must not look healthy again.
        if (!codeIsStale) {
            setStatusMessage("");
        }
        console.log("Websocket open");

        requestNewCode(ws);
    });
    ws.addEventListener("close", (ev) => {
        clearTimeout(codeFetcher);
        markCodeStale();

        // 4003 and 4004 are the server saying this page cannot come back: the
        // staff permission was removed, or the event is gone. Retrying would ask
        // again every five seconds forever, so say so and stop.
        if (ev.code === 4003 || ev.code === 4004) {
            setStatusMessage(_("Sidan kan inte längre uppdateras. Ladda om sidan."));
            console.warn(`WebSocket closed by the server with code ${ev.code}; not retrying`);
            return;
        }

        setStatusMessage(_("Anslutningen till servern bröts"));
        console.warn(`WebSocket closed! Retrying in 5 seconds`);

        setTimeout(makeWebsocket, 5_000);
    });
};

// The QR code is optional, so a failure there must not stop the list from
// connecting: the guard inside updateQrCode keeps this line from throwing.
updateQrCode(codeDisplay.innerText);
updateEmptyState();
makeWebsocket();
