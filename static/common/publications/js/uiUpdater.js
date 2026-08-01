import { getSpreadLayout } from './spreadLayout.js';

export function updateUIComponents(state) {
    updateLoadingDisplay(state);
    updateLoadingProgress(state);
    if (state.pdfDoc) {
        updatePageDisplay(state);
        updateZoomDisplay(state);
        updateViewMode(state);
        updateNavButtons(state);
        updateReadingProgress(state);
    }
}

function updateLoadingDisplay(state) {
    const loading = document.getElementById('pdf-loading');
    if (!loading) return;
    loading.classList.toggle('is-hidden', !state.isLoading);
}

function updateLoadingProgress(state) {
    const bar = document.getElementById('pdf-loading-bar');
    if (!bar) return;
    bar.style.width = `${state.loadingProgress || 0}%`;
}

function updatePageDisplay(state) {
    const { currentPage, pdfDoc } = state;
    const pageInput = document.getElementById('page-input');
    const pageCount = document.getElementById('page-count');
    if (!pageInput || !pageCount) return;

    if (document.activeElement !== pageInput) {
        pageInput.value = String(currentPage);
    }
    pageCount.textContent = pdfDoc.numPages;
    updatePageStatus(currentPage, pdfDoc.numPages);
}

function updatePageStatus(currentPage, pageCount) {
    const status = document.getElementById('page-status');
    if (status) status.textContent = `${currentPage} / ${pageCount}`;
}

function updateZoomDisplay(state) {
    const label = document.getElementById('zoom-label');
    if (label) label.textContent = `${Math.round(state.scale * 100)}%`;
}

function updateViewMode(state) {
    const viewer = state.viewerElement;
    if (!viewer) return;
    const layout = getSpreadLayout(state);
    const twoPage = Boolean(layout.leftPage && layout.rightPage);
    viewer.classList.toggle('two-page-view', twoPage);
    viewer.classList.toggle('single-page-view', !twoPage);
}

function updateNavButtons(state) {
    const layout = getSpreadLayout(state);
    const prev = document.getElementById('prev-page');
    const next = document.getElementById('next-page');
    if (prev) prev.disabled = layout.isFirstSpread;
    if (next) next.disabled = layout.isLastSpread;
}

function updateReadingProgress(state) {
    const bar = document.getElementById('reading-progress');
    if (!bar) return;
    const layout = getSpreadLayout(state);
    const visibleLastPage = layout.rightPage || layout.leftPage || state.currentPage;
    const progress = (visibleLastPage / state.pdfDoc.numPages) * 100;
    bar.style.width = `${Math.min(100, Math.max(0, progress))}%`;
}
