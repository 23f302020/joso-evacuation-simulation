(function () {
  const data = window.SCENARIO_V2_DATA;
  if (!data) return;

  const supportBounds = L.latLngBounds(data.supportArea.bounds);
  const map = L.map("map", {
    maxBounds: data.supportArea.maxBounds,
    maxBoundsViscosity: 0.85
  }).setView(data.map.center, data.map.zoom);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors &copy; CARTO"
  }).addTo(map);

  const outsideLayer = L.layerGroup().addTo(map);
  const floodLayer = L.geoJSON(null, {
    style: {
      weight: 0,
      fillColor: "#2563eb",
      fillOpacity: 0.3
    }
  }).addTo(map);
  const closedLayer = L.layerGroup().addTo(map);
  const routeLayer = L.layerGroup().addTo(map);
  const markerLayer = L.layerGroup().addTo(map);
  const shelterLayer = L.layerGroup().addTo(map);

  const nodes = data.graph.nodes;
  const edgesById = new Map();
  const adjacency = new Map();

  function addOutsideMask() {
    const s = supportBounds.getSouth();
    const n = supportBounds.getNorth();
    const w = supportBounds.getWest();
    const e = supportBounds.getEast();
    L.polygon(
      [
        [[-85, -180], [-85, 180], [85, 180], [85, -180]],
        [[s, w], [s, e], [n, e], [n, w]]
      ],
      {
        weight: 0,
        fillColor: "#1f2937",
        fillOpacity: 0.18,
        interactive: false
      }
    ).addTo(outsideLayer);
  }

  addOutsideMask();
  if (data.cityBoundary) {
    L.geoJSON(data.cityBoundary, {
      style: { color: "#374151", weight: 2, fill: false, interactive: false }
    }).addTo(map);
  }
  map.fitBounds(supportBounds);

  for (const edge of data.graph.edges) {
    edgesById.set(edge.id, edge);
    if (!adjacency.has(edge.u)) adjacency.set(edge.u, []);
    adjacency.get(edge.u).push(edge);
  }

  for (const shelter of data.shelters) {
    L.circleMarker([shelter.lat, shelter.lon], {
      radius: 5,
      color: "#047857",
      fillColor: "#10b981",
      fillOpacity: 0.8,
      weight: 1
    }).bindPopup(`${shelter.name}<br>収容人数: ${shelter.capacity}`).addTo(shelterLayer);
  }

  L.circleMarker([data.breachPoint.lat, data.breachPoint.lon], {
    radius: 7,
    color: "#b45309",
    fillColor: "#f59e0b",
    fillOpacity: 0.9,
    weight: 2
  }).bindPopup(`${data.breachPoint.name}<br>${data.breachPoint.note}`).addTo(map);

  const legend = L.control({ position: "bottomright" });
  legend.onAdd = function () {
    const div = L.DomUtil.create("div", "legend");
    div.innerHTML = [
      '<div class="legend-row"><span class="swatch swatch-river"></span>鬼怒川</div>
      <div class="legend-row"><span class="swatch swatch-flood"></span>シナリオ浸水範囲</div>',
      '<div class="legend-row"><span class="swatch swatch-closed"></span>閉鎖道路</div>',
      '<div class="legend-row"><span class="swatch swatch-route"></span>避難ルート</div>',
      '<div class="legend-row"><span class="swatch swatch-area"></span>市区町村境界</div>',
      '<div class="legend-row"><span class="swatch swatch-outside"></span>対応地域外</div>'
    ].join("");
    return div;
  };
  legend.addTo(map);

  let activeTime = data.times[0].id;
  let activeClick = null;

  function createTimeButtons() {
    const wrap = document.getElementById("time-buttons");
    for (const time of data.times) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "time-button";
      button.textContent = time.label;
      button.dataset.timeId = time.id;
      button.setAttribute("aria-pressed", time.id === activeTime ? "true" : "false");
      button.addEventListener("click", () => setTime(time.id));
      wrap.appendChild(button);
    }
  }

  function setTime(timeId) {
    activeTime = timeId;
    document.querySelectorAll(".time-button").forEach((button) => {
      button.setAttribute("aria-pressed", button.dataset.timeId === timeId ? "true" : "false");
    });
    updateScenarioLayers();
    if (activeClick) routeFromClick(activeClick);
  }

  function updateScenarioLayers() {
    const time = data.times.find((item) => item.id === activeTime);
    const closures = data.closures[activeTime] || [];
    floodLayer.clearLayers();
    floodLayer.addData(data.floods[activeTime]);
    closedLayer.clearLayers();

    for (const edgeId of closures) {
      const edge = edgesById.get(edgeId);
      if (!edge) continue;
      L.polyline(edge.coords, {
        color: "#dc2626",
        weight: 3,
        opacity: 0.65
      }).addTo(closedLayer);
    }

    document.getElementById("status-progress").textContent = `${time.progressPercent}%`;
    document.getElementById("status-closures").textContent = `${closures.length} 本`;
    document.getElementById("status-shelters").textContent = `${data.shelters.length} 施設`;
    document.getElementById("status-area").textContent = data.supportArea.label;
  }

  function nearestNode(latlng) {
    let best = null;
    let bestScore = Infinity;
    for (const [nodeId, coord] of Object.entries(nodes)) {
      const dy = coord[0] - latlng.lat;
      const dx = coord[1] - latlng.lng;
      const score = dx * dx + dy * dy;
      if (score < bestScore) {
        best = nodeId;
        bestScore = score;
      }
    }
    return best;
  }

  class MinHeap {
    constructor() {
      this.items = [];
    }
    push(item) {
      this.items.push(item);
      this.bubbleUp(this.items.length - 1);
    }
    pop() {
      if (this.items.length === 0) return null;
      const top = this.items[0];
      const last = this.items.pop();
      if (this.items.length > 0) {
        this.items[0] = last;
        this.sinkDown(0);
      }
      return top;
    }
    bubbleUp(index) {
      while (index > 0) {
        const parent = Math.floor((index - 1) / 2);
        if (this.items[parent].dist <= this.items[index].dist) break;
        [this.items[parent], this.items[index]] = [this.items[index], this.items[parent]];
        index = parent;
      }
    }
    sinkDown(index) {
      while (true) {
        const left = index * 2 + 1;
        const right = left + 1;
        let smallest = index;
        if (left < this.items.length && this.items[left].dist < this.items[smallest].dist) smallest = left;
        if (right < this.items.length && this.items[right].dist < this.items[smallest].dist) smallest = right;
        if (smallest === index) break;
        [this.items[smallest], this.items[index]] = [this.items[index], this.items[smallest]];
        index = smallest;
      }
    }
  }

  function shortestRoute(startNode, closedSet) {
    const targetNodes = new Set(data.shelters.map((shelter) => shelter.node));
    const dist = new Map([[startNode, 0]]);
    const prev = new Map();
    const heap = new MinHeap();
    heap.push({ node: startNode, dist: 0 });

    while (heap.items.length > 0) {
      const current = heap.pop();
      if (current.dist !== dist.get(current.node)) continue;
      if (targetNodes.has(current.node)) {
        return reconstruct(startNode, current.node, current.dist, prev);
      }
      for (const edge of adjacency.get(current.node) || []) {
        if (closedSet.has(edge.id)) continue;
        const nextDist = current.dist + edge.length;
        if (nextDist < (dist.get(edge.v) ?? Infinity)) {
          dist.set(edge.v, nextDist);
          prev.set(edge.v, { node: current.node, edgeId: edge.id });
          heap.push({ node: edge.v, dist: nextDist });
        }
      }
    }
    return null;
  }

  function reconstruct(startNode, targetNode, distance, prev) {
    const edgeIds = [];
    let current = targetNode;
    while (current !== startNode) {
      const step = prev.get(current);
      if (!step) break;
      edgeIds.push(step.edgeId);
      current = step.node;
    }
    edgeIds.reverse();
    const coords = [];
    for (const edgeId of edgeIds) {
      const edge = edgesById.get(edgeId);
      if (!edge) continue;
      for (const coord of edge.coords) {
        const last = coords[coords.length - 1];
        if (!last || last[0] !== coord[0] || last[1] !== coord[1]) {
          coords.push(coord);
        }
      }
    }
    const shelter = data.shelters.find((item) => item.node === targetNode);
    return { targetNode, shelter, distance, edgeIds, coords };
  }

  function routeFromClick(latlng) {
    activeClick = latlng;
    routeLayer.clearLayers();
    markerLayer.clearLayers();
    const result = document.getElementById("route-result");

    if (!supportBounds.contains(latlng)) {
      result.innerHTML = [
        "<strong>対応地域外です</strong>",
        `${data.supportArea.label}の範囲内をクリックしてください。`,
        "灰色の範囲は、このシミュレーション版の対象外です。"
      ].join("<br>");
      return;
    }

    L.marker(latlng).addTo(markerLayer);

    const startNode = nearestNode(latlng);
    const closedSet = new Set(data.closures[activeTime] || []);
    const route = shortestRoute(startNode, closedSet);

    if (!route || route.coords.length < 2) {
      result.textContent = "この時刻では到達可能な避難所が見つかりません。";
      return;
    }

    L.polyline(route.coords, {
      color: "#111827",
      weight: 5,
      opacity: 0.82
    }).addTo(routeLayer);

    const km = (route.distance / 1000).toFixed(2);
    result.innerHTML = [
      `<strong>${route.shelter.name}</strong>`,
      `距離: ${km} km`,
      `閉鎖回避: ${closedSet.size} 本の道路を除外`,
      `出発ノード: ${startNode}`
    ].join("<br>");
  }

  map.on("click", (event) => routeFromClick(event.latlng));
  createTimeButtons();
  updateScenarioLayers();

  // ------------------------------------------------------------------ Kinugawa River layer
  if (window.KINUGAWA_RIVER) {
    L.geoJSON(window.KINUGAWA_RIVER, {
      style: function (f) {
        var t = f.geometry ? f.geometry.type : "";
        if (t === "Polygon" || t === "MultiPolygon") {
          return { color: "#0d9488", weight: 1.5, opacity: 0.85, fillColor: "#0d9488", fillOpacity: 0.30 };
        }
        return { color: "#0d9488", weight: 3.5, opacity: 0.85, fill: false };
      }
    }).bindTooltip("鬼怒川", { sticky: true, direction: "top" }).addTo(map);
  }
})();
