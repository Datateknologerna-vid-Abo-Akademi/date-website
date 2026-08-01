import * as pdfjsLib from 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.5.136/pdf.min.mjs';

pdfjsLib.GlobalWorkerOptions.workerSrc =
    'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.5.136/pdf.worker.min.mjs';

const MAX_CONCURRENT = 2;
const queue = [];
let active = 0;

function enqueue(task) {
    queue.push(task);
    pump();
}

function pump() {
    while (active < MAX_CONCURRENT && queue.length > 0) {
        const task = queue.shift();
        active += 1;
        task().finally(() => {
            active -= 1;
            pump();
        });
    }
}

async function renderThumbnail(card) {
    const url = card.dataset.pdfUrl;
    const canvas = card.querySelector('.publication-thumb-canvas');
    if (!url || !canvas) return;

    let loadingTask;
    try {
        loadingTask = pdfjsLib.getDocument({ url, disableAutoFetch: true, disableStream: false });
        const pdf = await loadingTask.promise;
        const page = await pdf.getPage(1);

        const container = canvas.parentElement;
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        const targetCssWidth = container.clientWidth || 280;
        const baseViewport = page.getViewport({ scale: 1 });
        const scale = (targetCssWidth * dpr) / baseViewport.width;
        const viewport = page.getViewport({ scale });

        canvas.width = Math.floor(viewport.width);
        canvas.height = Math.floor(viewport.height);
        canvas.style.width = '100%';
        canvas.style.height = 'auto';

        const ctx = canvas.getContext('2d', { alpha: false });
        await page.render({ canvasContext: ctx, viewport }).promise;

        card.classList.add('thumb-loaded');

        pdf.cleanup();
        pdf.destroy();
    } catch (error) {
        console.warn('Publication thumbnail failed:', error);
        card.classList.add('thumb-failed');
        if (loadingTask) {
            try { await loadingTask.destroy(); } catch (_) { /* ignore */ }
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const cards = document.querySelectorAll('.publication-card[data-pdf-url]');
    if (!cards.length) return;

    if (!('IntersectionObserver' in window)) {
        cards.forEach((card) => enqueue(() => renderThumbnail(card)));
        return;
    }

    const observer = new IntersectionObserver(
        (entries) => {
            for (const entry of entries) {
                if (entry.isIntersecting) {
                    const card = entry.target;
                    observer.unobserve(card);
                    enqueue(() => renderThumbnail(card));
                }
            }
        },
        { rootMargin: '300px 0px' }
    );

    cards.forEach((card) => observer.observe(card));
});
