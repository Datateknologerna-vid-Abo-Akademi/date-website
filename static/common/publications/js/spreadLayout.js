export function getSpreadLayout(state, page = state.currentPage) {
    const numPages = state.pdfDoc.numPages;
    const normalizedPage = normalizeTargetPage(page, state);

    if (state.pagesPerView !== 2 || numPages === 1) {
        return {
            type: 'single',
            currentPage: normalizedPage,
            leftPage: normalizedPage,
            rightPage: null,
            isFirstSpread: normalizedPage <= 1,
            isLastSpread: normalizedPage >= numPages,
        };
    }

    if (numPages === 2) {
        return {
            type: 'spread',
            currentPage: 1,
            leftPage: 1,
            rightPage: 2,
            isFirstSpread: true,
            isLastSpread: true,
        };
    }

    if (normalizedPage === 1) {
        return {
            type: 'cover-right',
            currentPage: 1,
            leftPage: null,
            rightPage: 1,
            isFirstSpread: true,
            isLastSpread: false,
        };
    }

    if (normalizedPage === numPages && numPages % 2 === 0) {
        return {
            type: 'cover-left',
            currentPage: normalizedPage,
            leftPage: normalizedPage,
            rightPage: null,
            isFirstSpread: false,
            isLastSpread: true,
        };
    }

    const rightPage = Math.min(normalizedPage + 1, numPages);
    return {
        type: 'spread',
        currentPage: normalizedPage,
        leftPage: normalizedPage,
        rightPage,
        isFirstSpread: false,
        isLastSpread: rightPage >= numPages,
    };
}

export function normalizeTargetPage(target, state) {
    const numPages = state.pdfDoc.numPages;
    const clamped = Math.min(Math.max(1, target), numPages);
    if (state.pagesPerView !== 2) return clamped;
    if (numPages === 1) return 1;
    // 2-page PDFs always render as a single (1, 2) spread.
    if (numPages === 2) return 1;
    if (clamped === 1) return 1;
    if (clamped === numPages && numPages % 2 === 0) return clamped;
    return clamped % 2 === 0 ? clamped : clamped - 1;
}

export function getPreviousPagePosition(state) {
    const layout = getSpreadLayout(state);
    if (layout.isFirstSpread) return layout.currentPage;
    if (state.pagesPerView !== 2) return Math.max(1, layout.currentPage - 1);
    if (layout.type === 'cover-left') return normalizeTargetPage(layout.leftPage - 2, state);
    if (layout.leftPage <= 2) return 1;
    return normalizeTargetPage(layout.leftPage - 2, state);
}

export function getNextPagePosition(state) {
    const layout = getSpreadLayout(state);
    if (layout.isLastSpread) return layout.currentPage;
    if (state.pagesPerView !== 2) return Math.min(state.pdfDoc.numPages, layout.currentPage + 1);
    const nextPage = layout.rightPage ? layout.rightPage + 1 : layout.currentPage + 1;
    return normalizeTargetPage(nextPage, state);
}
