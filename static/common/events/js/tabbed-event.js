(function () {
    "use strict";

    function getHashTarget() {
        if (!window.location.hash) {
            return "";
        }
        return window.location.hash.slice(1).replace(/\//g, "");
    }

    function showTab(contentClass, targetClass) {
        if (!contentClass || !targetClass) {
            return;
        }
        document.querySelectorAll("." + contentClass).forEach(function (node) {
            node.classList.add("hidden");
        });
        document.querySelectorAll("." + targetClass).forEach(function (node) {
            node.classList.remove("hidden");
        });
    }

    function initTabbedNav(navRoot) {
        var contentClass = navRoot.dataset.tabContentClass;
        if (!contentClass) {
            return;
        }

        navRoot.querySelectorAll("[data-nav]").forEach(function (link) {
            link.addEventListener("click", function () {
                showTab(contentClass, link.dataset.nav);
            });
        });

        var initialTarget = getHashTarget();
        if (initialTarget) {
            showTab(contentClass, initialTarget);
        }

        window.addEventListener("hashchange", function () {
            var target = getHashTarget();
            if (target) {
                showTab(contentClass, target);
            }
        });
    }

    document.querySelectorAll("[data-tabbed-nav]").forEach(initTabbedNav);
}());
