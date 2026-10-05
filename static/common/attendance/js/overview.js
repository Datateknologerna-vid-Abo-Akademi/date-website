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
const statusMessage = document.getElementById("status-message")

const attendeeList = document.getElementById("present-attendees");
const attendeeEmptyState = document.getElementById("no-present-attendees");
const attendeeCount = document.getElementById("present-count");

const qrDiv = document.getElementById("qrcode");
const qrCanvas = document.createElement("canvas");
qrDiv.appendChild(qrCanvas);

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

        const untilNext = Number(data.until_next) * 1000;
        // A renamed or missing field would make this NaN, and setTimeout treats
        // NaN as zero, which would turn the countdown into a tight request loop.
        const delay = Number.isFinite(untilNext) && untilNext > 0 ? untilNext : CODE_REQUEST_FALLBACK_MS;
        codeFetcher = setTimeout(() => requestNewCode(ws), delay);
    } else if (data.type == "attendance_snapshot") {
        replaceAttendees(data.data);
    } else if (data.type == "attendance_change") {
        applyAttendanceChange(data.data);
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
        setStatusMessage("");
        console.log("Websocket open");

        requestNewCode(ws);
    });
    ws.addEventListener("close", (ev) => {
        clearTimeout(codeFetcher);

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
