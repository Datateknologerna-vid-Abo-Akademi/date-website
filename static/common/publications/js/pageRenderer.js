import { getSpreadLayout } from './spreadLayout.js';

let pageRendering = false;
let pendingRender = null;

const FLIP_DURATION_MS = 750;
const SHUFFLE_DURATION_MS = 350;

export async function renderPages(state, options = {}) {
    const direction = options.direction || 'none';
    const skipAnimation = options.skipAnimation === true || direction === 'none';

    if (pageRendering) {
        pendingRender = { state, options };
        return;
    }
    pageRendering = true;

    try {
        const newSpread = await buildSpread(state);
        if (!newSpread) return;

        // Remove any orphan animation elements from interrupted flips.
        state.viewerElement
            .querySelectorAll('.page-flipper-row, .page-flipper, .page-spread-hybrid, .page-shuffle')
            .forEach((el) => el.remove());
        const existingSpread = state.viewerElement.querySelector('.page-spread:not(.page-spread-hybrid)');

        if (skipAnimation || !existingSpread) {
            if (existingSpread) existingSpread.remove();
            state.viewerElement.appendChild(newSpread);
            return;
        }

        if (state.pagesPerView === 1) {
            runSinglePageShuffle(state, existingSpread, newSpread, direction);
        } else {
            runTwoPageFlip(state, existingSpread, newSpread, direction);
        }
    } finally {
        pageRendering = false;
        if (pendingRender) {
            const next = pendingRender;
            pendingRender = null;
            renderPages(next.state, next.options);
        }
    }
}

/**
 * Build the destination spread element. In desktop (two-page) mode, the
 * cover (page 1) lives in the right slot with an empty placeholder on its
 * left, and the last page lives in the left slot — so navigating away from
 * either gives the natural "open the book" / "close the book" motion when
 * the flipper rotates around the spine.
 */
async function buildSpread(state) {
    const spread = document.createElement('div');
    spread.className = 'page-spread';

    const layout = getSpreadLayout(state);

    try {
        if (layout.type === 'single') {
            spread.appendChild(await renderPage(state, layout.leftPage));
        } else if (layout.type === 'cover-right') {
            const rightCanvas = await renderPage(state, layout.rightPage);
            spread.appendChild(buildEmptySlot(rightCanvas));
            spread.appendChild(rightCanvas);
        } else if (layout.type === 'cover-left') {
            const leftCanvas = await renderPage(state, layout.leftPage);
            spread.appendChild(leftCanvas);
            spread.appendChild(buildEmptySlot(leftCanvas));
        } else {
            const [leftCanvas, rightCanvas] = await Promise.all([
                renderPage(state, layout.leftPage),
                renderPage(state, layout.rightPage),
            ]);
            spread.appendChild(leftCanvas);
            spread.appendChild(rightCanvas);
        }
        return spread;
    } catch (error) {
        console.error('Error rendering pages:', error);
        showErrorMessage(state, 'Failed to render PDF pages. Please try again.');
        return null;
    }
}

/**
 * Single-page mode (mobile) uses a card-shuffle slide instead of the book
 * flip — the rotateY animation reads as "turning a stiff page" which is at
 * odds with the touch-swipe gesture mobile users actually use. Old card
 * slides off in the navigation direction, new card slides in from the
 * opposite side, both moving together.
 */
function runSinglePageShuffle(state, existingSpread, newSpread, direction) {
    const oldCanvas = existingSpread.querySelector('canvas');
    const newCanvas = newSpread.querySelector('canvas');
    if (!oldCanvas || !newCanvas) {
        existingSpread.remove();
        state.viewerElement.appendChild(newSpread);
        return;
    }

    const shuffle = document.createElement('div');
    shuffle.className = `page-shuffle page-shuffle-${direction}`;

    const oldCard = document.createElement('div');
    oldCard.className = 'page-shuffle-card page-shuffle-old';
    oldCard.appendChild(cloneCanvas(oldCanvas));

    const newCard = document.createElement('div');
    newCard.className = 'page-shuffle-card page-shuffle-new';
    newCard.appendChild(cloneCanvas(newCanvas));

    shuffle.appendChild(oldCard);
    shuffle.appendChild(newCard);

    existingSpread.remove();
    state.viewerElement.appendChild(newSpread);
    state.viewerElement.appendChild(shuffle);

    triggerShuffle(shuffle, () => shuffle.remove());
}

