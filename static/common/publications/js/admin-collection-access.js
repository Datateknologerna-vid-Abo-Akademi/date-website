(function () {
  function replaceCollectionId(urlTemplate, collectionId) {
    return urlTemplate.replace(/\/0\/$/, "/" + collectionId + "/");
  }

  function renderSummary(container, details) {
    container.replaceChildren();

    const title = document.createElement("strong");
    title.textContent = details.title;
    container.append(title, ": ", details.access);

    const extras = [];
    if (details.memberships && details.memberships.length) {
      extras.push("Memberships: " + details.memberships.join(", "));
    }
    if (details.visibility === "password") {
      extras.push(details.has_password ? "Password configured" : "Password missing");
    }
    if (!details.active) {
      extras.push("Inactive");
    }
    if (extras.length) {
      container.append(" (" + extras.join("; ") + ")");
    }

    container.append(" ");
    const editLink = document.createElement("a");
    editLink.href = details.edit_url;
    editLink.textContent = "Edit collection access";
    container.append(editLink);
  }

  async function updateSummary(select, container) {
    const collectionId = select.value;
    if (!collectionId) {
      container.textContent = "Choose a collection to show its current access settings here.";
      return;
    }

    const urlTemplate = container.dataset.urlTemplate;
    if (!urlTemplate) {
      return;
    }

    container.textContent = "Loading collection access...";
    try {
      const response = await fetch(replaceCollectionId(urlTemplate, collectionId), {
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        throw new Error("Request failed");
      }
      renderSummary(container, await response.json());
    } catch (error) {
      container.textContent = "Could not load collection access settings.";
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    const select = document.getElementById("id_collection");
    const container = document.getElementById("publication-collection-access-summary");
    if (!select || !container) {
      return;
    }

    select.addEventListener("change", function () {
      updateSummary(select, container);
    });
    if (select.value && !container.querySelector("a")) {
      updateSummary(select, container);
    }
  });
})();
