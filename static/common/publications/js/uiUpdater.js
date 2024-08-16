export function updateUIComponents(state) {
    if (state.isLoading) {
        updateLoadingDisplay(state);
    } else {
        updatePageDisplay(state);
        updateZoomDisplay(state);
        updateViewMode(state);
    }
}

function updateLoadingDisplay(state) {
    const loadingElement = document.createElement('div');
    loadingElement.className = 'loading-message';
    loadingElement.textContent = 'Loading PDF...';
    state.viewerElement.innerHTML = '';
    state.viewerElement.appendChild(loadingElement);
}

function updatePageDisplay(state) {
    const { currentPage, pdfDoc, pagesPerView } = state;
    if (!pdfDoc) return;

    let endPage = currentPage;
    if (pagesPerView === 2 && currentPage < pdfDoc.numPages) {
        endPage = currentPage + 1;
    }
    document.getElementById('page-num').textContent = `${currentPage} - ${endPage}`;
    document.getElementById('page-count').textContent = pdfDoc.numPages;
}

function updateZoomDisplay(state) {
    document.getElementById('zoom-select').value = state.scale;
}

function updateViewMode(state) {
    const viewer = document.getElementById('pdf-viewer');
    viewer.classList.toggle('two-page-view', state.pagesPerView === 2);
}