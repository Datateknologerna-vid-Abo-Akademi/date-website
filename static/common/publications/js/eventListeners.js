import { renderPages } from './pageRenderer.js';
import { updateState, shouldRenderTwoPages } from './pdfViewer.js';

export function setupEventListeners(state) {
    document.getElementById('prev-page').addEventListener('click', () => {
    if (state.currentPage <= 1) return;

    let newPage;

    if (state.currentPage === state.pdfDoc.numPages) {
        // Jump back two from the last page (the previous pair)
        newPage = state.currentPage - 2;
    } else if (shouldRenderTwoPages(state)) {
        // Regular two-page navigation
        newPage = state.currentPage - 2;
    } else {
        // Standard single-page navigation
        newPage = state.currentPage - 1;
    }

    updateState({ currentPage: Math.max(1, newPage) });
    renderPages(state);
});




    document.getElementById('next-page').addEventListener('click', () => {
    if (state.currentPage >= state.pdfDoc.numPages) return;

    let newPage;

    if (shouldRenderTwoPages(state) && state.currentPage === state.pdfDoc.numPages - 2) {
        newPage = state.pdfDoc.numPages;
    } else {
        newPage = shouldRenderTwoPages(state) ? state.currentPage + 2 : state.currentPage + 1;
    }

    updateState({ currentPage: Math.min(state.pdfDoc.numPages, newPage) });
    renderPages(state);
});


    document.getElementById('go-to-page').addEventListener('click', () => {
        const input = document.getElementById('page-input');
        const n = parseInt(input.value);
        if (n > 0 && n <= state.pdfDoc.numPages) {
            updateState({ currentPage: n });
            renderPages(state);
        }
    });

    document.getElementById('zoom-select').addEventListener('change', (e) => {
        // Disable tag after its been used
        document.getElementById('zoom-select').disabled = true;
        // Re-enable it after a short delay
        setTimeout(() => {
            document.getElementById('zoom-select').disabled = false;
        }, 100);
        updateState({ scale: parseFloat(e.target.value) });
        renderPages(state);
    });

    document.getElementById('prev-page-mobile').addEventListener('click', () => {
        if (state.currentPage <= 1) return;
        updateState({ currentPage: state.currentPage - 1 });
        renderPages(state);
    });

    document.getElementById('next-page-mobile').addEventListener('click', () => {
        if (state.currentPage >= state.pdfDoc.numPages) return;
        updateState({ currentPage: state.currentPage + 1 });
        renderPages(state);
    });

    // Add keyboard navigation
    document.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowLeft') {
            document.getElementById('prev-page').click();
        } else if (e.key === 'ArrowRight') {
            document.getElementById('next-page').click();
        }
    });
}