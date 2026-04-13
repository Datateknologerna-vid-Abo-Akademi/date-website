(() => {
    const galleryConfig = document.getElementById('gallery-config');
    const albumTotalCount = parseInt(galleryConfig?.dataset.albumTotalCount || '0', 10);
    const counterPageLabel = galleryConfig?.dataset.counterPageLabel || 'Sida';
    const counterImageLabel = galleryConfig?.dataset.counterImageLabel || 'Bild';
    const shareActionLabel = galleryConfig?.dataset.shareActionLabel || 'Dela eller kopiera länk';
    const shareWorkingLabel = galleryConfig?.dataset.shareWorkingLabel || 'Delar...';
    const shareSuccessLabel = galleryConfig?.dataset.shareSuccessLabel || 'Länk delad';
    const copySuccessLabel = galleryConfig?.dataset.copySuccessLabel || 'Länk kopierad';
    const shareErrorLabel = galleryConfig?.dataset.shareErrorLabel || 'Kunde inte dela eller kopiera länk';
    const loadingMoreLabel = galleryConfig?.dataset.loadingMoreLabel || 'Laddar fler bilder...';
    const loadMoreErrorLabel = galleryConfig?.dataset.loadMoreErrorLabel || 'Kunde inte ladda fler bilder.';
    const downloadLabel = galleryConfig?.dataset.downloadLabel || 'Ladda ner aktuell bild';

    let nextFragmentUrl = (galleryConfig?.dataset.nextFragmentUrl || '').trim() || null;
    let isOpen = false;
    let closingViaPopstate = false;
    let isLoadingNextPage = false;
    let shareFeedbackTimer = null;
    let shareActionToken = 0;
    let loadMoreObserver = null;
    let scrollCheckQueued = false;
    let masonryGrid = null;
    let syncAfterLoadRequested = false;
    let masonryLayoutQueued = false;
    let masonryNeedsReload = false;
    let itemResizeObserver = null;

    const lightbox = GLightbox({
        selector: '.glightbox',
        touchNavigation: true,
        loop: false,
        keyboardNavigation: true,
        closeOnOutsideClick: true,
        zoomable: true,
        draggable: true,
    });

    const dlBtn = document.createElement('a');
    dlBtn.id = 'lightbox-dl-btn';
    dlBtn.innerHTML = '<i class="fas fa-download"></i>';
    dlBtn.setAttribute('download', '');
    dlBtn.setAttribute('aria-label', downloadLabel);
    dlBtn.setAttribute('title', downloadLabel);
    dlBtn.style.display = 'none';
    document.body.appendChild(dlBtn);

    const shareBtn = document.createElement('button');
    shareBtn.id = 'lightbox-share-btn';
    shareBtn.type = 'button';
    shareBtn.innerHTML = '<i class="fas fa-link"></i>';
    shareBtn.setAttribute('aria-label', shareActionLabel);
    shareBtn.setAttribute('title', shareActionLabel);
    shareBtn.style.display = 'none';
    document.body.appendChild(shareBtn);

    const shareFeedback = document.createElement('div');
    shareFeedback.id = 'lightbox-share-feedback';
    shareFeedback.setAttribute('role', 'status');
    shareFeedback.setAttribute('aria-live', 'polite');
    shareFeedback.style.display = 'none';
    document.body.appendChild(shareFeedback);

    const lbCounter = document.createElement('div');
    lbCounter.id = 'lightbox-counter';
    lbCounter.setAttribute('aria-live', 'polite');
    lbCounter.style.display = 'none';
    document.body.appendChild(lbCounter);

    const grid = document.getElementById('photo-grid');
    const galleryLoading = document.getElementById('gallery-loading');
    const gallerySentinel = document.getElementById('gallery-sentinel');
    const galleryPaginationFallback = document.getElementById('gallery-pagination-fallback');
    const urlParams = new URLSearchParams(window.location.search);
    const requestedOpenAt = parseInt(urlParams.get('lightbox') || '', 10);
    let pendingOpenIndex = Number.isInteger(requestedOpenAt) && requestedOpenAt >= 1 ? requestedOpenAt : null;

    if (galleryPaginationFallback) {
        galleryPaginationFallback.hidden = true;
    }

    function setGalleryLoading(isLoading, message) {
        if (!galleryLoading) return;
        if (isLoading) {
            galleryLoading.hidden = false;
            galleryLoading.textContent = message || loadingMoreLabel;
        } else {
            galleryLoading.hidden = true;
            galleryLoading.textContent = '';
        }
    }

    function getGridItems() {
        return grid.querySelectorAll('.grid-item');
    }

    function getLoadedItemCount() {
        return getGridItems().length;
    }

    function getItemImages(items) {
        return items.flatMap((item) => Array.from(item.querySelectorAll('.gallery-image')));
    }

    function markImagesEager(images, options = {}) {
        const { highPriorityCount = 0 } = options;

        images.forEach((image, index) => {
            image.loading = 'eager';
            image.decoding = 'async';

            if ('fetchPriority' in image) {
                image.fetchPriority = index < highPriorityCount ? 'high' : 'auto';
            }
        });
    }

    function queueMasonryLayout(options = {}) {
        const { reloadItems = false } = options;
        if (!masonryGrid) return;

        masonryNeedsReload = masonryNeedsReload || reloadItems;
        if (masonryLayoutQueued) return;

        masonryLayoutQueued = true;
        window.requestAnimationFrame(() => {
            masonryLayoutQueued = false;

            if (!masonryGrid) {
                masonryNeedsReload = false;
                return;
            }

            if (masonryNeedsReload) {
                masonryGrid.masonry('reloadItems');
            }

            masonryGrid.masonry('layout');
            masonryNeedsReload = false;
        });
    }

    function stabilizeMasonryLayout(options = {}) {
        queueMasonryLayout(options);
        window.requestAnimationFrame(() => queueMasonryLayout(options));
        window.setTimeout(() => queueMasonryLayout(options), 90);
        window.setTimeout(() => queueMasonryLayout(options), 240);
        window.setTimeout(() => queueMasonryLayout(options), 520);
    }

    function observeGridItems(items) {
        if (!('ResizeObserver' in window) || !items.length) return;

        if (!itemResizeObserver) {
            itemResizeObserver = new ResizeObserver(() => {
                stabilizeMasonryLayout();
            });
        }

        items.forEach((item) => itemResizeObserver.observe(item));
    }

    function preloadImageSource(src, timeoutMs) {
        return new Promise((resolve) => {
            if (!src) {
                resolve(false);
                return;
            }

            let finished = false;
            let timerId = null;
            const preloader = new Image();

            const done = (loaded) => {
                if (finished) return;
                finished = true;
                if (timerId) {
                    window.clearTimeout(timerId);
                }
                preloader.onload = null;
                preloader.onerror = null;
                resolve(loaded);
            };

            preloader.decoding = 'async';
            preloader.onload = () => done(true);
            preloader.onerror = () => done(false);
            timerId = window.setTimeout(() => done(false), timeoutMs);
            preloader.src = src;
        });
    }

    async function preloadGridItems(items, options = {}) {
        const { timeoutMs = 2400 } = options;
        const images = getItemImages(items);

        if (!images.length) return;

        markImagesEager(images, { highPriorityCount: 4 });
        await Promise.all(images.map((image) => preloadImageSource(image.currentSrc || image.src, timeoutMs)));
    }

    function getCurrentGridItem() {
        return getGridItems()[lightbox.index];
    }

    function syncLightboxElements() {
        const gridCount = getGridItems().length;
        const lightboxCount = lightbox.elements ? lightbox.elements.length : 0;
        if (gridCount === lightboxCount) return;

        if (isLoadingNextPage) {
            syncAfterLoadRequested = true;
            return;
        }

        const parsedElements = lightbox.getElements();
        const parsedCount = parsedElements.length;
        const activeIndex = Math.min(lightbox.index || 0, Math.max(parsedCount - 1, 0));
        const canAppendSlides = lightboxCount > 0 && parsedCount > lightboxCount && parsedCount === gridCount;

        if (canAppendSlides) {
            parsedElements.slice(lightboxCount).forEach((element, offset) => {
                lightbox.insertSlide(element.slideConfig || element, lightboxCount + offset);
            });
        } else {
            lightbox.setElements(parsedElements);
            if (isOpen && parsedCount) {
                lightbox.goToSlide(activeIndex);
            }
        }

        syncAfterLoadRequested = false;

        if (isOpen && lightbox.elements?.length) {
            updateDlBtn();
            updateCounter();
        }
    }

    function getCurrentGlobalIndex() {
        const currentItem = getCurrentGridItem();
        const globalIndex = parseInt(currentItem?.dataset.globalIndex || '', 10);
        return Number.isNaN(globalIndex) ? lightbox.index + 1 : globalIndex;
    }

    function updateDlBtn() {
        const el = lightbox.elements[lightbox.index];
        if (el?.href) dlBtn.href = el.href;
    }

    function updateCounter() {
        if (!lightbox.elements?.length) return;
        const localIndex = lightbox.index + 1;
        const globalIndex = getCurrentGlobalIndex();
        const fullCounterText = `${counterPageLabel} ${localIndex}/${lightbox.elements.length} · ${counterImageLabel} ${globalIndex}/${albumTotalCount}`;
        lbCounter.setAttribute('aria-label', fullCounterText);
        lbCounter.textContent = window.matchMedia('(max-width: 575px)').matches ? `${globalIndex}/${albumTotalCount}` : fullCounterText;
    }

    function showDlBtn() {
        dlBtn.style.display = 'flex';
    }

    function hideDlBtn() {
        dlBtn.style.display = 'none';
    }

    function showShareBtn() {
        shareBtn.style.display = 'flex';
    }

    function hideShareBtn() {
        shareBtn.style.display = 'none';
        shareFeedback.style.display = 'none';
    }

    function showCounter() {
        lbCounter.style.display = 'inline-flex';
    }

    function hideCounter() {
        lbCounter.style.display = 'none';
    }

    function clearShareFeedbackTimer() {
        if (shareFeedbackTimer) {
            window.clearTimeout(shareFeedbackTimer);
            shareFeedbackTimer = null;
        }
    }

    function resetShareFeedback() {
        setShareVisualState('idle');
        shareFeedback.style.display = 'none';
        shareFeedback.classList.remove('ok', 'fail');
    }

    function setShareVisualState(state) {
        shareBtn.classList.remove('copying', 'copied-ok', 'copied-fail');

        if (state === 'copying') {
            shareBtn.classList.add('copying');
            shareBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            shareBtn.setAttribute('title', shareWorkingLabel);
            shareBtn.setAttribute('aria-label', shareWorkingLabel);
        } else if (state === 'success') {
            shareBtn.classList.add('copied-ok');
            shareBtn.innerHTML = '<i class="fas fa-check"></i>';
            shareBtn.setAttribute('title', copySuccessLabel);
            shareBtn.setAttribute('aria-label', copySuccessLabel);
        } else if (state === 'error') {
            shareBtn.classList.add('copied-fail');
            shareBtn.innerHTML = '<i class="fas fa-times"></i>';
            shareBtn.setAttribute('title', shareErrorLabel);
            shareBtn.setAttribute('aria-label', shareErrorLabel);
        } else {
            shareBtn.innerHTML = '<i class="fas fa-link"></i>';
            shareBtn.setAttribute('title', shareActionLabel);
            shareBtn.setAttribute('aria-label', shareActionLabel);
        }
    }

    async function copyShareLink(shareHref) {
        try {
            await navigator.clipboard.writeText(shareHref);
            return true;
        } catch (err) {
            const textArea = document.createElement('textarea');
            textArea.value = shareHref;
            textArea.setAttribute('readonly', '');
            textArea.style.position = 'absolute';
            textArea.style.left = '-9999px';
            document.body.appendChild(textArea);
            textArea.select();
            const copied = document.execCommand('copy');
            document.body.removeChild(textArea);
            return copied;
        }
    }

    async function shareCurrentLink() {
        const shareUrl = new URL(window.location.href);
        shareUrl.searchParams.set('lightbox', String(getCurrentGlobalIndex()));
        const shareHref = shareUrl.toString();

        if (navigator.share) {
            try {
                await navigator.share({ title: document.title, url: shareHref });
                return { success: true, mode: 'native' };
            } catch (err) {
                if (err && err.name === 'AbortError') {
                    return { success: false, cancelled: true };
                }
            }
        }

        const copied = await copyShareLink(shareHref);
        return { success: copied, mode: 'copy' };
    }

    function flashShareButton(result) {
        setShareVisualState(result.success ? 'success' : 'error');
        shareFeedback.textContent = result.success
            ? (result.mode === 'native' ? shareSuccessLabel : copySuccessLabel)
            : shareErrorLabel;
        shareFeedback.classList.remove('ok', 'fail');
        shareFeedback.classList.add(result.success ? 'ok' : 'fail');
        shareFeedback.style.display = 'inline-flex';

        clearShareFeedbackTimer();
        shareFeedbackTimer = window.setTimeout(() => {
            resetShareFeedback();
            shareFeedbackTimer = null;
        }, result.success ? 1800 : 1500);
    }

    shareBtn.addEventListener('click', async () => {
        const actionToken = ++shareActionToken;
        clearShareFeedbackTimer();
        setShareVisualState('copying');
        const result = await shareCurrentLink();

        if (actionToken !== shareActionToken) return;
        if (result.cancelled) {
            resetShareFeedback();
            return;
        }

        flashShareButton(result);
    });

    function openPendingLightbox() {
        if (!pendingOpenIndex) return false;

        const items = getGridItems();
        if (items.length < pendingOpenIndex) return false;

        const cleanUrl = new URL(window.location.href);
        cleanUrl.searchParams.delete('lightbox');
        history.replaceState({ lightboxBase: true }, '', cleanUrl);
        lightbox.openAt(pendingOpenIndex - 1);
        pendingOpenIndex = null;
        return true;
    }

    function markTargetImagePriority(globalIndex) {
        if (!globalIndex) return;
        const targetItem = grid.querySelector(`.grid-item[data-global-index="${globalIndex}"]`);
        const targetImg = targetItem ? targetItem.querySelector('.gallery-image') : null;
        if (!targetImg) return;

        targetImg.loading = 'eager';
        targetImg.fetchPriority = 'high';
    }

    function preloadTargetImage(globalIndex) {
        return new Promise((resolve) => {
            const targetItem = grid.querySelector(`.grid-item[data-global-index="${globalIndex}"]`);
            const targetImg = targetItem ? targetItem.querySelector('.gallery-image') : null;

            if (!targetImg || targetImg.complete) {
                resolve();
                return;
            }

            const src = targetImg.currentSrc || targetImg.src;
            if (!src) {
                resolve();
                return;
            }

            let finished = false;
            const done = () => {
                if (finished) return;
                finished = true;
                resolve();
            };

            const preloader = new Image();
            preloader.onload = done;
            preloader.onerror = done;
            preloader.src = src;

            window.setTimeout(done, 1400);
        });
    }

    async function loadNextPage($grid, options = {}) {
        if (!nextFragmentUrl || isLoadingNextPage) return false;

        const { advanceLightboxOnSuccess = false } = options;
        isLoadingNextPage = true;
        setGalleryLoading(true);
        let loadErrored = false;

        try {
            const response = await fetch(nextFragmentUrl, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const payload = await response.json();
            const fragment = document.createRange().createContextualFragment(payload.html);
            const appendedItems = Array.from(fragment.querySelectorAll('.grid-item'));

            await preloadGridItems(appendedItems);

            grid.appendChild(fragment);

            if (appendedItems.length) {
                observeGridItems(appendedItems);
                $grid.masonry('appended', appendedItems);
                stabilizeMasonryLayout({ reloadItems: true });

                // Keep listening in case a browser still finalizes dimensions after preload.
                $(appendedItems).imagesLoaded().progress(() => {
                    stabilizeMasonryLayout();
                });

                window.setTimeout(() => {
                    stabilizeMasonryLayout({ reloadItems: true });
                    syncLightboxElements();
                }, 80);
            }

            nextFragmentUrl = payload.has_next ? `?page=${payload.next_page}&fragment=1` : null;
            syncLightboxElements();

            if (advanceLightboxOnSuccess && isOpen && appendedItems.length && lightbox.elements?.length) {
                const nextIndex = Math.min(lightbox.index + 1, lightbox.elements.length - 1);
                if (nextIndex > lightbox.index) {
                    lightbox.goToSlide(nextIndex);
                }
            }

            if (pendingOpenIndex) {
                markTargetImagePriority(pendingOpenIndex);
            }

            window.requestAnimationFrame(() => maybeLoadMoreIfNeeded($grid));
            return payload.has_next;
        } catch (err) {
            loadErrored = true;
            setGalleryLoading(true, loadMoreErrorLabel);
            if (galleryPaginationFallback) {
                galleryPaginationFallback.hidden = false;
            }
            return false;
        } finally {
            isLoadingNextPage = false;
            if (syncAfterLoadRequested) {
                // Ensure new anchors are registered in GLightbox after batch append.
                syncLightboxElements();
            }
            if (!loadErrored) {
                setGalleryLoading(false);
            } else {
                window.setTimeout(() => setGalleryLoading(false), 2500);
            }
        }
    }

    function isSentinelNearViewport() {
        if (!gallerySentinel) return false;
        const sentinelRect = gallerySentinel.getBoundingClientRect();
        return sentinelRect.top <= window.innerHeight + 1200;
    }

    function maybeLoadMoreIfNeeded($grid) {
        if (!nextFragmentUrl || isLoadingNextPage) return;
        if (isSentinelNearViewport()) {
            loadNextPage($grid);
        }
    }

    async function loadMoreForViewerIfNeeded() {
        if (!isOpen || !nextFragmentUrl || isLoadingNextPage || !masonryGrid) return;

        const atOrNearEnd = lightbox.index >= Math.max(0, lightbox.elements.length - 10);
        if (!atOrNearEnd) return;

        await loadNextPage(masonryGrid);
    }

    function setupInfiniteScroll($grid) {
        if (!gallerySentinel || !nextFragmentUrl) return;

        const observerOptions = { rootMargin: '1200px 0px' };

        const queueViewportCheck = () => {
            if (scrollCheckQueued) return;
            scrollCheckQueued = true;
            window.requestAnimationFrame(() => {
                scrollCheckQueued = false;
                maybeLoadMoreIfNeeded($grid);
            });
        };

        window.addEventListener('scroll', queueViewportCheck, { passive: true });
        document.addEventListener('scroll', queueViewportCheck, { passive: true, capture: true });
        window.addEventListener('touchend', queueViewportCheck, { passive: true });
        window.addEventListener('touchmove', queueViewportCheck, { passive: true });
        window.addEventListener('resize', () => {
            queueViewportCheck();
            stabilizeMasonryLayout({ reloadItems: true });
        }, { passive: true });
        window.addEventListener('orientationchange', () => {
            queueViewportCheck();
            stabilizeMasonryLayout({ reloadItems: true });
        }, { passive: true });

        if ('IntersectionObserver' in window) {
            loadMoreObserver = new IntersectionObserver((entries) => {
                if (entries.some((entry) => entry.isIntersecting)) {
                    maybeLoadMoreIfNeeded($grid);
                }
            }, observerOptions);
            loadMoreObserver.observe(gallerySentinel);

            maybeLoadMoreIfNeeded($grid);
            return;
        }

        queueViewportCheck();
    }

    async function ensurePendingLightboxLoaded($grid) {
        while (pendingOpenIndex && getLoadedItemCount() < pendingOpenIndex && nextFragmentUrl) {
            const hasMore = await loadNextPage($grid);
            if (!hasMore) break;
        }

        if (pendingOpenIndex) {
            markTargetImagePriority(pendingOpenIndex);
            await preloadTargetImage(pendingOpenIndex);
        }

        openPendingLightbox();
    }

    lightbox.on('open', () => {
        syncLightboxElements();
        isOpen = true;
        showDlBtn();
        showShareBtn();
        showCounter();
        updateDlBtn();
        updateCounter();
        const url = new URL(window.location.href);
        url.searchParams.set('lightbox', String(getCurrentGlobalIndex()));
        history.pushState({ lightbox: true }, '', url);
        loadMoreForViewerIfNeeded();
    });

    lightbox.on('slide_changed', () => {
        updateDlBtn();
        updateCounter();
        const url = new URL(window.location.href);
        url.searchParams.set('lightbox', String(getCurrentGlobalIndex()));
        history.replaceState({ ...(history.state || {}), lightbox: true }, '', url);
        loadMoreForViewerIfNeeded();
    });

    lightbox.on('close', () => {
        isOpen = false;
        hideDlBtn();
        hideShareBtn();
        hideCounter();
        if (!closingViaPopstate && history.state && history.state.lightbox) {
            history.back();
        }
        closingViaPopstate = false;
    });

    window.addEventListener('popstate', () => {
        if (isOpen) {
            hideDlBtn();
            hideShareBtn();
            hideCounter();
            closingViaPopstate = true;
            lightbox.close();
        }
    });

    document.addEventListener('click', (e) => {
        if (e.target.closest('.gclose') || e.target.closest('.goverlay')) {
            hideDlBtn();
            hideShareBtn();
            hideCounter();
        }
    }, true);

    document.addEventListener('click', async (e) => {
        if (!isOpen || !e.target.closest('.gnext')) return;
        const atEnd = lightbox.index >= lightbox.elements.length - 1;
        if (!atEnd || !nextFragmentUrl || isLoadingNextPage || !masonryGrid) return;

        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();

        await loadNextPage(masonryGrid, { advanceLightboxOnSuccess: true });
    }, true);

    document.addEventListener('keydown', (e) => {
        if (isOpen && e.key === 'Escape') {
            hideDlBtn();
            hideShareBtn();
            hideCounter();
        }
    }, true);

    document.addEventListener('keydown', (e) => {
        if (!isOpen) return;
        if ((e.key === 'd' || e.key === 'D') && dlBtn.href) {
            dlBtn.click();
        }
    });

    document.addEventListener('keydown', async (e) => {
        if (!isOpen || e.key !== 'ArrowRight') return;
        const atEnd = lightbox.index >= lightbox.elements.length - 1;
        if (!atEnd || !nextFragmentUrl || isLoadingNextPage || !masonryGrid) return;

        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();

        await loadNextPage(masonryGrid, { advanceLightboxOnSuccess: true });
    });

    // GLightbox binds click handlers only to anchors known at init time.
    // Use delegation so images loaded later never fall through to /media/.
    grid.addEventListener('click', (e) => {
        const targetItem = e.target.closest('.grid-item.glightbox');
        if (!targetItem || !grid.contains(targetItem)) return;
        if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;

        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();

        syncLightboxElements();

        const targetIndex = Array.from(getGridItems()).indexOf(targetItem);
        if (targetIndex < 0) return;

        if (!lightbox.elements || lightbox.elements.length <= targetIndex) {
            lightbox.setElements(lightbox.getElements());
        }

        if (lightbox.elements?.length > targetIndex) {
            lightbox.openAt(targetIndex);
        }
    }, true);

    const gridGap = parseInt(getComputedStyle(grid).getPropertyValue('--gap')) || 6;
    const $grid = $('.grid');
    masonryGrid = $grid;

    markImagesEager(getItemImages(Array.from(getGridItems())), { highPriorityCount: 6 });
    observeGridItems(Array.from(getGridItems()));

    $grid.masonry({
        itemSelector: '.grid-item',
        columnWidth: '.grid-sizer',
        percentPosition: true,
        gutter: gridGap,
    });

    // Relayout as dimensions settle, even if the browser finishes decode later than expected.
    $grid.imagesLoaded().progress(() => {
        stabilizeMasonryLayout();
    });

    stabilizeMasonryLayout({ reloadItems: true });

    syncLightboxElements();
    setupInfiniteScroll($grid);

    if (pendingOpenIndex) {
        ensurePendingLightboxLoaded($grid);
    }
})();
