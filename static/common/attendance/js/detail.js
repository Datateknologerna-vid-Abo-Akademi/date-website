/** @type {(text: string) => string} */
const _ = gettext;

const codeInput = document.getElementById("code");

const qrScanButton = document.getElementById("qr-scan");
const qrScanStopButton = document.getElementById("qr-scan-stop");

const qrReaderDiv = document.getElementById("qr-reader-div");
const qrReaderVideo = document.getElementById("qr-reader");
const qrReaderError = document.getElementById("qr-reader-error");

// This button is normally hidden, and the rightmost corners of the scan button will
// not be rounded unless it is the only button in its group, so we just remove the
// hidden button entirely and swap them as necessary
qrScanStopButton.remove();

const swapScanAndStop = () => {
    if (qrScanStopButton.hidden) {
        qrScanStopButton.hidden = false;
        qrScanButton.hidden = true;
        qrScanButton.replaceWith(qrScanStopButton);
    } else {
        qrScanButton.hidden = false;
        qrScanStopButton.hidden = true;
        qrScanStopButton.replaceWith(qrScanButton);
    }
};

const startScan = (scanner) => {
    qrReaderError.hidden = true;

    qrScanButton.disabled = true;
    scanner.start()
    .then(() => {
        swapScanAndStop();

        qrReaderDiv.hidden = false;
        qrReaderVideo.scrollIntoView({
            behavior: "instant",
            block: "center",
        });
    }).catch((err) => {
        qrReaderError.hidden = false;
        if (err === "Camera not found.") {
            qrReaderError.innerText = _("Ingen kamera hittades");
        } else {
            console.error("Error while scanning:", err);
            qrReaderError.innerText = _("Ett oväntat fel uppstod medan QR-skannern startades");
        }
    }).finally(() => {
        qrScanButton.disabled = false;
    });
}

const stopScan = (scanner) => {
    scanner.stop();
    qrReaderDiv.hidden = true;

    swapScanAndStop();
};

const onResult = (scanner, result) => {
    codeInput.value = "";
    const url = URL.parse(result.data);
    if (url === null || !url.searchParams.has("code")) {
        qrReaderError.hidden = false;
        qrReaderError.innerText = "QR code did not contain a code";
    } else {
        codeInput.value = url.searchParams.get("code");
    }

    stopScan(scanner);

    codeInput.scrollIntoView({
        behavior: "instant",
        block: "center",
    });
};


// https://github.com/nimiq/qr-scanner#usage
const qrScanner = new QrScanner(
    qrReaderVideo,
    (res) => onResult(qrScanner, res),
    {
        "highlightScanRegion": true,
        "highlightCodeOutline": true,
        "returnDetailedScanResult": true,
    },
);


qrScanButton.addEventListener("click", () => startScan(qrScanner));
qrScanStopButton.addEventListener("click", () => stopScan(qrScanner));

qrScanButton.disabled = false;
