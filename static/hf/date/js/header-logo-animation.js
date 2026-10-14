/*
 * Hero logo trace animation for the HF homepage.
 *
 * The hero logo in templates/hf/svg/logo.svg is emitted as one <path> per
 * visual element, already ordered in draw sequence:
 *
 *   .hf-ring       the outer circle
 *   .hf-ring-dot   the bead dots sitting in the ring's gap
 *   .hf-letter     the arc lettering, in reading order
 *   .hf-disc       the disc together with the figure as negative space
 *   .hf-detail     the fine detail inside the disc
 *
 * This script walks the logo stroke by stroke with stroke-dashoffset, then
 * fades the fills in together, and sweeps a highlight across the finished
 * mark. Every measurement is taken from the live paths with getTotalLength()
 * and getBBox(), so the timing survives any later edit of the artwork.
 *
 * Without JavaScript, or with reduced motion requested, the logo just renders
 * in its final state: the artwork carries a real fill and the script adds the
 * zeroed-out state itself rather than relying on a stylesheet.
 */
(function () {
    'use strict';

    var svg = document.querySelector('.hero-text-box .albin svg');
    if (!svg) return;

    var paths = Array.prototype.slice.call(svg.querySelectorAll('path'));
    if (!paths.length) return;

    var svgNs = 'http://www.w3.org/2000/svg';

    // One entry per drawn layer. `delay` is when the layer starts, `stagger`
    // is the extra delay per element inside it, `duration` is one element's
    // draw. The disc gets the longest draw because it carries the whole
    // figure: its outline runs first, then every interior contour in turn.
    var stages = [
        { selector: '.hf-ring', delay: 140, stagger: 0, duration: 1300 },
        { selector: '.hf-ring-dot', delay: 560, stagger: 26, duration: 430 },
        { selector: '.hf-letter', delay: 760, stagger: 48, duration: 560 },
        { selector: '.hf-disc', delay: 1020, stagger: 0, duration: 2700 },
        { selector: '.hf-detail', delay: 1520, stagger: 36, duration: 440 }
    ];

    var fillDuration = 640;
    var fillOverlap = 150;
    var sweepStartGap = 90;
    var sweepDuration = 760;

    var state = {};
    var animations = [];
    var sweepNodes = null;

    function mark(el) {
        state[el] = {
            opacity: el.style.opacity,
            fillOpacity: el.style.fillOpacity,
            stroke: el.style.stroke,
            strokeOpacity: el.style.strokeOpacity,
            strokeWidth: el.style.strokeWidth,
            strokeDasharray: el.style.strokeDasharray,
            strokeDashoffset: el.style.strokeDashoffset
        };
    }

    // Put every path back to plain artwork in its final state. Used when the
    // animation is skipped or when anything in it throws, so a failure can
    // never leave an invisible hero. Live animations are cancelled first,
    // because a running animation with fill:forwards outranks the inline
    // styles set here and would keep a path hidden.
    function reveal() {
        animations.forEach(function (animation) {
            animation.cancel();
        });
        animations.length = 0;
        if (sweepNodes.parentNode) sweepNodes.parentNode.removeChild(sweepNodes);
        sweepNodes = null;

        paths.forEach(function (path) {
            if (state[path]) {
                Object.keys(state[path]).forEach(function (property) {
                    path.style[property] = state[path][property];
                });
            }
            path.style.opacity = '1';
            path.style.fillOpacity = '1';
            path.style.stroke = 'none';
            path.style.strokeOpacity = '0';
            path.style.removeProperty('stroke-dasharray');
            path.style.removeProperty('stroke-dashoffset');
        });
        svg.classList.remove('is-animating');
    }

    function localUnitsPerViewBoxUnit() {
        var transform = '';
        if (paths[0].parentNode) {
            transform = paths[0].parentNode.getAttribute('transform') || '';
        }
        var match = /scale\(\s*(-?[\d.]+)/.exec(transform);
        if (!match) return 1;
        var scale = Math.abs(parseFloat(match[1]));
        return scale > 0 ? 1 / scale : 1;
    }

    function measure(path) {
        return Math.ceil(path.getTotalLength()) + 24;
    }

    function collect() {
        var timeline = [];
        stages.forEach(function (stage) {
            var elements = Array.prototype.slice.call(svg.querySelectorAll(stage.selector));
            elements.forEach(function (path, index) {
                timeline.push({
                    path: path,
                    length: measure(path),
                    delay: stage.delay + index * stage.stagger,
                    duration: stage.duration,
                    end: stage.delay + index * stage.stagger + stage.duration
                });
            });
        });
        return timeline;
    }

    function applyTraceState(entry, strokeWidth) {
        var style = entry.path.style;
        style.stroke = 'currentColor';
        style.strokeWidth = strokeWidth;
        style.strokeLinecap = 'round';
        style.strokeLinejoin = 'round';
        style.strokeDasharray = entry.length + ' ' + entry.length;
        style.strokeDashoffset = entry.length;
        style.fillOpacity = '0';
        style.opacity = '1';
    }

    function drawEntry(entry) {
        var animation = entry.path.animate(
            [{ strokeDashoffset: entry.length }, { strokeDashoffset: 0 }],
            {
                duration: entry.duration,
                delay: entry.delay,
                easing: 'linear',
                fill: 'forwards'
            }
        );

        animation.onfinish = function () {
            entry.path.style.removeProperty('stroke-dasharray');
            entry.path.style.removeProperty('stroke-dashoffset');
        };
    }

    function fillEntry(path, delay) {
        var animation = path.animate(
            [
                { fillOpacity: 0, strokeOpacity: 1 },
                { fillOpacity: 0.88, strokeOpacity: 0.5, offset: 0.66 },
                { fillOpacity: 1, strokeOpacity: 0 }
            ],
            {
                duration: fillDuration,
                delay: delay,
                easing: 'cubic-bezier(.2,.7,.2,1)',
                fill: 'forwards'
            }
        );

        animation.onfinish = function () {
            path.style.fillOpacity = '1';
            path.style.stroke = 'none';
            path.style.strokeOpacity = '0';
        };
    }

    // A gradient-clipped copy of the whole mark, wiped across it once the
    // fills land. Everything here works in the artwork group's own user space
    // and the copies are appended inside that group, so the gradient, the clip
    // rectangle and the animated `x` all share one coordinate system. The
    // group carries scale(0.1, -0.1), so viewBox units would be off by a
    // factor of ten here.
    function buildSweep(artGroup, strokeWidth) {
        var box = artGroup.getBBox();
        var sweepWidth = box.width * 0.3;
        var centreY = box.y + box.height / 2;
        var gradientId = 'hf-logo-sweep';
        var clipId = 'hf-logo-sweep-clip';

        var defs = document.createElementNS(svgNs, 'defs');

        // The artwork is filled in --secondaryColor, so a highlight in that
        // same colour would be invisible over it. The sheen is drawn in the
        // variant's own --primaryColor instead, which reads as a soft shadow
        // travelling across the finished mark.
        var sheenColor =
            getComputedStyle(svg).getPropertyValue('--primaryColor').trim() || '#191970';

        var gradient = document.createElementNS(svgNs, 'linearGradient');
        gradient.setAttribute('id', gradientId);
        gradient.setAttribute('gradientUnits', 'userSpaceOnUse');
        gradient.setAttribute('x1', String(box.x));
        gradient.setAttribute('y1', String(centreY));
        gradient.setAttribute('x2', String(box.x + box.width));
        gradient.setAttribute('y2', String(centreY));
        [
            { offset: '0%', opacity: '0' },
            { offset: '34%', opacity: '0' },
            { offset: '50%', opacity: '0.42' },
            { offset: '66%', opacity: '0' },
            { offset: '100%', opacity: '0' }
        ].forEach(function (stopDefinition) {
            var stop = document.createElementNS(svgNs, 'stop');
            stop.setAttribute('offset', stopDefinition.offset);
            stop.setAttribute('stop-color', sheenColor);
            stop.setAttribute('stop-opacity', stopDefinition.opacity);
            gradient.appendChild(stop);
        });
        defs.appendChild(gradient);

        var clipPath = document.createElementNS(svgNs, 'clipPath');
        clipPath.setAttribute('id', clipId);
        clipPath.setAttribute('clipPathUnits', 'userSpaceOnUse');
        var clipRect = document.createElementNS(svgNs, 'rect');
        clipRect.setAttribute('x', String(box.x - sweepWidth));
        clipRect.setAttribute('y', String(box.y));
        clipRect.setAttribute('width', String(sweepWidth));
        clipRect.setAttribute('height', String(box.height));
        clipPath.appendChild(clipRect);
        defs.appendChild(clipPath);

        var group = document.createElementNS(svgNs, 'g');
        group.setAttribute('clip-path', 'url(#' + clipId + ')');
        group.setAttribute('opacity', '0');
        group.setAttribute('aria-hidden', 'true');

        paths.forEach(function (path) {
            var clone = path.cloneNode(false);
            // The clone inherits the tracing state that applyTraceState put on
            // the original, including a fill-opacity of 0 and a dash array
            // whose offset hides the whole stroke, so it has to be cleared or
            // the highlight paints nothing at all.
            clone.removeAttribute('class');
            clone.style.opacity = '1';
            clone.style.fillOpacity = '1';
            clone.style.strokeOpacity = '1';
            clone.style.removeProperty('stroke-dasharray');
            clone.style.removeProperty('stroke-dashoffset');
            clone.style.fill = 'url(#' + gradientId + ')';
            clone.style.stroke = 'url(#' + gradientId + ')';
            clone.style.strokeWidth = strokeWidth * 0.5;
            clone.style.strokeLinecap = 'round';
            clone.style.strokeLinejoin = 'round';
            clone.style.pointerEvents = 'none';
            group.appendChild(clone);
        });

        group.appendChild(defs);

        var artGroup = paths[0].parentNode;
        artGroup.appendChild(group);
        return { group: group, clipRect: clipRect, width: sweepWidth, box: box };
    }

    function playSweep(sweep, delay) {
        animations.push(
            sweep.group.animate(
                [
                    { opacity: 0 },
                    { opacity: 1, offset: 0.16 },
                    { opacity: 1, offset: 0.74 },
                    { opacity: 0 }
                ],
                { duration: sweepDuration, delay: delay, easing: 'ease-out', fill: 'forwards' }
            )
        );

        animations.push(
            sweep.clipRect.animate(
                [
                    { x: sweep.box.x - sweep.width },
                    { x: sweep.box.x + sweep.box.width }
                ],
                {
                    duration: sweepDuration,
                    delay: delay,
                    easing: 'cubic-bezier(.25,.1,.25,1)',
                    fill: 'forwards'
                }
            )
        );
    }

    function run() {
        var reducedMotion =
            window.matchMedia &&
            window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        if (reducedMotion || typeof svg.animate !== 'function') {
            reveal();
            return;
        }

        svg.classList.add('is-animating');
        // The artwork is authored 10x inside its group transform, so a stroke
        // width meant to read as a given fraction of the viewBox has to be
        // converted into those local units.
        var strokeWidth = svg.viewBox.baseVal.width * 0.0055 * localUnitsPerViewBoxUnit();
        var timeline = collect();
        if (!timeline.length) {
            reveal();
            return;
        }

        timeline.forEach(function (entry) {
            applyTraceState(entry, strokeWidth);
        });

        var traceEnd = timeline.reduce(function (latest, entry) {
            return Math.max(latest, entry.end);
        }, 0);
        var fillDelay = Math.max(0, traceEnd - fillOverlap);

        var sweep = buildSweep(paths[0].parentNode, strokeWidth);
        sweepNodes = sweep.group;

        timeline.forEach(function (entry) {
            drawEntry(entry);
            fillEntry(entry.path, fillDelay);
        });

        playSweep(sweep, fillDelay + sweepStartGap);

        // Tidy up once the fill and the sweep have landed: drop the highlight
        // copies and release the class that hides the fills while setting up.
        window.setTimeout(
            function () {
                if (sweepNodes && sweepNodes.parentNode) {
                    sweepNodes.parentNode.removeChild(sweepNodes);
                }
                sweepNodes = null;
                svg.classList.remove('is-animating');
            },
            fillDelay + sweepStartGap + sweepDuration + 120
        );
    }

    try {
        run();
    } catch (error) {
        reveal();
    }
}());
