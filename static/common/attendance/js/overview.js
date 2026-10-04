/** @type {(text: string) => string} */
const _ = gettext;

/**
 * @param {string} url
 */
const stripLastSeparator = (url) => {
    const lastSeparatorIdx = url.lastIndexOf('/');
    return lastSeparatorIdx < 1 ? url : url.slice(0, lastSeparatorIdx);
};

const wsUrl = `/ws${stripLastSeparator(window.location.pathname)}`

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

/**
 * One row per attendee, matched on the key rather than the name: two members can
 * share a name, and a guest may type a name a member already has.
 *
 * @param {{key: string, name: string}} entry
 */
const addAttendee = (entry) => {
    const alreadyListed = Array.from(attendeeList.children).some((item) => item.dataset.attendee === entry.key);
    if (alreadyListed) {
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
 * Replace the whole list with the snapshot the server sends on connect, so
 * anything that happened between the page render and the socket opening is not
 * lost.
 *
 * Entries are keyed, so a snapshot and a live change for the same attendee are
 * idempotent: the second one lands on the same row, either message may arrive
 * first, and no ordering dance between them is needed.
 *
 * @param {Array<{key: string, name: string}>} entries
 */
const replaceAttendees = (entries) => {
    attendeeList.replaceChildren();

    for (const entry of entries) {
        addAttendee(entry);
    }

    updateEmptyState();
}

/**
 * @param {{key: string, name: string, type: string}} change
 */
const applyAttendanceChange = (change) => {
    if (change.type == "ENTER") {
        addAttendee(change);
    } else if (change.type == "LEAVE") {
        removeAttendee(change.key);
    }
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
    setStatusMessage(_("Ansluter till servern..."));
    const ws = new WebSocket(wsUrl);
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
