import { renderPages } from './pageRenderer.js';
import { updateState, preloadNeighborPages } from './pdfViewer.js';

const ZOOM_STEPS = [0.5, 0.75, 1, 1.25, 1.5, 2];
const SWIPE_THRESHOLD = 50;
const SWIPE_RATIO = 1.4;

export function setupEventListeners(state) {
    document.getElementById('prev-page')?.addEventListener('click', () => navigatePrev(state));
    document.getElementById('next-page')?.addEventListener('click', () => navigateNext(state));

    setupPageInput(state);
    setupZoomControls(state);
    setupFullscreen(state);
    setupKeyboard(state);
    setupTouchSwipe(state);
}

function setupPageInput(state) {
    const form = document.getElementById('page-jump-form');
    const input = document.getElementById('page-input');
    if (!form || !input) return;

    const commit = () => {
        const n = parseInt(input.value, 10);
        if (!state.pdfDoc || Number.isNaN(n)) {
            syncInputFromState(state);
            return;
        }
        const target = normalizeTargetPage(n, state);
        if (target === state.currentPage) {
            syncInputFromState(state);
            return;
        }
        const direction = target > state.currentPage ? 'next' : 'prev';
        updateState({ currentPage: target });
        renderPages(state, { direction });
        preloadNeighborPages(state);
    };

    input.addEventListener('focus', () => input.select());
    input.addEventListener('blur', commit);
    form.addEventListener('submit', (e) => {
        e.preventDefault();
        input.blur();
    });
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            syncInputFromState(state);
            input.blur();
        }
    });
}

function syncInputFromState(state) {
    const input = document.getElementById('page-input');
    if (!input || !state.pdfDoc) return;
    input.value = String(state.currentPage);
}

function setupZoomControls(state) {
    document.getElementById('zoom-in')?.addEventListener('click', () => stepZoom(state, +1));
    document.getElementById('zoom-out')?.addEventListener('click', () => stepZoom(state, -1));
}

function stepZoom(state, delta) {
    const currentIdx = closestZoomIndex(state.scale);
    const nextIdx = Math.min(ZOOM_STEPS.length - 1, Math.max(0, currentIdx + delta));
    const nextScale = ZOOM_STEPS[nextIdx];
    if (nextScale === state.scale) return;
    updateState({ scale: nextScale });
    renderPages(state, { skipAnimation: true });
}

function closestZoomIndex(scale) {
    let bestIdx = 0;
    let bestDiff = Infinity;
    ZOOM_STEPS.forEach((z, i) => {
        const d = Math.abs(z - scale);
        if (d < bestDiff) {
            bestDiff = d;
            bestIdx = i;
        }
    });
    return bestIdx;
}

function setupFullscreen(state) {
    document.getElementById('fullscreen-toggle')?.addEventListener('click', () => toggleFullscreen(state));
    document.addEventListener('fullscreenchange', updateFullscreenButton);
}

function toggleFullscreen(state) {
    const el = state.shellElement || document.documentElement;
    if (!document.fullscreenElement) {
        if (el.requestFullscreen) {
            el.requestFullscreen().catch((err) => console.warn('Fullscreen denied:', err));
        }
    } else if (document.exitFullscreen) {
        document.exitFullscreen();
    }
}

function updateFullscreenButton() {
    const btn = document.getElementById('fullscreen-toggle');
    const icon = btn?.querySelector('i');
    if (!icon) return;
    icon.className = document.fullscreenElement ? 'las la-compress' : 'las la-expand';
}

function setupKeyboard(state) {
    document.addEventListener('keydown', (e) => {
        if (!state.pdfDoc) return;
        const tag = (e.target.tagName || '').toLowerCase();
        if (tag === 'input' || tag === 'select' || tag === 'textarea' || e.target.isContentEditable) {
            return;
        }
        const numPages = state.pdfDoc.numPages;

        switch (e.key) {
            case 'ArrowLeft':
            case 'PageUp':
                e.preventDefault();
                navigatePrev(state);
                break;
            case 'ArrowRight':
            case 'PageDown':
            case ' ':
                e.preventDefault();
                navigateNext(state);
                break;
            case 'Home':
                e.preventDefault();
                if (state.currentPage !== 1) {
                    updateState({ currentPage: 1 });
                    renderPages(state, { direction: 'prev' });
                    preloadNeighborPages(state);
                }
                break;
            case 'End': {
                e.preventDefault();
                const target = normalizeTargetPage(numPages, state);
                if (state.currentPage !== target) {
                    updateState({ currentPage: target });
                    renderPages(state, { direction: 'next' });
                    preloadNeighborPages(state);
                }
                break;
            }
            case 'f':
            case 'F':
                toggleFullscreen(state);
                break;
            case '+':
            case '=':
                e.preventDefault();
                stepZoom(state, +1);
                break;
            case '-':
            case '_':
                e.preventDefault();
                stepZoom(state, -1);
                break;
        }
    });
}

