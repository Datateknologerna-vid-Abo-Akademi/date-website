if (typeof jQuery !== 'undefined' || typeof(django.jQuery) !== 'undefined') {
    (function ($) {
        if (typeof($.fn.JSONView) !== 'undefined') return;
        !function (e) {
            var n, t, l, r;
            return l = function () {
                function e(e) {
                    null == e && (e = {}), this.options = e
                }

                return e.prototype.htmlEncode = function (e) {
                    return null !== e ? e.toString().replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;") : ""
                }, e.prototype.jsString = function (e) {
                    return e = JSON.stringify(e).slice(1, -1), this.htmlEncode(e)
                }, e.prototype.decorateWithSpan = function (e, n) {
                    return '<span class="' + n + '">' + this.htmlEncode(e) + "</span>"
                }, e.prototype.valueToHTML = function (e, n) {
                    var t;
                    return null == n && (n = 0), t = Object.prototype.toString.call(e).match(/\s(.+)]/)[1].toLowerCase(), this["" + t + "ToHTML"].call(this, e, n)
                }, e.prototype.nullToHTML = function (e) {
                    return this.decorateWithSpan("null", "null")
                }, e.prototype.numberToHTML = function (e) {
                    return this.decorateWithSpan(e, "num")
                }, e.prototype.stringToHTML = function (e) {
                    var n, t;
                    return /^(http|https|file):\/\/[^\s]+$/i.test(e) ? '<a href="' + this.htmlEncode(e) + '"><span class="q">"</span>' + this.jsString(e) + '<span class="q">"</span></a>' : (n = "", e = this.jsString(e), this.options.nl2br && (t = /([^>\\r\\n]?)(\\r\\n|\\n\\r|\\r|\\n)/g, t.test(e) && (n = " multiline", e = (e + "").replace(t, "$1<br />"))), '<span class="string' + n + '">"' + e + '"</span>')
                }, e.prototype.booleanToHTML = function (e) {
                    return this.decorateWithSpan(e, "bool")
                }, e.prototype.arrayToHTML = function (e, n) {
                    var t, l, r, o, s, i, a, p;
                    for (null == n && (n = 0), l = !1, s = "", o = e.length, r = a = 0, p = e.length; p > a; r = ++a) i = e[r], l = !0, s += "<li>" + this.valueToHTML(i, n + 1), o > 1 && (s += ","), s += "</li>", o--;
                    return l ? (t = 0 === n ? "" : " collapsible", '<ul class="array level' + n + t + '">' + s + "</ul>") : ""
                }, e.prototype.objectToHTML = function (e, n) {
                    var t, l, r, o, s, i, a;
                    null == n && (n = 0), l = !1, s = "", o = 0;
                    for (i in e) o++;
                    for (i in e) a = e[i], l = !0, r = this.options.escape ? this.jsString(i) : i, s += '<li><span class="prop"><span class="q">"</span>' + r + '<span class="q">"</span></span>: ' + this.valueToHTML(a, n + 1), o > 1 && (s += ","), s += "</li>", o--;
                    return l ? (t = 0 === n ? "" : " collapsible", '<ul class="obj level' + n + t + '">' + s + "</ul>") : ""
                }, e.prototype.jsonToHTML = function (e) {
                    return '<div class="jsonview">' + this.valueToHTML(e) + "</div>"
                }, e
            }(), "undefined" != typeof module && null !== module && (module.exports = l), t = function () {
                function e() {
                }
            }(), n = e, r = {
            }, n.fn.JSONView = function () {
                var e, o, s, i, a, p, c;
                return e = arguments, null != r[e[0]] ? (a = e[0], this.each(function () {
                    var t, l;
                    return t = n(this), null != e[1] ? (l = e[1], t.find(".jsonview .collapsible.level" + l).siblings(".collapser").each(function () {
                        return r[a](this)
                    })) : t.find(".jsonview > ul > li .collapsible").siblings(".collapser").each(function () {
                        return r[a](this)
                    })
                })) : (i = e[0], p = e[1] || {}, o = {
                    collapsed: !1,
                    nl2br: !1,
                    recursive_collapser: !1,
                    escape: !0
                }, p = n.extend(o, p), s = new l({
                    nl2br: p.nl2br,
                    escape: p.escape
                }), "[object String]" === Object.prototype.toString.call(i) && (i = JSON.parse(i)), c = s.jsonToHTML(i), this.each(function () {
                    var e, l, r, o, s, i;
                    for (e = n(this), e.html(c), r = e[0].getElementsByClassName("collapsible"), i = [], o = 0, s = r.length; s > o; o++) l = r[o], "LI" === l.parentNode.nodeName ? i.push(t.bindEvent(l.parentNode, p)) : i.push(void 0);
                    return i
                }))
            }
        }($);

        $(document).ready(function () {

            $('.jsonwidget').each(function (i) {
                var widget = $(this);
                var rawarea = widget.find('textarea');
                var parsedarea = widget.find('div.parsed');
                var validjson = true;
                try {
                    JSON.parse(rawarea.val());
                } catch (e) {
                    validjson = false;
                }
                if (validjson) {
                    rawarea.hide();
                    widget.find('.parsed').show();
                    parsedarea.JSONView(rawarea.val(), {strict: true}).css({
                        overflow: "auto",
                        resize: "both"
                    });
                } else {
                    // invalid json
                        window.alert('Enter valid JSON.');
                }
            });

        });
    })((typeof jQuery !== 'undefined') ? jQuery : django.jQuery);
} else {
    throw new Error('django-prettyjson requires jQuery');
}