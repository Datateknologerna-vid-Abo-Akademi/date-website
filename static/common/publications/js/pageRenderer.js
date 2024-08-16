let pageRendering = false;
let pageNumPending = null;

export async function renderPages(state) {
    if (pageRendering) {
        pageNumPending = state.currentPage;
        return;
    }

    pageRendering = true;
    state.viewerElement.innerHTML = '';

    try {
        if (shouldRenderTwoPages(state)) {
            await Promise.all([
                renderPage(state, state.currentPage),
                renderPage(state, state.currentPage + 1)
            ]);
        } else {
            await renderPage(state, state.currentPage);
        }
    } catch (error) {
        console.error('Error rendering pages:', error);
        showErrorMessage('Failed to render PDF pages. Please try again.');
    }

    pageRendering = false;
    if (pageNumPending !== null) {
        renderPages({ ...state, currentPage: pageNumPending });
        pageNumPending = null;
    }
}

async function renderPage(state, pageNumber) {
    const page = await state.pdfDoc.getPage(pageNumber);
    const canvas = document.createElement('canvas');
    canvas.className = 'page-canvas';
    const context = canvas.getContext('2d');
    const viewport = page.getViewport({ scale: state.scale });
    canvas.height = viewport.height;
    canvas.width = viewport.width;
    await page.render({ canvasContext: context, viewport: viewport }).promise;
    state.viewerElement.appendChild(canvas);
}

function shouldRenderTwoPages(state) {
    return state.pagesPerView === 2 && state.currentPage > 1 && state.currentPage < state.pdfDoc.numPages - 1;
}

function showErrorMessage(message) {
    const errorElement = document.createElement('p');
    errorElement.className = 'error-message';
    errorElement.textContent = message;
    state.viewerElement.appendChild(errorElement);
}