function triggerShuffle(shuffle, cleanup) {
    // Force the initial transforms to commit before adding the trigger class.
    shuffle.getBoundingClientRect();
    requestAnimationFrame(() => {
        shuffle.classList.add('is-flipping');
    });

    let cleaned = false;
    const onEnd = () => {
        if (cleaned) return;
        cleaned = true;
        cleanup();
    };
    // Two cards transition; wait for whichever ends last (or the safety
    // timeout) before tearing down so we don't snap mid-slide.
    let endCount = 0;
    shuffle.addEventListener('transitionend', (e) => {
        if (e.propertyName !== 'transform') return;
        endCount += 1;
        if (endCount >= 2) onEnd();
    });
    setTimeout(onEnd, SHUFFLE_DURATION_MS + 200);
}

function runTwoPageFlip(state, existingSpread, newSpread, direction) {
    const oldSlots = getSlots(existingSpread);
    const newSlots = getSlots(newSpread);

    // Same model regardless of cover/spread/back-cover layout: one half
    // stays put in the hybrid, the other half is the flipping sheet whose
    // back becomes the new opposite-side page.
    let hybridLeft, hybridRight, flipperFront, flipperBack;
    // When flipping off the cover (or onto the back cover), the hybrid's
    // stationary slot is empty and would let the new page show through
    // underneath before the flipper has rotated to reveal it. Hide that
    // page until cleanup so the back face of the flipper is the only thing
    // the user sees emerging on that side.
    let maskedNewSlot = null;
    if (direction === 'next') {
        hybridLeft = oldSlots.left;
        hybridRight = newSlots.right;
        flipperFront = oldSlots.right;
        flipperBack = newSlots.left;
        if (!hybridLeft) maskedNewSlot = newSlots.left;
    } else {
        hybridLeft = newSlots.left;
        hybridRight = oldSlots.right;
        flipperFront = oldSlots.left;
        flipperBack = newSlots.right;
        if (!hybridRight) maskedNewSlot = newSlots.right;
    }

    if (!flipperFront || !flipperBack) {
        // Shouldn't happen given the navigation guards, but bail safely.
        existingSpread.remove();
        state.viewerElement.appendChild(newSpread);
        return;
    }

    const referenceCanvas =
        newSlots.left || newSlots.right || oldSlots.left || oldSlots.right;

    const hybrid = document.createElement('div');
    hybrid.className = 'page-spread page-spread-hybrid';
    hybrid.appendChild(hybridLeft ? cloneCanvas(hybridLeft) : buildEmptySlot(referenceCanvas));
    hybrid.appendChild(hybridRight ? cloneCanvas(hybridRight) : buildEmptySlot(referenceCanvas));

    const flipper = buildFlipper(cloneCanvas(flipperFront), cloneCanvas(flipperBack), direction);

    const flipperRow = document.createElement('div');
    flipperRow.className = `page-flipper-row page-flipper-row-${direction}`;
    const placeholder = buildPlaceholder(referenceCanvas);
    if (direction === 'next') {
        flipperRow.appendChild(placeholder);
        flipperRow.appendChild(flipper);
    } else {
        flipperRow.appendChild(flipper);
        flipperRow.appendChild(placeholder);
    }

    existingSpread.remove();
    state.viewerElement.appendChild(newSpread);
    state.viewerElement.appendChild(hybrid);
    state.viewerElement.appendChild(flipperRow);

    if (maskedNewSlot) maskedNewSlot.style.visibility = 'hidden';

    triggerFlip(flipper, () => {
        if (maskedNewSlot) maskedNewSlot.style.visibility = '';
        flipperRow.remove();
        hybrid.remove();
    });
}

function getSlots(spread) {
    const children = Array.from(spread.children);
    if (children.length === 1) {
        // Single-page (mobile) — only one slot, conventionally the left.
        return { left: children[0], right: null };
    }
    const leftEl = children[0] || null;
    const rightEl = children[1] || null;
    const isCanvas = (el) => el && el.tagName === 'CANVAS';
    return {
        left: isCanvas(leftEl) ? leftEl : null,
        right: isCanvas(rightEl) ? rightEl : null,
    };
}

