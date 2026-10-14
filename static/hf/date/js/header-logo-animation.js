/*
 * Hero logo trace animation for the HF homepage.
 *
 * The hero logo in templates/hf/svg/logo.svg is emitted as one <path> per
 * visual element, already ordered in draw sequence:
 *
 *   .hf-ring       the outer circle
 *   .hf-ring-dot   the bead dots sitting in the ring's gap
 *   .hf-letter     the arc lettering, in reading order
 *   .hf-disc       the disc, figure contours first and its outline last
 *   .hf-detail     the fine detail inside the disc
 *
 * This script walks the logo stroke by stroke with stroke-dashoffset and then
 * fades the fills in together. Every measurement is taken from the live paths
 * with getTotalLength(), so the timing survives any later edit of the artwork.
 *
 * Two deliberate exceptions to the stroke trace:
 *
 *   The outer circle fades in whole. It is an annulus, so a dash trace leaves
 *   the same gap in two concentric contours at once, and a circle with an
 *   obvious gap in it reads as a mistake rather than as drawing.
 *
 *   The disc outline is the last contour of its own path, so the figure is
 *   drawn first and the circle closes around it at the end. Leading with the
 *   outline would mean the longest phase of the animation is spent watching a
 *   large unfinished circle.
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

    // One entry per traced layer. `delay` is when the layer starts, `stagger`
    // is the extra delay per element inside it, and `duration` is one
    // element's draw. The disc gets the longest draw because it carries the
    // whole figure plus its closing circle.
    var stages = [
        { selector: '.hf-ring-dot', delay: 950, stagger: 50, duration: 650 },
        { selector: '.hf-letter', delay: 1400, stagger: 85, duration: 900 },
        { selector: '.hf-disc', delay: 2100, stagger: 0, duration: 4400 },
        { selector: '.hf-detail', delay: 3200, stagger: 65, duration: 800 }
    ];

    var ringFadeDelay = 200;
    var ringFadeDuration = 1200;
    var fillDuration = 1100;
    var fillOverlap = 300;

    var state = {};
    var animations = [];

    function remember(el) {
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
                var delay = stage.delay + index * stage.stagger;
                timeline.push({
                    path: path,
                    length: measure(path),
                    delay: delay,
                    duration: stage.duration,
                    end: delay + stage.duration
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
        animations.push(animation);
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
        animations.push(animation);
    }

    function fadeInRing(path) {
        path.style.transformBox = 'fill-box';
        path.style.transformOrigin = 'center';
        path.style.opacity = '0';
        path.style.fillOpacity = '0';

        var animation = path.animate(
            [
                { opacity: 0, fillOpacity: 0, transform: 'scale(0.96)' },
                { opacity: 1, fillOpacity: 1, transform: 'scale(1)' }
            ],
            {
                duration: ringFadeDuration,
                delay: ringFadeDelay,
                easing: 'cubic-bezier(.2,.7,.2,1)',
                fill: 'forwards'
            }
        );

        animation.onfinish = function () {
            path.style.opacity = '1';
            path.style.fillOpacity = '1';
            path.style.transform = 'scale(1)';
        };
        animations.push(animation);
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

        svg.querySelectorAll('.hf-ring').forEach(fadeInRing);

        timeline.forEach(function (entry) {
            drawEntry(entry);
            fillEntry(entry.path, fillDelay);
        });

        // Release the class that hides the fills while the layers are being
        // measured and set up. Every path is visible by then anyway.
        window.setTimeout(
            function () {
                svg.classList.remove('is-animating');
            },
            fillDelay + fillDuration + 120
        );
    }

    try {
        run();
    } catch (error) {
        reveal();
    }
}());
