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
    let url = null;
    try {
        // `new URL` and not `URL.parse`: the static parser is a 2024 API
        // (Chrome 126+, Safari 17.6+), and on anything older it throws, which
        // would leave the code empty and the camera running. The page's own origin
        // is the base, so a QR that carries a path rather than a full link, which
        // is what an older code in the wild holds, still fills the box in.
        url = new URL(result.data, window.location.origin);
    } catch (err) {
        // Not a URL at all, which gets the same answer as one without a code
        // parameter.
        console.debug("The scanned value is not a URL:", err);
    }

    if (url === null || !url.searchParams.has("code")) {
        qrReaderError.hidden = false;
        qrReaderError.innerText = _("QR-koden innehöll ingen kod");
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
let qrScanner = null;
try {
    qrScanner = new QrScanner(
        qrReaderVideo,
        (res) => onResult(qrScanner, res),
        {
            "highlightScanRegion": true,
            "highlightCodeOutline": true,
            "returnDetailedScanResult": true,
        },
    );
} catch (err) {
    // Scanning is optional, and the code can still be typed in. A failed CDN load
    // leaves QrScanner undefined, so say what happened instead of leaving the
    // button disabled with no explanation.
    console.error("Could not set up the QR scanner:", err);
    qrReaderError.hidden = false;
    qrReaderError.innerText = _("QR-skannern kunde inte laddas");
}


qrScanButton.addEventListener("click", () => startScan(qrScanner));
qrScanStopButton.addEventListener("click", () => stopScan(qrScanner));

qrScanButton.disabled = qrScanner === null;
