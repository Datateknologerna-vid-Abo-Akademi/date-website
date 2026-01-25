import * as pdfjsLib from 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.5.136/pdf.min.mjs';
import { renderPages } from './pageRenderer.js';
import { setupEventListeners } from './eventListeners.js';
import { updateUIComponents } from './uiUpdater.js';

pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.5.136/pdf.worker.min.mjs';

class PDFViewerState {
    constructor() {
        this.pdfDoc = null;
        this.currentPage = 1;
        this.scale = 1;
        this.pagesPerView = 1;
        this.viewerElement = null;
        this.isLoading = true;
    }

    updateState(newState) {
        Object.assign(this, newState);
        updateUIComponents(this);
    }
}

const state = new PDFViewerState();

export function initPDFViewer(pdfUrl, viewerElement) {
    state.viewerElement = viewerElement;
    state.updateState({ isLoading: true });

    function updatePagesPerView() {
        const newPagesPerView = window.innerWidth > 1024 ? 2 : 1;
        if (newPagesPerView !== state.pagesPerView) {
            state.updateState({ pagesPerView: newPagesPerView });
            if (state.pdfDoc) {
                renderPages(state);
            }
        }
    }

    updatePagesPerView();
    window.addEventListener('resize', updatePagesPerView);

    setupEventListeners(state);

    loadPDF(pdfUrl);
}

async function loadPDF(pdfUrl) {
    try {
        const loadingTask = pdfjsLib.getDocument(pdfUrl);
        const pdfDoc = await loadingTask.promise;
        state.updateState({ pdfDoc, isLoading: false });
        renderPages(state);
    } catch (error) {
        console.error('Error loading PDF:', error);
        showErrorMessage('Failed to load PDF. Please try again later.');
        state.updateState({ isLoading: false });
    }
}

function showErrorMessage(message) {
    state.viewerElement.innerHTML = `<p class="error-message">${message}</p>`;
}

export function getState() {
    return state;
}

export function updateState(newState) {
    state.updateState(newState);
}

export function shouldRenderTwoPages() {
    return state.pdfDoc && state.pagesPerView === 2 && state.currentPage > 1 && state.currentPage < state.pdfDoc.numPages;
}