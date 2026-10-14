/*
 * Hero logo trace animation for the HF homepage.
 *
 * templates/hf/svg/logo.svg is emitted by scripts/trace_hero_logo_svg.py as one
 * <path> per visual element. The classes carry the roles:
 *
 *   .hf-ring        the ring band, as fill geometry
 *   .hf-ring-outer  the band's outer circle, as a stroke guide
 *   .hf-ring-dot    the bead dots sitting in the gap inside the band
 *   .hf-letter      the arc lettering, in reading order
 *   .hf-figure      the disc's interior contours, one path each
 *   .hf-disc-edge   the disc's outline, as a stroke guide
 *   .hf-disc        the disc, carrying the figure as negative space
 *   .hf-detail      the fine detail inside the disc
 *
 * The animation is built around one sweep. A hand starts at the first letter
 * of the arc text and travels clockwise round the emblem, and the beads start
 * drawing when the hand reaches the angle they sit at.
 *
 * The hand is not a separate effect: it is the leading edge of the two circles.
 * They are traced at exactly the sweep's pace and rotated so their dashes begin
 * on the sweep's origin, which means their leading edges stay radially aligned
 * with each other and with everything else the hand has reached. A dash trace
 * cannot show a circle without a gap in it, but with both gaps in the same
 * place the gap is the hand, and it reads as intended.
 *
 * The lettering is deliberately not on the hand. The top arc reads clockwise
 * and the bottom arc reads anticlockwise, because the bottom words sit upright
 * rather than upside down, so no single rotating hand can write both in order:
 * running the bottom arc with the hand spells it right to left. It is written
 * instead, in reading order, at a pace that keeps it in step with the hand over
 * the top arc.
 *
 * The figure is not a ring, so it is not swept. Its contours are drawn one
 * after another, top of the artwork downwards, the way it would be sketched,
 * starting while the hand is still going round so the two overlap.
 *
 * Every measurement is taken from the live paths with getBBox(),
 * getPointAtLength(), getTotalLength() and getCTM(), so the timing survives any
 * later edit of the artwork.
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

    // The sweep: one turn, starting a beat after the page settles. A turn is a
    // repeating movement, so it wants to be brisk; the figure below is a
    // one-off drawing, and that one wants to be slow enough to follow.
    var sweepDelay = 250;
    var sweepTurn = 2800;

    // Radial layers. Each element starts when the sweep reaches the angle it
    // sits at, and `duration` is how long one element takes to draw. The
    // durations belong to the sweep: they set how wide a swath of the emblem is
    // mid-draw behind the hand, so they scale with the turn rather than staying
    // put and leaving a long tail.
    //
    // Only the beads are on the hand. The lettering is not, and that is not an
    // oversight: the top arc reads clockwise and the bottom arc reads
    // anticlockwise, because the bottom words sit upright rather than upside
    // down. One rotating hand therefore cannot write both in order, and running
    // the bottom arc with the hand spells it right to left.
    var radialLayers = [{ selector: '.hf-ring-dot', duration: 440 }];

    // The lettering is written instead, in the order the artwork lists it,
    // which the trace script emits as reading order.
    var textLayers = [
        { selector: '.hf-letter', delay: 400, stagger: 55, duration: 560 }
    ];

    // The circles, traced at the sweep's own pace so their leading edge is the
    // hand everything else waits for.
    var circleSelectors = ['.hf-ring-outer', '.hf-disc-edge'];

    // The figure, drawn top downwards rather than swept, and started while the
    // hand is still going round so the two overlap instead of queueing up.
    var figureLayers = [
        { selector: '.hf-figure, .hf-detail', delay: 1100, stagger: 75, duration: 800 }
    ];

    // Fill geometry: invisible while the drawing is happening, then faded in
    // whole so the solid emblem arrives with the figure punched out of it.
    var fillSelectors = ['.hf-ring', '.hf-disc'];

    var fillDuration = 1100;
    var fillOverlap = 300;
    var strokeFractionOfViewBox = 0.0042;

    var animations = [];
    var centreLocal = null;
    var centreViewBox = null;

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
        var transform = paths[0].parentNode.getAttribute('transform') || '';
        var match = /scale\(\s*(-?[\d.]+)/.exec(transform);
        if (!match) return 1;
        var scale = Math.abs(parseFloat(match[1]));
        return scale > 0 ? 1 / scale : 1;
    }

    function measure(path) {
        return Math.ceil(path.getTotalLength()) + 24;
    }

    // Angles are measured in the viewport's own coordinates, which run the way
    // the viewer sees them, rather than in the artwork's, which run bottom-up
    // because the group transform flips y.
    function toViewBox(path, x, y) {
        return new DOMPoint(x, y).matrixTransform(path.getCTM());
    }

    function angleBetween(point, centre) {
        var degrees = (Math.atan2(point.y - centre.y, point.x - centre.x) * 180) / Math.PI;
        return (degrees + 360) % 360;
    }

    function boxAngle(path, centre) {
        var box = path.getBBox();
        return angleBetween(
            toViewBox(path, box.x + box.width / 2, box.y + box.height / 2),
            centre
        );
    }

    function startAngle(path, centre) {
        var point = path.getPointAtLength(0);
        return angleBetween(toViewBox(path, point.x, point.y), centre);
    }

    // The trace script mirrors a circle when it would otherwise travel the
    // other way round from its neighbour. That mirror is part of the artwork,
    // so the rotation below is composed on top of it rather than written over
    // it, which would silently drop the mirror and set the two circles
    // drawing against each other.
    function circleBaseTransform(path) {
        if (typeof path.hfBaseTransform === 'undefined') {
            path.hfBaseTransform = path.getAttribute('transform') || '';
        }
        return path.hfBaseTransform;
    }

    function setCircleTransform(path, degrees) {
        var base = circleBaseTransform(path);
        var rotation =
            'rotate(' + degrees + ' ' + centreLocal.x + ' ' + centreLocal.y + ')';
        path.setAttribute('transform', base ? base + ' ' + rotation : rotation);
    }

    // A dash can only begin where its path begins, so each circle is rotated to
    // bring that start onto the sweep's origin. The artwork's y flip makes a
    // rotation in the path's own coordinates run the other way on screen, so
    // the direction is measured with a one degree nudge instead of assumed.
    function alignCircleToOrigin(path, origin) {
        setCircleTransform(path, 0);
        var before = startAngle(path, centreViewBox);
        setCircleTransform(path, 1);
        var perLocalDegree = ((startAngle(path, centreViewBox) - before + 540) % 360) - 180;
        var wanted = ((origin - before + 540) % 360) - 180;
        setCircleTransform(path, perLocalDegree === 0 ? 0 : wanted / perLocalDegree);
    }

    function sweepOrigin() {
        var firstLetter = svg.querySelector('.hf-letter');
        // Failing that, start at twelve o'clock, which is 270 in this frame.
        return firstLetter ? boxAngle(firstLetter, centreViewBox) : 270;
    }

    function collect() {
        var origin = sweepOrigin();
        var timeline = [];

        circleSelectors.forEach(function (selector) {
            svg.querySelectorAll(selector).forEach(function (path) {
                alignCircleToOrigin(path, origin);
                timeline.push({
                    path: path,
                    length: measure(path),
                    delay: sweepDelay,
                    duration: sweepTurn,
                    end: sweepDelay + sweepTurn
                });
            });
        });

        radialLayers.forEach(function (layer) {
            Array.prototype.slice.call(svg.querySelectorAll(layer.selector)).forEach(
                function (path) {
                    var clockwise = ((boxAngle(path, centreViewBox) - origin) % 360 + 360) % 360;
                    var delay = sweepDelay + (clockwise / 360) * sweepTurn;
                    timeline.push({
                        path: path,
                        length: measure(path),
                        delay: delay,
                        duration: layer.duration,
                        end: delay + layer.duration
                    });
                }
            );
        });

        function pushInDocumentOrder(layer) {
            Array.prototype.slice.call(svg.querySelectorAll(layer.selector)).forEach(
                function (path, index) {
                    var delay = layer.delay + index * layer.stagger;
                    timeline.push({
                        path: path,
                        length: measure(path),
                        delay: delay,
                        duration: layer.duration,
                        end: delay + layer.duration
                    });
                }
            );
        }

        textLayers.forEach(pushInDocumentOrder);
        figureLayers.forEach(pushInDocumentOrder);

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

    function run() {
        var reducedMotion =
            window.matchMedia &&
            window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        if (reducedMotion || typeof svg.animate !== 'function') {
            reveal();
            return;
        }

        var ring = svg.querySelector('.hf-ring');
        if (!ring) {
            reveal();
            return;
        }
        var ringBox = ring.getBBox();
        centreLocal = { x: ringBox.x + ringBox.width / 2, y: ringBox.y + ringBox.height / 2 };
        centreViewBox = toViewBox(ring, centreLocal.x, centreLocal.y);

        svg.classList.add('is-animating');
        // The artwork is authored 10x inside its group transform, so a stroke
        // width meant to read as a given fraction of the viewBox has to be
        // converted into those local units. 0.0042 of the viewBox is a little
        // over 2px once the logo is at its widest, which keeps the trace
        // lighter than the artwork it is drawing.
        var strokeWidth =
            svg.viewBox.baseVal.width * strokeFractionOfViewBox * localUnitsPerViewBoxUnit();
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

        timeline.forEach(function (entry) {
            drawEntry(entry);
            fillEntry(entry.path, fillDelay);
        });

        fillSelectors.forEach(function (selector) {
            svg.querySelectorAll(selector).forEach(function (path) {
                path.style.opacity = '1';
                path.style.fillOpacity = '0';
                fillEntry(path, fillDelay);
            });
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
