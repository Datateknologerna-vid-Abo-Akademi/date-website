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
    pageInput.max = pdfDoc.numPages;
    pageCount.textContent = pdfDoc.numPages;
}

function updateZoomDisplay(state) {
    const label = document.getElementById('zoom-label');
    if (label) label.textContent = `${Math.round(state.scale * 100)}%`;
}

function updateViewMode(state) {
    const viewer = state.viewerElement;
    if (!viewer) return;
    // A two-page layout is rendered whenever the spread shows two real
    // pages: any middle spread, plus the 2-page-PDF special case where both
    // pages share a single (1, 2) spread (see layoutFor in pageRenderer).
    const numPages = state.pdfDoc.numPages;
    const twoPage = state.pagesPerView === 2
        && ((state.currentPage > 1 && state.currentPage < numPages) || numPages === 2);
    viewer.classList.toggle('two-page-view', twoPage);
    viewer.classList.toggle('single-page-view', !twoPage);
}

function updateNavButtons(state) {
    const numPages = state.pdfDoc.numPages;
    const inPair = state.pagesPerView === 2 && state.currentPage > 1 && state.currentPage < numPages;
    const twoPageWholeDoc = state.pagesPerView === 2 && numPages === 2;
    const atStart = state.currentPage <= 1;
    // Also at the end when the current spread already includes the last
    // page (odd-paginated PDFs have no useful "back cover" view past the
    // final spread, and 2-page PDFs render the whole document as one
    // spread — see navigateNext).
    const atEnd = state.currentPage >= numPages
        || (inPair && state.currentPage + 1 >= numPages)
        || twoPageWholeDoc;
    const prev = document.getElementById('prev-page');
    const next = document.getElementById('next-page');
    if (prev) prev.disabled = atStart;
    if (next) next.disabled = atEnd;
}

function updateReadingProgress(state) {
    const bar = document.getElementById('reading-progress');
    if (!bar) return;
    const progress = (state.currentPage / state.pdfDoc.numPages) * 100;
    bar.style.width = `${Math.min(100, Math.max(0, progress))}%`;
}
