import { renderPages } from './pageRenderer.js';
import { updateState, shouldRenderTwoPages } from './pdfViewer.js';

export function setupEventListeners(state) {
    document.getElementById('prev-page').addEventListener('click', () => {
        if (state.currentPage <= 1) return;
        const newPage = shouldRenderTwoPages() ? state.currentPage - 2 : state.currentPage - 1;
        updateState({ currentPage: Math.max(1, newPage) });
        renderPages(state);
    });

    document.getElementById('next-page').addEventListener('click', () => {
        if (state.currentPage >= state.pdfDoc.numPages) return;
        const newPage = shouldRenderTwoPages() ? state.currentPage + 2 : state.currentPage + 1;
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