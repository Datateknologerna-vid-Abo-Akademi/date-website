function setExternalLinksOpenInNewTab() {
    const currentURL = new URL(document.URL);
    document.querySelectorAll('a[href]').forEach((elem) => {
        const rawHref = (elem.getAttribute('href') || '').trim();
        if (!rawHref || rawHref.startsWith('#')) return;

        let linkHref;
        try {
            linkHref = new URL(rawHref, document.baseURI);
        } catch (err) {
            return;
        }

        if (!['http:', 'https:'].includes(linkHref.protocol)) return;

        if (currentURL.origin !== linkHref.origin) {
            elem.target = '_blank';
            elem.rel = 'noopener noreferrer';
        }
    });
}

setExternalLinksOpenInNewTab();
