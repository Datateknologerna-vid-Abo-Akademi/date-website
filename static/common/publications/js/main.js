import { initPDFViewer } from './pdfViewer.js';

document.addEventListener('DOMContentLoaded', () => {
    const pdfUrl = document.getElementById('pdf-viewer').dataset.pdfUrl;
    const viewerElement = document.getElementById('pdf-viewer');
    initPDFViewer(pdfUrl, viewerElement);
});