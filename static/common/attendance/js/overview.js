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

const qrDiv = document.getElementById("qrcode");
const qrCanvas = document.createElement("canvas");
qrDiv.appendChild(qrCanvas);

const qrOptions = {
    scale: 8,
};

const updateQrCode = (code) => {
    const url = stripLastSeparator(window.location.href);

    // https://github.com/soldair/node-qrcode
    QRCode.toCanvas(qrCanvas, `${url}?code=${code}`, qrOptions);
    codeDisplay.innerText = code;
};

const setStatusMessage = (msg) => {
    statusMessage.innerText = msg;
}

const updateEmptyState = () => {
    attendeeEmptyState.hidden = attendeeList.children.length > 0;
}

/**
 * @param {string} name
 */
const addAttendee = (name) => {
    const alreadyListed = Array.from(attendeeList.children).some((item) => item.dataset.attendee === name);
    if (alreadyListed) {
        return;
    }

    const item = document.createElement("li");
    item.dataset.attendee = name;
    item.innerText = name;
    attendeeList.appendChild(item);

    updateEmptyState();
}

/**
 * @param {string} name
 */
const removeAttendee = (name) => {
    for (const item of Array.from(attendeeList.children)) {
        if (item.dataset.attendee === name) {
            item.remove();
        }
    }

    updateEmptyState();
}

/**
 * @param {{name: string, type: string}} change
 */
const applyAttendanceChange = (change) => {
    if (change.type == "ENTER") {
        addAttendee(change.name);
    } else if (change.type == "LEAVE") {
        removeAttendee(change.name);
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

let codeFetcher = null;
const onMessage = (ws, msg) => {
    const data = JSON.parse(msg.data);

    if (data.type == "code") {
        updateQrCode(data.code);

        codeFetcher = setTimeout(() => requestNewCode(ws), data.until_next * 1000);
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
        setStatusMessage(_("Anslutningen till servern bröts"));
        console.warn(`WebSocket closed! Retrying in 5 seconds`);

        clearTimeout(codeFetcher);
        setTimeout(makeWebsocket, 5_000);
    });
};

updateQrCode(codeDisplay.innerText);
updateEmptyState();
makeWebsocket();
