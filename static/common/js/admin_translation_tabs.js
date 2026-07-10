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
    return [...document.querySelectorAll(".mt")]
      .map((field) => ({ field, language: translatedFieldLanguage(field) }))
      .filter(({ language }) => language)
      .map(({ field, language }) => ({ row: field.closest(".form-row"), language }))
      .filter(({ row }) => row);
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
        let nextIndex = currentIndex;
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
    new MutationObserver(initialise).observe(document.body, { childList: true, subtree: true });
  });
})();
