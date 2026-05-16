import * as pdfjsLib from 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.5.136/pdf.min.mjs';
import { renderPages } from './pageRenderer.js';
import { setupEventListeners } from './eventListeners.js';
import { updateUIComponents } from './uiUpdater.js';

pdfjsLib.GlobalWorkerOptions.workerSrc =
    'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.5.136/pdf.worker.min.mjs';

class PDFViewerState {
    constructor() {
        this.pdfDoc = null;
        this.currentPage = 1;
        this.scale = 1;
        this.pagesPerView = 1;
        this.viewerElement = null;
        this.shellElement = null;
        this.isLoading = true;
        this.loadingProgress = 0;
    }

    updateState(newState) {
        Object.assign(this, newState);
        updateUIComponents(this);
    }
}

const state = new PDFViewerState();

function computePagesPerView() {
    return window.innerWidth > 1024 ? 2 : 1;
}

export function initPDFViewer(pdfUrl, viewerElement) {
    state.viewerElement = viewerElement;
    state.shellElement = document.getElementById('pdf-shell');
    state.pagesPerView = computePagesPerView();
    state.updateState({ isLoading: true, loadingProgress: 0 });

    let resizeTimer;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => {
            const newPagesPerView = computePagesPerView();
            if (newPagesPerView !== state.pagesPerView) {
                state.updateState({ pagesPerView: newPagesPerView });
            }
            // Always re-render — even when pagesPerView didn't flip, the
            // viewer width might have changed and the fit-scale needs to
            // recompute so state.scale=1 keeps meaning "fit to viewport".
            if (state.pdfDoc) {
                renderPages(state, { skipAnimation: true });
            }
        }, 150);
    });

    setupEventListeners(state);
    loadPDF(pdfUrl);
}

async function loadPDF(pdfUrl) {
    try {
        const loadingTask = pdfjsLib.getDocument(pdfUrl);
        loadingTask.onProgress = ({ loaded, total }) => {
            if (total) {
                const pct = Math.min(100, Math.round((loaded / total) * 100));
                state.updateState({ loadingProgress: pct });
            }
        };
        const pdfDoc = await loadingTask.promise;
        state.updateState({ pdfDoc, loadingProgress: 100 });
        await renderPages(state, { skipAnimation: true });
        state.updateState({ isLoading: false });
        preloadNeighborPages(state);
    } catch (error) {
        console.error('Error loading PDF:', error);
        showErrorMessage('Failed to load PDF. Please try again later.');
        state.updateState({ isLoading: false });
    }
}

function showErrorMessage(message) {
    state.viewerElement.innerHTML = `<p class="pdf-error">${message}</p>`;
}

export function preloadNeighborPages(state) {
    if (!state.pdfDoc) return;
    const numPages = state.pdfDoc.numPages;
    const toLoad = new Set();
    for (let offset = -2; offset <= 3; offset++) {
        const p = state.currentPage + offset;
        if (p >= 1 && p <= numPages) toLoad.add(p);
    }
    toLoad.forEach((p) => {
        state.pdfDoc.getPage(p).catch(() => { /* ignore */ });
    });
}

export function getState() {
    return state;
}

export function updateState(newState) {
    state.updateState(newState);
}