function setupTouchSwipe(state) {
    const stage = document.querySelector('.pdf-stage');
    if (!stage) return;

    let startX = null;
    let startY = null;
    let startTime = 0;

    stage.addEventListener('touchstart', (e) => {
        if (e.touches.length !== 1) {
            startX = null;
            return;
        }
        startX = e.touches[0].clientX;
        startY = e.touches[0].clientY;
        startTime = Date.now();
    }, { passive: true });

    stage.addEventListener('touchend', (e) => {
        if (startX === null) return;
        const touch = e.changedTouches[0];
        const dx = touch.clientX - startX;
        const dy = touch.clientY - startY;
        const elapsed = Date.now() - startTime;
        startX = null;
        if (elapsed > 600) return;
        if (Math.abs(dx) < SWIPE_THRESHOLD) return;
        if (Math.abs(dx) < Math.abs(dy) * SWIPE_RATIO) return;
        if (dx < 0) navigateNext(state);
        else navigatePrev(state);
    }, { passive: true });

    stage.addEventListener('touchcancel', () => { startX = null; }, { passive: true });
}

function navigatePrev(state) {
    if (!state.pdfDoc || state.currentPage <= 1) return;
    const numPages = state.pdfDoc.numPages;
    const twoPage = state.pagesPerView === 2;

    let newPage;
    if (state.currentPage === numPages && twoPage) {
        newPage = Math.max(2, state.currentPage - 2);
    } else if (twoPage && state.currentPage > 2) {
        newPage = state.currentPage - 2;
    } else {
        newPage = state.currentPage - 1;
    }
    newPage = Math.max(1, newPage);
    if (newPage === state.currentPage) return;
    updateState({ currentPage: newPage });
    renderPages(state, { direction: 'prev' });
    preloadNeighborPages(state);
}

function navigateNext(state) {
    if (!state.pdfDoc || state.currentPage >= state.pdfDoc.numPages) return;
    const numPages = state.pdfDoc.numPages;
    const inPair = state.pagesPerView === 2 && state.currentPage > 1 && state.currentPage < numPages;

    // 2-page PDFs in two-page mode show both pages as a single spread, so
    // there's nothing to navigate to.
    if (state.pagesPerView === 2 && numPages === 2) return;

    // The current spread already covers the last page when currentPage + 1
    // >= numPages — true for odd-paginated PDFs at the final spread (e.g.
    // pages 2,3 of a 3-page PDF). Flipping forward would only reveal a
    // back-cover view that duplicates the page just shown on the right.
    if (inPair && state.currentPage + 1 >= numPages) return;

    let newPage;
    if (inPair && state.currentPage === numPages - 2) {
        newPage = numPages;
    } else if (inPair) {
        newPage = state.currentPage + 2;
    } else {
        newPage = state.currentPage + 1;
    }
    newPage = Math.min(numPages, newPage);
    if (newPage === state.currentPage) return;
    updateState({ currentPage: newPage });
    renderPages(state, { direction: 'next' });
    preloadNeighborPages(state);
}

/**
 * Snap a requested page number to a position the two-page layout can render
 * without producing a redundant back-cover view. Valid two-page positions:
 *   1                               (cover-right)
 *   2, 4, 6, … up to numPages-1     (spread starts on even pages)
 *   numPages, only if even          (cover-left / back-cover view)
 * For odd numPages, a target of numPages snaps down to numPages-1 so the
 * final spread (numPages-1, numPages) is shown instead of the last page
 * alone.
 */
function normalizeTargetPage(target, state) {
    const numPages = state.pdfDoc.numPages;
    const clamped = Math.min(Math.max(1, target), numPages);
    if (state.pagesPerView !== 2) return clamped;
    // 2-page PDFs always render as a single (1, 2) spread — pin to 1.
    if (numPages === 2) return 1;
    if (clamped === 1) return 1;
    if (clamped === numPages && numPages % 2 === 0) return clamped;
    return clamped % 2 === 0 ? clamped : clamped - 1;
}
