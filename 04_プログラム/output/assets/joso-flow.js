(() => {
  "use strict";

  const timeline = document.querySelector("#simulation-time");
  if (!timeline) return;

  const events = [
    { title: "情報を準備します", description: "道路、浸水、避難所、人口、車両の情報を常総市にそろえます。" },
    { title: "浸水範囲が広がります", description: "時間の経過に合わせて、浸水する範囲と通れない道路を更新します。" },
    { title: "住民と車両が避難を始めます", description: "住民、車、迎えに行く車両が、それぞれの避難先へ移動します。" },
    { title: "通れない道路を避けます", description: "進む先が通れなくなった場合は、通行できる別の道を探します。" },
    { title: "到着状況を記録します", description: "避難先へ到着できたか、どのくらい時間がかかったかを記録します。" }
  ];

  const vehicleRoutes = {
    car: [[70, 424], [177, 366], [214, 354], [405, 398], [515, 365], [604, 337], [690, 401]],
    pickup: [[792, 105], [688, 176], [540, 229], [470, 238], [365, 266], [318, 273], [214, 285], [150, 175], [128, 104]],
    bus: [[598, 485], [600, 422], [604, 337], [648, 352], [711, 388], [690, 438]]
  };

  const storySteps = [...document.querySelectorAll("[data-step]")];
  const flowSteps = [...document.querySelectorAll("[data-flow-step]")];
  const checklist = [...document.querySelectorAll("[data-event-check]")];
  const floods = [...document.querySelectorAll("[data-flood-at]")];
  const closures = [...document.querySelectorAll("[data-closure-at]")];
  const vehicles = [...document.querySelectorAll("[data-vehicle]")];
  const dataSources = [...document.querySelectorAll("[data-source]")];
  const currentTime = document.querySelector("[data-current-time]");
  const timelineOutput = document.querySelector("[data-timeline-output]");
  const eventNumber = document.querySelector("[data-event-number]");
  const eventTitle = document.querySelector("[data-event-title]");
  const eventDescription = document.querySelector("[data-event-description]");
  const playButton = document.querySelector("[data-action='play']");
  const heroPlayButton = document.querySelector("[data-action='hero-play']");
  const playLabel = document.querySelector("[data-play-label]");
  const speedSelect = document.querySelector("[data-speed]");

  const endTime = Number(timeline.max);
  let simulationTime = Number(timeline.value);
  let playing = false;
  let speed = Number(speedSelect?.value || 1);
  let lastFrame = 0;

  const formatTime = (seconds) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}時間${String(minutes).padStart(2, "0")}分`;
  };

  const getStep = (progress) => Math.min(events.length - 1, Math.floor(progress * events.length));

  const pointOnRoute = (points, progress) => {
    const bounded = Math.max(0, Math.min(1, progress));
    const scaled = bounded * (points.length - 1);
    const index = Math.min(points.length - 2, Math.floor(scaled));
    const local = scaled - index;
    const start = points[index];
    const end = points[index + 1];
    return [start[0] + (end[0] - start[0]) * local, start[1] + (end[1] - start[1]) * local];
  };

  const updateVehicles = (progress, step) => {
    const travelProgress = Math.max(0, (progress - .34) / .66);
    vehicles.forEach((vehicle) => {
      const kind = vehicle.dataset.vehicle;
      const route = vehicleRoutes[kind];
      const offset = kind === "pickup" ? .04 : kind === "bus" ? .1 : 0;
      const [x, y] = pointOnRoute(route, travelProgress - offset);
      vehicle.setAttribute("transform", `translate(${x} ${y})`);
      vehicle.classList.toggle("is-visible", step >= 2);
    });
  };

  const update = () => {
    const progress = simulationTime / endTime;
    const step = getStep(progress);
    const floodStage = Math.min(4, Math.floor(progress * 5));

    timeline.value = String(Math.round(simulationTime));
    timeline.style.setProperty("--timeline-position", `${progress * 100}%`);
    currentTime.textContent = formatTime(simulationTime);
    timelineOutput.textContent = formatTime(simulationTime);
    eventNumber.textContent = String(step + 1);
    eventTitle.textContent = events[step].title;
    eventDescription.textContent = events[step].description;

    storySteps.forEach((item) => {
      const itemStep = Number(item.dataset.step);
      item.classList.toggle("is-active", itemStep === step);
      item.classList.toggle("is-complete", itemStep < step);
      if (itemStep === step) item.setAttribute("aria-current", "step");
      else item.removeAttribute("aria-current");
    });
    flowSteps.forEach((item) => item.classList.toggle("is-active", Number(item.dataset.flowStep) <= step));
    checklist.forEach((item) => {
      const itemStep = Number(item.dataset.eventCheck);
      item.classList.toggle("is-current", itemStep === step);
      item.classList.toggle("is-complete", itemStep < step);
    });
    floods.forEach((item) => item.classList.toggle("is-visible", Number(item.dataset.floodAt) <= floodStage));
    closures.forEach((item) => item.classList.toggle("is-visible", Number(item.dataset.closureAt) <= step));
    dataSources.forEach((item, index) => item.classList.toggle("is-feeding", index <= Math.min(dataSources.length - 1, Math.floor(progress * 8))));
    updateVehicles(progress, step);
  };

  const setPlaying = (nextPlaying) => {
    playing = nextPlaying;
    if (playLabel) playLabel.textContent = playing ? "一時停止" : "再生";
    if (playButton) {
      playButton.setAttribute("aria-pressed", String(playing));
      const icon = playButton.querySelector("path");
      if (icon) icon.setAttribute("d", playing ? "M5 4h3v12H5Zm7 0h3v12h-3Z" : "m7 4 8 6-8 6Z");
    }
    if (playing) {
      if (simulationTime >= endTime) simulationTime = 0;
      lastFrame = performance.now();
      requestAnimationFrame(tick);
    }
  };

  const tick = (now) => {
    if (!playing) return;
    const elapsed = Math.min(80, now - lastFrame);
    lastFrame = now;
    simulationTime = Math.min(endTime, simulationTime + elapsed * .6 * speed);
    update();
    if (simulationTime >= endTime) setPlaying(false);
    else requestAnimationFrame(tick);
  };

  playButton?.addEventListener("click", () => setPlaying(!playing));
  heroPlayButton?.addEventListener("click", () => {
    document.querySelector("#simulation")?.scrollIntoView({ behavior: "smooth", block: "start" });
    window.setTimeout(() => setPlaying(true), 350);
  });
  document.querySelector("[data-action='reset']")?.addEventListener("click", () => {
    setPlaying(false);
    simulationTime = 0;
    update();
  });
  speedSelect?.addEventListener("change", () => { speed = Number(speedSelect.value); });
  timeline.addEventListener("input", () => {
    setPlaying(false);
    simulationTime = Number(timeline.value);
    update();
  });
  storySteps.forEach((item) => item.addEventListener("click", () => {
    setPlaying(false);
    const step = Number(item.dataset.step);
    simulationTime = step === events.length - 1 ? endTime : (endTime / events.length) * step + 1;
    update();
  }));

  const roleLabels = {
    population_and_types: "人口・支援の必要度",
    rescue_substitution_and_fixed_shelter: "出発地と避難先",
    safe_shelters: "避難所",
    true_closure_timeline: "時間ごとの通れない道路",
    time_mapping: "実際の時刻との対応",
    drt_initial_vehicle_edges: "迎えに行く車両の出発位置",
    private_vehicle_demand: "自家用車の移動",
    sumo_network: "交通を再現する道路"
  };

  const setConfigText = (name, value) => {
    const target = document.querySelector(`[data-config='${name}']`);
    if (target) target.textContent = value;
  };
  const fileName = (path) => path.split(/[\\/]/).pop();

  const loadTechnicalData = async () => {
    const status = document.querySelector("[data-config-status]");
    try {
      const [parametersResponse, sourcesResponse] = await Promise.all([
        fetch("../config/jdrt_parameters_v2.json"),
        fetch("../config/jdrt_input_sources_v1.json")
      ]);
      if (!parametersResponse.ok || !sourcesResponse.ok) throw new Error("設定ファイルを取得できませんでした");
      const parameters = await parametersResponse.json();
      const sources = await sourcesResponse.json();

      setConfigText("city-code", parameters.city_code);
      setConfigText("simulation-hours", `${parameters.simulation_end_sec / 3600}時間`);
      setConfigText("origin-count", `${parameters.population.origin_count.toLocaleString("ja-JP")}地点`);
      setConfigText("shelter-count", `${parameters.shelters.expected_count.toLocaleString("ja-JP")}か所`);
      setConfigText("private-vehicles", `${parameters.traffic_demand.private_vehicle_count.toLocaleString("ja-JP")}台`);
      setConfigText("fleet-total", `${parameters.fleet.total.toLocaleString("ja-JP")}台`);
      const closureSource = sources.files.find((item) => item.role === "true_closure_timeline");
      setConfigText("closure-steps", `${closureSource?.expected_time_steps ?? "—"}時点`);
      setConfigText("core-runs", `${parameters.experiment.expected_core_run_count.toLocaleString("ja-JP")}回を事前に設定`);

      const tbody = document.querySelector("[data-source-files]");
      if (tbody) {
        tbody.replaceChildren(...sources.files.map((source) => {
          const row = document.createElement("tr");
          const label = document.createElement("td");
          const file = document.createElement("td");
          const unit = document.createElement("td");
          label.textContent = roleLabels[source.role] || source.role;
          file.textContent = fileName(source.path);
          unit.textContent = source.expected_filtered_rows
            ? `${source.expected_filtered_rows.toLocaleString("ja-JP")}行（使用分）`
            : source.expected_rows
              ? `${source.expected_rows.toLocaleString("ja-JP")}行`
              : source.expected_time_steps
                ? `${source.expected_time_steps.toLocaleString("ja-JP")}時点`
                : "ファイル全体";
          row.append(label, file, unit);
          return row;
        }));
      }
      if (status) status.textContent = "";
    } catch (error) {
      document.querySelectorAll("[data-config]").forEach((item) => { item.textContent = "設定JSON参照"; });
      if (status) status.textContent = "数値は設定JSONを正本としています。直接ファイルとして開いた場合は、下のJSONリンクから確認できます。";
    }
  };

  update();
  loadTechnicalData();
})();
