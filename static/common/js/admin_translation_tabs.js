(() => {
  "use strict";

  const fieldClassPrefix = "mt-field-";
  let selectedLanguage = null;

  function translatedFieldLanguage(field) {
    for (const className of field.classList) {
      if (!className.startsWith(fieldClassPrefix)) {
        continue;
      }
      const match = className.slice(fieldClassPrefix.length).match(/-(.+)$/);
      if (match) {
        return match[1];
      }
    }
    return null;
  }

  function translatedRows() {
    const rows = new Map();
    for (const field of document.querySelectorAll(".mt")) {
      const language = translatedFieldLanguage(field);
      const row = language && field.closest(".form-row");
      if (!row) {
        continue;
      }
      if (!rows.has(row)) {
        rows.set(row, new Set());
      }
      rows.get(row).add(language);
    }

    // A .form-row that holds more than one language is a tabular inline row,
    // which puts every language's input, the read-only columns and the delete
    // box in one table row. Hiding it to show one language would hide all of
    // that (a poll's Votes column, for example), so those rows keep every
    // language column and only rows that hold a single language follow the tabs.
    return [...rows]
      .filter(([, languages]) => languages.size === 1)
      .map(([row, languages]) => ({ row, language: [...languages][0] }));
  }

  function updateRows() {
    for (const { row, language } of translatedRows()) {
      row.hidden = language !== selectedLanguage;
    }
  }

  function updateTabs(tabs) {
    for (const tab of tabs.querySelectorAll("button")) {
      const selected = tab.dataset.language === selectedLanguage;
      tab.classList.toggle("active", selected);
      tab.setAttribute("aria-pressed", String(selected));
    }
    tabs.querySelector(".translation-language-status").textContent = selectedLanguage;
  }

  function selectLanguage(language, tabs) {
    selectedLanguage = language;
    updateRows();
    updateTabs(tabs);
  }

  function initialise() {
    const rows = translatedRows();
    const languages = [...new Set(rows.map(({ language }) => language))];
    if (!languages.length) {
      return;
    }

    selectedLanguage = selectedLanguage && languages.includes(selectedLanguage) ? selectedLanguage : languages[0];
    let tabs = document.querySelector(".translation-language-tabs");
    if (!tabs) {
      tabs = document.createElement("nav");
      tabs.className = "translation-language-tabs";
      tabs.setAttribute("role", "group");
      tabs.setAttribute("aria-label", "Content language");
      tabs.innerHTML = languages
        .map(
          (language) =>
            `<button type="button" aria-pressed="false" data-language="${language}">${language.replace("_", "-")}</button>`,
        )
        .join("") + '<span class="translation-language-status" aria-live="polite"></span>';
      tabs.addEventListener("click", (event) => {
        const button = event.target.closest("button[data-language]");
        if (!button) {
          return;
        }
        selectLanguage(button.dataset.language, tabs);
      });
      tabs.addEventListener("keydown", (event) => {
        const buttons = [...tabs.querySelectorAll("button[data-language]")];
        const currentIndex = buttons.indexOf(document.activeElement);
        if (currentIndex < 0) {
          return;
        }
        let nextIndex;
        if (event.key === "ArrowRight" || event.key === "ArrowDown") {
          nextIndex = (currentIndex + 1) % buttons.length;
        } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
          nextIndex = (currentIndex - 1 + buttons.length) % buttons.length;
        } else if (event.key === "Home") {
          nextIndex = 0;
        } else if (event.key === "End") {
          nextIndex = buttons.length - 1;
        } else {
          return;
        }
        event.preventDefault();
        buttons[nextIndex].focus();
        selectLanguage(buttons[nextIndex].dataset.language, tabs);
      });
      rows[0].row.before(tabs);
    }

    updateRows();
    updateTabs(tabs);
  }

  document.addEventListener("DOMContentLoaded", () => {
    initialise();
    new MutationObserver((mutations) => {
      if (mutations.some((mutation) => !mutation.target.closest(".translation-language-tabs"))) {
        initialise();
      }
    }).observe(document.body, { childList: true, subtree: true });
  });
})();
