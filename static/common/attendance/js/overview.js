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
makeWebsocket();
