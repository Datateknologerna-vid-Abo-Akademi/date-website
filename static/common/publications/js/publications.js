import * as pdfjsLib from 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.5.136/pdf.min.mjs';

pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.5.136/pdf.worker.min.mjs';

let pdfDoc = null;
let pageRendering = false;
let pageNumPending = null;
let scale = 1;
let viewer;
let currentPage = 1;
let pagesPerView = 1;

export function initPDFViewer(pdfUrl) {
    viewer = document.getElementById('pdf-viewer');

    function updatePagesPerView() {
        pagesPerView = window.innerWidth > 1024 ? 2 : 1;
        viewer.classList.toggle('two-page-view', pagesPerView === 2);
    }

    updatePagesPerView();
    window.addEventListener('resize', () => {
        updatePagesPerView();
        renderPages();
    });

    async function renderPages() {
        pageRendering = true;
        viewer.innerHTML = '';
        for (let i = 0; i < pagesPerView; i++) {
            if (currentPage + i <= pdfDoc.numPages) {
                const page = await pdfDoc.getPage(currentPage + i);
                const canvas = document.createElement('canvas');
                canvas.className = 'page-canvas';
                const context = canvas.getContext('2d');
                const viewport = page.getViewport({scale: scale});
                canvas.height = viewport.height;
                canvas.width = viewport.width;
                await page.render({canvasContext: context, viewport: viewport}).promise;
                viewer.appendChild(canvas);
            }
        }
        pageRendering = false;
        if (pageNumPending !== null) {
            renderPages(pageNumPending);
            pageNumPending = null;
        }
        updatePageDisplay();
    }

    function queueRenderPage(num) {
        if (pageRendering) {
            pageNumPending = num;
        } else {
            currentPage = num;
            renderPages();
        }
    }

    function updatePageDisplay() {
        const endPage = Math.min(currentPage + pagesPerView - 1, pdfDoc.numPages);
        document.getElementById('page-num').textContent = `${currentPage} - ${endPage}`;
        document.getElementById('page-count').textContent = pdfDoc.numPages;
    }

    document.getElementById('prev-page').addEventListener('click', () => {
        if (currentPage <= 1) return;
        currentPage = Math.max(1, currentPage - pagesPerView);
        queueRenderPage(currentPage);
    });

    document.getElementById('next-page').addEventListener('click', () => {
        if (currentPage >= pdfDoc.numPages) return;
        currentPage = Math.min(pdfDoc.numPages - pagesPerView + 1, currentPage + pagesPerView);
        queueRenderPage(currentPage);
    });

    document.getElementById('go-to-page').addEventListener('click', () => {
        const input = document.getElementById('page-input');
        const n = parseInt(input.value);
        if (n > 0 && n <= pdfDoc.numPages) {
            currentPage = n;
            queueRenderPage(currentPage);
        }
    });

    document.getElementById('zoom-select').addEventListener('change', (e) => {
        scale = parseFloat(e.target.value);
        renderPages();
    });

    document.getElementById('prev-page-mobile').addEventListener('click', () => {
        if (currentPage <= 1) return;
        queueRenderPage(currentPage - 1);
    });

    document.getElementById('next-page-mobile').addEventListener('click', () => {
        if (currentPage >= pdfDoc.numPages) return;
        queueRenderPage(currentPage + 1);
    });

    async function initViewer() {
        try {
            pdfDoc = await pdfjsLib.getDocument(pdfUrl).promise;
            updatePageDisplay();
            renderPages();
        } catch (error) {
            console.error('Error loading PDF:', error);
            viewer.innerHTML = '<p>Error loading PDF. Please try again later.</p>';
        }
    }

    initViewer();
}