function buildFlipper(frontCanvas, backCanvas, direction) {
    const flipper = document.createElement('div');
    flipper.className = `page-flipper page-flipper-${direction}`;

    const front = document.createElement('div');
    front.className = 'page-flipper-face page-flipper-front';
    front.appendChild(frontCanvas);

    const back = document.createElement('div');
    back.className = 'page-flipper-face page-flipper-back';
    back.appendChild(backCanvas);

    flipper.appendChild(front);
    flipper.appendChild(back);
    return flipper;
}

function buildPlaceholder(referenceCanvas) {
    const placeholder = document.createElement('div');
    placeholder.className = 'page-flipper-placeholder';
    if (referenceCanvas?.style.width) placeholder.style.width = referenceCanvas.style.width;
    if (referenceCanvas?.style.height) placeholder.style.height = referenceCanvas.style.height;
    return placeholder;
}

function buildEmptySlot(referenceCanvas) {
    const slot = document.createElement('div');
    slot.className = 'page-empty-slot';
    if (referenceCanvas?.style.width) slot.style.width = referenceCanvas.style.width;
    if (referenceCanvas?.style.height) slot.style.height = referenceCanvas.style.height;
    return slot;
}

function triggerFlip(flipper, cleanup) {
    // Force the browser to commit the initial transform before mutating.
    flipper.getBoundingClientRect();
    requestAnimationFrame(() => {
        flipper.classList.add('is-flipping');
    });

    let cleaned = false;
    const onEnd = () => {
        if (cleaned) return;
        cleaned = true;
        cleanup();
    };
    flipper.addEventListener('transitionend', (e) => {
        if (e.propertyName === 'transform') onEnd();
    });
    setTimeout(onEnd, FLIP_DURATION_MS + 200);
}

function cloneCanvas(src) {
    const clone = document.createElement('canvas');
    clone.className = src.className;
    clone.width = src.width;
    clone.height = src.height;
    clone.style.cssText = src.style.cssText;
    const ctx = clone.getContext('2d', { alpha: false });
    ctx.drawImage(src, 0, 0);
    return clone;
}

async function renderPage(state, pageNumber) {
    const page = await state.pdfDoc.getPage(pageNumber);
    const canvas = document.createElement('canvas');
    canvas.className = 'page-canvas';

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const fitScale = computeFitScale(state, page);
    const effectiveScale = state.scale * fitScale;
    const cssViewport = page.getViewport({ scale: effectiveScale });
    const renderViewport = page.getViewport({ scale: effectiveScale * dpr });

    canvas.width = Math.floor(renderViewport.width);
    canvas.height = Math.floor(renderViewport.height);
    canvas.style.width = `${cssViewport.width}px`;
    canvas.style.height = `${cssViewport.height}px`;

    const context = canvas.getContext('2d', { alpha: false });
    await page.render({ canvasContext: context, viewport: renderViewport }).promise;
    return canvas;
}

/**
 * Compute the scale at which a page fits the viewer width. state.scale acts
 * as a multiplier on top of this fit baseline, so scale=1 always means
 * "fit-to-viewport" (the natural default users expect) and scale=2 means
 * "twice as wide as fit" — the latter overflows and is scrollable via the
 * .pdf-stage's overflow:auto.
 */
function computeFitScale(state, page) {
    const viewer = state.viewerElement;
    if (!viewer) return 1;
    // page-spread gap (1.25rem ≈ 20px) only consumes width in two-page mode.
    const gap = state.pagesPerView === 2 ? 20 : 0;
    const cols = state.pagesPerView === 2 ? 2 : 1;
    const naturalWidth = page.getViewport({ scale: 1 }).width;
    const available = Math.max(0, viewer.clientWidth - gap);
    const fit = available / (cols * naturalWidth);
    // Clamp so a freakishly narrow viewport doesn't render a 5px-wide page
    // or, on the other side, a missing viewer width doesn't blow up to NaN.
    if (!Number.isFinite(fit) || fit <= 0) return 1;
    return Math.min(fit, 4);
}

function showErrorMessage(state, message) {
    const el = document.createElement('p');
    el.className = 'pdf-error';
    el.textContent = message;
    state.viewerElement.innerHTML = '';
    state.viewerElement.appendChild(el);
}
