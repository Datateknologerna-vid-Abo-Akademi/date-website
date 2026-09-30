import { initPDFViewer } from './pdfViewer.js';

document.addEventListener('DOMContentLoaded', () => {
    const viewerElement = document.getElementById('pdf-viewer');
    if (!viewerElement) return;
    const pdfUrl = viewerElement.dataset.pdfUrl;
    initPDFViewer(pdfUrl, viewerElement);
});
