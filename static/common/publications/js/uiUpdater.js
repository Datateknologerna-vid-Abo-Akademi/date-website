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

    // If on the first page and not in two-page view, only show "1"
    if (currentPage === 1 && pagesPerView === 1) {
        endPage = currentPage; // Show only "1" when on the cover page
    } else if (pagesPerView === 2 && currentPage < pdfDoc.numPages) {
        // Show two-page range, e.g., "3-4"
        endPage = currentPage + 1;
    }

    // Update the page display text
    document.getElementById('page-num').textContent = `${currentPage}${endPage !== currentPage ? ` - ${endPage}` : ''}`;
    document.getElementById('page-count').textContent = pdfDoc.numPages;
}


function updateZoomDisplay(state) {
    document.getElementById('zoom-select').value = state.scale;
}

function updateViewMode(state) {
    const viewer = document.getElementById('pdf-viewer');

    // Add a class to handle single-page view for the cover page and the last page
    if (state.currentPage === 1 || state.currentPage >= state.pdfDoc.numPages || state.pagesPerView === 1) {
        viewer.classList.add('single-page-view');
        viewer.classList.remove('two-page-view');
    } else if (state.pagesPerView === 2) {
        viewer.classList.add('two-page-view');
        viewer.classList.remove('single-page-view');
    } else {
        viewer.classList.remove('two-page-view', 'single-page-view');
    }
}
