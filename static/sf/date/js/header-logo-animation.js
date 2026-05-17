(function () {
    var svgNs = 'http://www.w3.org/2000/svg';
    var svg = document.querySelector('.hero-text-box .albin svg');
    var paths = Array.prototype.slice.call(document.querySelectorAll('.hero-text-box .albin path'));
    if (!svg || !paths.length) return;

    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        svg.classList.add('is-ready');
        return;
    }

    var mainBodyPaths = [];
    var leafPaths = [];
    var letterPaths = [];
    var mottoPaths = [];
    var mainTraceSliceGroups = [];

    var sfLetterIds = createLookup(['path22', 'path23']);
    var mottoLetterIds = createLookup([
        'path24', 'path25', 'path26', 'path27', 'path28', 'path29', 'path30',
        'path31', 'path32', 'path33', 'path34', 'path35', 'path36', 'path37'
    ]);

    var viewBox = svg.viewBox && svg.viewBox.baseVal;
    var centerX = viewBox ? viewBox.x + (viewBox.width / 2) : 0;

    var strokeColor = 'var(--secondaryColor)';
    var finalFillColor = 'var(--secondaryColor)';
    var noFillColor = 'none';
    var lineCap = 'round';
    var lineJoin = 'round';
    var leafStrokeWidth = '0.5';
    var mainTraceStrokeWidth = '0.6';
    var sweepStrokeWidth = '0.5';
    var settledFillStrokeWidth = '0.4';

    var leafDrawDuration = 1080;
    var leafDrawDelayBase = 140;
    var leafDrawDelayStep = 42;
    var letterDrawDelayStep = 180;
    var mottoDrawDelayGap = 140;
    var mottoDrawDelayStep = 48;
    var mainTraceDelay = 120;
    var mainTraceSliceCount = 18;
    var mainTraceSliceStep = 48;
    var mainTraceSliceFadeDuration = 160;
    var sharedFillDuration = 560;
    var sharedFillOverlap = 120;

    var leafDistanceThreshold = viewBox ? viewBox.width * 0.2 : 0;
    var leafWidthThreshold = viewBox ? viewBox.width * 0.18 : 0;
    var leafHeightThreshold = viewBox ? viewBox.height * 0.18 : 0;
    var letterWidthMin = viewBox ? viewBox.width * 0.1 : 0;
    var letterWidthMax = viewBox ? viewBox.width * 0.16 : 0;
    var letterHeightMin = viewBox ? viewBox.height * 0.18 : 0;
    var letterHeightMax = viewBox ? viewBox.height * 0.28 : 0;
    var letterCenterDistanceMin = viewBox ? viewBox.width * 0.03 : 0;
    var letterCenterDistanceMax = viewBox ? viewBox.width * 0.16 : 0;

    function createLookup(ids) {
        var lookup = {};

        ids.forEach(function (id) {
            lookup[id] = true;
        });

        return lookup;
    }

    function createSvgNode(tagName) {
        return document.createElementNS(svgNs, tagName);
    }

    function setBasePathState(path) {
        path.style.opacity = '0';
        path.style.transformBox = 'fill-box';
        path.style.transformOrigin = 'center bottom';
    }

    function applyTraceStyles(path, len, strokeWidth) {
        path.style.fill = finalFillColor;
        path.style.fillOpacity = '0';
        path.style.stroke = strokeColor;
        path.style.strokeWidth = strokeWidth;
        path.style.strokeLinecap = lineCap;
        path.style.strokeLinejoin = lineJoin;
        path.style.strokeDasharray = len + ' ' + len;
        path.style.strokeDashoffset = len;
        path.style.opacity = '1';
    }

    function applyMainBodyStyles(path) {
        path.style.fill = finalFillColor;
        path.style.fillOpacity = '0';
        path.style.stroke = strokeColor;
        path.style.strokeOpacity = '0';
        path.style.strokeWidth = '0';
        path.style.strokeLinecap = lineCap;
        path.style.strokeLinejoin = lineJoin;
        path.style.opacity = '1';
    }

    function applySettledFillStroke(path) {
        path.style.stroke = strokeColor;
        path.style.strokeOpacity = '1';
        path.style.strokeWidth = settledFillStrokeWidth;
        path.style.strokeLinecap = lineCap;
        path.style.strokeLinejoin = lineJoin;
    }

    function createTraceEntry(path, bbox, len) {
        return {
            path: path,
            x: bbox.x,
            y: bbox.y + bbox.height,
            len: len
        };
    }

    function isLeafPath(bbox, pathCenterX) {
        return viewBox
            && Math.abs(pathCenterX - centerX) > leafDistanceThreshold
            && bbox.width < leafWidthThreshold
            && bbox.height < leafHeightThreshold;
    }

    function isCenterLetterPath(bbox, pathCenterX) {
        var centerDistance = Math.abs(pathCenterX - centerX);

        return viewBox
            && centerDistance > letterCenterDistanceMin
            && centerDistance < letterCenterDistanceMax
            && bbox.width > letterWidthMin
            && bbox.width < letterWidthMax
            && bbox.height > letterHeightMin
            && bbox.height < letterHeightMax;
    }

    function sortLeaves(a, b) {
        return (b.y - a.y) || (a.x - b.x);
    }

    function sortByX(a, b) {
        return a.x - b.x;
    }

    function createTraceKeyframes(len) {
        return [
            { opacity: 1, fillOpacity: 0, strokeDashoffset: len, transform: 'scale(0.94)' },
            { opacity: 1, fillOpacity: 0, strokeDashoffset: len * 0.68, transform: 'scale(0.96)', offset: 0.3 },
            { opacity: 1, fillOpacity: 0, strokeDashoffset: len * 0.34, transform: 'scale(0.985)', offset: 0.62 },
            { opacity: 1, fillOpacity: 0, strokeDashoffset: 0, transform: 'scale(1.015)', offset: 0.88 },
            { opacity: 1, fillOpacity: 0, strokeDashoffset: 0, transform: 'scale(1)' }
        ];
    }

    function animateTrace(path, len, delay) {
        var animation = path.animate(createTraceKeyframes(len), {
            duration: leafDrawDuration,
            delay: delay,
            easing: 'linear',
            fill: 'forwards'
        });

        animation.onfinish = function () {
            path.style.opacity = '1';
            path.style.fillOpacity = '0';
            path.style.transform = 'scale(1)';
            path.style.removeProperty('stroke-dasharray');
            path.style.removeProperty('stroke-dashoffset');
        };
    }

    function createFillKeyframes(keepSettledStroke, strokeStartWidth) {
        if (!keepSettledStroke) {
            return [
                { fillOpacity: 0 },
                { fillOpacity: 1 }
            ];
        }

        return [
            { fillOpacity: 0, strokeOpacity: strokeStartWidth === '0' ? 0 : 1, strokeWidth: strokeStartWidth },
            { fillOpacity: 0.86, strokeOpacity: 1, strokeWidth: settledFillStrokeWidth, offset: 0.78 },
            { fillOpacity: 1, strokeOpacity: 1, strokeWidth: settledFillStrokeWidth }
        ];
    }

    function animateFill(path, delay, keepSettledStroke, strokeStartWidth) {
        var animation = path.animate(createFillKeyframes(keepSettledStroke, strokeStartWidth || settledFillStrokeWidth), {
            duration: sharedFillDuration,
            delay: delay,
            easing: 'cubic-bezier(.2,.7,.2,1)',
            fill: 'forwards'
        });

        animation.onfinish = function () {
            path.style.fill = finalFillColor;
            path.style.fillOpacity = '1';

            if (keepSettledStroke) {
                applySettledFillStroke(path);
            }
        };
    }

    function animateTracedEntries(entries, baseDelay, step, fillDelay, keepSettledStroke, strokeStartWidth) {
        entries.forEach(function (entry, index) {
            var drawDelay = baseDelay + (index * step);

            animateTrace(entry.path, entry.len, drawDelay);
            animateFill(entry.path, fillDelay, keepSettledStroke, strokeStartWidth);
        });
    }

    function getSeriesLastStart(baseDelay, step, count) {
        return baseDelay + (Math.max(count - 1, 0) * step);
    }

    function getSeriesEnd(baseDelay, step, count, duration) {
        return getSeriesLastStart(baseDelay, step, count) + duration;
    }

    function appendCloneWithAncestorTransforms(targetGroup, sourcePath, decorateClone) {
        var clone = sourcePath.cloneNode(false);
        var ancestor = sourcePath.parentNode;
        var currentTarget = targetGroup;
        var transforms = [];

        clone.removeAttribute('class');
        if (decorateClone) decorateClone(clone);

        while (ancestor && ancestor !== svg) {
            if (ancestor.nodeType === 1 && ancestor.hasAttribute('transform')) {
                transforms.unshift(ancestor.getAttribute('transform'));
            }
            ancestor = ancestor.parentNode;
        }

        transforms.forEach(function (transformValue) {
            var wrapper = createSvgNode('g');
            wrapper.setAttribute('transform', transformValue);
            currentTarget.appendChild(wrapper);
            currentTarget = wrapper;
        });

        currentTarget.appendChild(clone);
        return clone;
    }

    function buildSweepLayer(defs) {
        var gradient = createSvgNode('linearGradient');
        var clipPath = createSvgNode('clipPath');
        var clipRect = createSvgNode('rect');
        var sweepGroup = createSvgNode('g');
        var sweepWidth = viewBox.width * 0.28;
        var sweepId = 'sf-logo-sweep';
        var clipId = 'sf-logo-sweep-clip';

        gradient.setAttribute('id', sweepId);
        gradient.setAttribute('gradientUnits', 'userSpaceOnUse');
        gradient.setAttribute('x1', '0');
        gradient.setAttribute('y1', String(viewBox.y));
        gradient.setAttribute('x2', String(viewBox.width));
        gradient.setAttribute('y2', String(viewBox.y));

        [
            { offset: '0%', color: '#ffffff', opacity: '0' },
            { offset: '42%', color: '#ffffff', opacity: '0' },
            { offset: '50%', color: '#ffffff', opacity: '0.55' },
            { offset: '58%', color: '#ffffff', opacity: '0' },
            { offset: '100%', color: '#ffffff', opacity: '0' }
        ].forEach(function (stopDef) {
            var stop = createSvgNode('stop');
            stop.setAttribute('offset', stopDef.offset);
            stop.setAttribute('stop-color', stopDef.color);
            stop.setAttribute('stop-opacity', stopDef.opacity);
            gradient.appendChild(stop);
        });

        clipPath.setAttribute('id', clipId);
        clipPath.setAttribute('clipPathUnits', 'userSpaceOnUse');
        clipRect.setAttribute('x', String(viewBox.x - sweepWidth));
        clipRect.setAttribute('y', String(viewBox.y));
        clipRect.setAttribute('width', String(sweepWidth));
        clipRect.setAttribute('height', String(viewBox.height));
        clipPath.appendChild(clipRect);

        defs.appendChild(gradient);
        defs.appendChild(clipPath);

        sweepGroup.setAttribute('clip-path', 'url(#' + clipId + ')');
        sweepGroup.setAttribute('opacity', '0');
        sweepGroup.setAttribute('aria-hidden', 'true');

        paths.forEach(function (path) {
            appendCloneWithAncestorTransforms(sweepGroup, path, function (clone) {
                clone.style.fill = 'url(#' + sweepId + ')';
                clone.style.stroke = 'url(#' + sweepId + ')';
                clone.style.strokeWidth = sweepStrokeWidth;
                clone.style.strokeLinecap = lineCap;
                clone.style.strokeLinejoin = lineJoin;
                clone.style.pointerEvents = 'none';
            });
        });

        return {
            group: sweepGroup,
            clipRect: clipRect,
            sweepWidth: sweepWidth
        };
    }

    function buildMainTraceSlices(defs) {
        var sliceGroups = [];
        var sliceHeight = viewBox.height / mainTraceSliceCount;

        for (var sliceIndex = 0; sliceIndex < mainTraceSliceCount; sliceIndex += 1) {
            var sliceClipPath = createSvgNode('clipPath');
            var sliceClipRect = createSvgNode('rect');
            var sliceGroup = createSvgNode('g');
            var sliceId = 'sf-logo-main-trace-slice-' + sliceIndex;
            var sliceY = viewBox.y + viewBox.height - ((sliceIndex + 1) * sliceHeight);

            sliceClipPath.setAttribute('id', sliceId);
            sliceClipPath.setAttribute('clipPathUnits', 'userSpaceOnUse');
            sliceClipRect.setAttribute('x', String(viewBox.x));
            sliceClipRect.setAttribute('y', String(sliceY));
            sliceClipRect.setAttribute('width', String(viewBox.width));
            sliceClipRect.setAttribute('height', String(sliceHeight + 1));
            sliceClipPath.appendChild(sliceClipRect);
            defs.appendChild(sliceClipPath);

            sliceGroup.setAttribute('clip-path', 'url(#' + sliceId + ')');
            sliceGroup.setAttribute('aria-hidden', 'true');
            sliceGroup.style.opacity = '0';
            sliceGroup.style.transition = 'opacity ' + mainTraceSliceFadeDuration + 'ms linear';

            mainBodyPaths.forEach(function (entry) {
                appendCloneWithAncestorTransforms(sliceGroup, entry.path, function (traceClone) {
                    traceClone.style.fill = noFillColor;
                    traceClone.style.fillOpacity = '0';
                    traceClone.style.stroke = strokeColor;
                    traceClone.style.strokeOpacity = '1';
                    traceClone.style.strokeWidth = mainTraceStrokeWidth;
                    traceClone.style.strokeLinecap = lineCap;
                    traceClone.style.strokeLinejoin = lineJoin;
                    traceClone.style.opacity = '1';
                    traceClone.style.pointerEvents = 'none';
                });
            });

            svg.appendChild(sliceGroup);
            sliceGroups.push(sliceGroup);
        }

        return sliceGroups;
    }

    paths.forEach(function (path) {
        var bbox;
        var len;
        var pathCenterX;

        try {
            bbox = path.getBBox();
            len = Math.ceil(path.getTotalLength()) + 50;
        } catch (e) {
            return;
        }

        pathCenterX = bbox.x + (bbox.width / 2);
        setBasePathState(path);

        if (isLeafPath(bbox, pathCenterX)) {
            applyTraceStyles(path, len, leafStrokeWidth);
            leafPaths.push(createTraceEntry(path, bbox, len));
            return;
        }

        if (sfLetterIds[path.id] || isCenterLetterPath(bbox, pathCenterX)) {
            applyTraceStyles(path, len, leafStrokeWidth);
            letterPaths.push(createTraceEntry(path, bbox, len));
            return;
        }

        if (mottoLetterIds[path.id]) {
            applyTraceStyles(path, len, leafStrokeWidth);
            mottoPaths.push(createTraceEntry(path, bbox, len));
            return;
        }

        applyMainBodyStyles(path);
        mainBodyPaths.push({ path: path });
    });

    leafPaths.sort(sortLeaves);
    letterPaths.sort(sortByX);
    mottoPaths.sort(sortByX);

    if (viewBox && mainBodyPaths.length) {
        var defs = createSvgNode('defs');
        var sweepLayer = buildSweepLayer(defs);

        svg.insertBefore(defs, svg.firstChild);
        svg.appendChild(sweepLayer.group);
        mainTraceSliceGroups = buildMainTraceSlices(defs);

        setTimeout(function () {
            sweepLayer.group.animate([
                { opacity: 0 },
                { opacity: 1, offset: 0.15 },
                { opacity: 1, offset: 0.75 },
                { opacity: 0 }
            ], {
                duration: 650,
                easing: 'ease-out',
                fill: 'forwards'
            });

            sweepLayer.clipRect.animate([
                { x: viewBox.x - sweepLayer.sweepWidth },
                { x: viewBox.x + viewBox.width }
            ], {
                duration: 650,
                easing: 'cubic-bezier(.25,.1,.25,1)',
                fill: 'forwards'
            });
        }, 1650);

        setTimeout(function () {
            mainTraceSliceGroups.forEach(function (sliceGroup, index) {
                setTimeout(function () {
                    sliceGroup.style.opacity = '1';
                }, index * mainTraceSliceStep);
            });
        }, mainTraceDelay);
    }

    requestAnimationFrame(function () {
        svg.classList.add('is-ready');

        requestAnimationFrame(function () {
            var lastLeafDrawEnd = getSeriesEnd(leafDrawDelayBase, leafDrawDelayStep, leafPaths.length, leafDrawDuration);
            var lastLetterDrawEnd = getSeriesEnd(leafDrawDelayBase, letterDrawDelayStep, letterPaths.length, leafDrawDuration);
            var mottoDrawDelayBase = getSeriesLastStart(leafDrawDelayBase, letterDrawDelayStep, letterPaths.length) + mottoDrawDelayGap;
            var lastMottoDrawEnd = getSeriesEnd(mottoDrawDelayBase, mottoDrawDelayStep, mottoPaths.length, leafDrawDuration);
            var lastMainTraceEnd = mainTraceDelay + ((mainTraceSliceCount - 1) * mainTraceSliceStep) + mainTraceSliceFadeDuration;
            var sharedFillDelay = Math.max(
                0,
                Math.max(lastLeafDrawEnd, lastLetterDrawEnd, lastMottoDrawEnd, lastMainTraceEnd) - sharedFillOverlap
            );

            animateTracedEntries(leafPaths, leafDrawDelayBase, leafDrawDelayStep, sharedFillDelay, true, leafStrokeWidth);
            animateTracedEntries(letterPaths, leafDrawDelayBase, letterDrawDelayStep, sharedFillDelay, false);
            animateTracedEntries(mottoPaths, mottoDrawDelayBase, mottoDrawDelayStep, sharedFillDelay, false);

            mainBodyPaths.forEach(function (entry) {
                animateFill(entry.path, sharedFillDelay, true, '0');
            });

            if (mainTraceSliceGroups.length) {
                setTimeout(function () {
                    mainTraceSliceGroups.forEach(function (sliceGroup) {
                        sliceGroup.style.transition = 'opacity ' + sharedFillDuration + 'ms ease-out';
                        sliceGroup.style.opacity = '0';
                    });

                    setTimeout(function () {
                        mainTraceSliceGroups.forEach(function (sliceGroup) {
                            sliceGroup.remove();
                        });
                        mainTraceSliceGroups = [];
                    }, sharedFillDuration);
                }, sharedFillDelay);
            }
        });
    });
}());
