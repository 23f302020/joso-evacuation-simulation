(function () {
  function createCard(page) {
    const link = document.createElement("a");
    link.className = page.primary ? "card-link card-link-primary" : "card-link";
    link.href = page.href;
    if (page.download) link.setAttribute("download", "");
    const title = document.createElement("span");
    title.className = "card-title";
    title.textContent = page.title;
    const meta = document.createElement("span");
    meta.className = "card-meta";
    meta.textContent = page.meta;
    link.append(title, meta);
    return link;
  }

  function createRouteItem(page) {
    const link = document.createElement("a");
    link.className = "route-link";
    link.href = page.href;
    const title = document.createElement("span");
    title.className = "route-title";
    title.textContent = page.title;
    const meta = document.createElement("span");
    meta.className = "route-meta";
    meta.textContent = page.meta;
    link.append(title, meta);
    return link;
  }

  function createCityCard(page) {
    const link = document.createElement("a");
    link.className = "city-card-link";
    link.href = page.href;
    const title = document.createElement("span");
    title.className = "city-card-title";
    title.textContent = page.title;
    const meta = document.createElement("span");
    meta.className = "city-card-meta";
    meta.textContent = page.meta;
    link.append(title, meta);
    return link;
  }

  function createUnavailableItem(page) {
    const item = document.createElement("li");
    item.className = "unavailable-item";
    const title = document.createElement("span");
    title.className = "unavailable-title";
    title.textContent = page.title;
    const meta = document.createElement("span");
    meta.className = "unavailable-meta";
    meta.textContent = `${page.meta} / ${page.reason}`;
    item.append(title, meta);
    return item;
  }

  function renderList(targetId, pages, createItem) {
    const target = document.getElementById(targetId);
    if (!target) return;
    target.replaceChildren(...pages.map(createItem));
  }

  function normalizeText(value) {
    return String(value || "").toLowerCase().replace(/\s+/g, "");
  }

  function renderCities(pages) {
    const target = document.getElementById("city-links");
    if (!target) return;

    const search = document.getElementById("city-search");
    const select = document.getElementById("city-select");
    const count = document.getElementById("city-count");

    if (select && select.options.length === 0) {
      const all = document.createElement("option");
      all.value = "";
      all.textContent = "すべての市区町村";
      select.appendChild(all);
      pages.forEach(function (page) {
        const option = document.createElement("option");
        option.value = page.meta;
        option.textContent = `${page.title}（${page.meta}）`;
        select.appendChild(option);
      });
    }

    function applyFilter() {
      const query = normalizeText(search ? search.value : "");
      const selected = select ? select.value : "";
      const filtered = pages.filter(function (page) {
        const haystack = normalizeText(`${page.title}${page.meta}`);
        return (!selected || page.meta === selected) && (!query || haystack.includes(query));
      });
      target.replaceChildren(...filtered.map(createCityCard));
      if (count) count.textContent = `${filtered.length} / ${pages.length} 件`;
    }

    if (search) search.addEventListener("input", applyFilter);
    if (select) select.addEventListener("change", applyFilter);
    applyFilter();
  }

  window.addEventListener("DOMContentLoaded", function () {
    const pages = window.RESULT_PAGES;
    if (!pages) return;
    renderList("overview-links", pages.overview, createCard);
    renderList("route-links", pages.routes, createRouteItem);
    renderList("scenario-links", pages.scenario || [], createCard);
    renderList("unified-links", pages.unified || [], createCard);
    renderList("phase2-excel-links", pages.phase2Excel || [], createCard);
    renderList("phase2-animation-links", pages.phase2Animation || [], createCard);
    renderList("phase3-links", pages.phase3 || [], createCard);
    renderCities(pages.cities || []);
    renderList("unavailable-links", pages.unavailable || [], createUnavailableItem);
  });
})();
