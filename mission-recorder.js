const STORAGE_KEY = "astra-flight-recorder-v1";
const MAX_SAMPLES = 4096;
const SCHEMA = "ASTRA-FLIGHT-RECORDER-5";
const DB_NAME = "astra-mission-data";
const DB_STORE = "recordings";
const DB_RECORD = "latest";

let databasePromise;

function openRecorderDatabase() {
  if (!globalThis.indexedDB) return Promise.resolve(null);
  if (databasePromise) return databasePromise;
  databasePromise = new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(DB_STORE);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error("IndexedDB non disponibile"));
    request.onblocked = () => reject(new Error("Database ASTRA bloccato"));
  }).catch(() => null);
  return databasePromise;
}

function snapshotValue(value) {
  if (value === null || typeof value === "string" || typeof value === "boolean") return value;
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (Array.isArray(value)) return value.map(snapshotValue);
  if (typeof value === "object") {
    return Object.fromEntries(Object.entries(value)
      .filter(([, item]) => item !== undefined)
      .map(([key, item]) => [key, snapshotValue(item)]));
  }
  return null;
}

function csvCell(value) {
  if (value === null) return "null";
  if (value === undefined) return "";
  const text = typeof value === "string" ? value : String(value);
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function flatten(value, prefix, output) {
  if (Array.isArray(value)) {
    if (!value.length) output[prefix] = "[]";
    else value.forEach((item, index) => flatten(item, `${prefix}[${index}]`, output));
  } else if (value && typeof value === "object") {
    const entries = Object.entries(value);
    if (!entries.length) output[prefix] = "{}";
    else entries.forEach(([key, item]) => flatten(item, prefix ? `${prefix}.${key}` : key, output));
  } else {
    output[prefix] = value;
  }
}

function fieldUnit(path) {
  const name = path.replace(/\[\d+\]/g, "[]").replace(/\[\]/g, "");
  const units = [
    // Match compound force/moment units before the generic `_m_s` speed suffix.
    ["_N_m_s", "N·m·s"], ["_N_m", "N·m"],
    ["_m_s2", "m/s^2"], ["_rad_s2", "rad/s^2"], ["_m3_s2", "m^3/s^2"],
    ["_m_s", "m/s"], ["_rad_s", "rad/s"], ["_m3_s", "m^3/s"],
    ["_kg_m3", "kg/m^3"], ["_J_kg", "J/kg"],
    ["_W_m2", "W/m^2"], ["_J_m2", "J/m^2"], ["_m2", "m^2"],
    ["_m3", "m^3"], ["_deg", "deg"], ["_rad", "rad"],
    ["_kg", "kg"], ["_Pa", "Pa"], ["_K", "K"], ["_N", "N"],
    ["_pct", "%"], ["_g", "g"], ["_s", "s"], ["_m", "m"],
  ];
  return units.find(([suffix]) => name.endsWith(suffix))?.[1] || null;
}

function stateFieldCatalog(samples) {
  const fields = new Map();
  const record = (path, value, sampleIndex) => {
    const field = fields.get(path) || {
      path, types: new Set(), present_sample_indices: new Set(), null_sample_indices: new Set(),
    };
    field.present_sample_indices.add(sampleIndex);
    if (value === null) field.null_sample_indices.add(sampleIndex);
    else field.types.add(value);
    fields.set(path, field);
  };
  const visit = (value, path, sampleIndex) => {
    if (Array.isArray(value)) {
      if (!value.length) record(`${path}[]`, "array", sampleIndex);
      else value.forEach(item => visit(item, `${path}[]`, sampleIndex));
      return;
    }
    if (value && typeof value === "object") {
      const entries = Object.entries(value);
      if (!entries.length) record(path, "object", sampleIndex);
      else entries.forEach(([key, item]) => visit(item, path ? `${path}.${key}` : key, sampleIndex));
      return;
    }
    record(path, value === null ? null : typeof value, sampleIndex);
  };

  samples.forEach((sample, sampleIndex) => {
    if (sample.state) visit(sample.state, "", sampleIndex);
  });
  return [...fields.values()].sort((a, b) => a.path.localeCompare(b.path)).map(field => ({
    path: field.path,
    unit: fieldUnit(field.path),
    types: [...field.types].sort(),
    present_samples: field.present_sample_indices.size,
    null_samples: field.null_sample_indices.size,
    absent_samples: samples.length - field.present_sample_indices.size,
  }));
}

const SIGNALS = {
  altitude_m: { label: "ALTITUDINE", unit: "m", color: "#b9aff3" },
  speed_m_s: { label: "VELOCITÀ", unit: "m/s", color: "#8997d0" },
  dynamic_pressure_Pa: { label: "PRESSIONE DINAMICA", unit: "Pa", color: "#d1c4ef" },
  load_factor_g: { label: "FATTORE DI CARICO", unit: "g", color: "#9ea5de" },
  stagnation_point_convective_heat_flux_W_m2: { label: "FLUSSO TERMICO DI RISTAGNO", unit: "W/m²", color: "#c0b1e5" },
  stagnation_point_convective_heat_load_J_m2: { label: "CARICO TERMICO CONVETTIVO", unit: "J/m²", color: "#858dc1" },
  attitude_error_deg: { label: "ERRORE D’ASSETTO", unit: "deg", color: "#d4c9f8" },
  acs_propellant_kg: { label: "RISERVA ACS", unit: "kg", color: "#abb3e1" },
  resource_percent: { label: "RISORSA", unit: "%", color: "#c5beef" },
};

const finite = value => Number.isFinite(value) ? value : null;
const copyVector = value => Array.isArray(value) && value.length >= 3
  ? value.slice(0, 3).map(finite) : null;

export class MissionRecorder {
  constructor(storage) {
    this.storage = storage ?? null;
    this.samples = [];
    this.metadata = null;
    this.lastTime = -Infinity;
    this.lastPhase = "";
    this.samplesSinceSave = 0;
    this.totalCaptured = 0;
    this.storageAvailable = null;
    this.wasDownsampled = false;
    this.hasStarted = false;
    this.persistTimer = null;
    this.databaseAvailable = false;
    this.persistedSampleCount = 0;
    this.needsFullRewrite = true;
    this.legacyRecord = null;
    try {
      if (!this.storage) this.storage = globalThis.localStorage;
      const saved = JSON.parse(this.storage?.getItem(STORAGE_KEY) || "null");
      if (saved && Array.isArray(saved.samples)) {
        this.legacyRecord = saved;
      }
    } catch {
      this.storageAvailable = false;
    }
    this.ready = this.restoreFromDatabase();
  }

  restoreRecord(record) {
    this.samples = record.samples.slice(-MAX_SAMPLES);
    this.metadata = record.metadata || null;
    this.wasDownsampled = !!record.sampling?.downsampled;
    this.totalCaptured = record.sampling?.total_captured || this.samples.length;
    const latest = this.samples[this.samples.length - 1];
    this.lastTime = Number.isFinite(latest?.time_s) ? latest.time_s : -Infinity;
    this.lastPhase = latest?.phase || "";
    this.storageAvailable = true;
  }

  async restoreFromDatabase() {
    const database = await openRecorderDatabase();
    this.databaseAvailable = !!database;
    if (!database) {
      if (!this.hasStarted && this.legacyRecord) {
        this.restoreRecord(this.legacyRecord);
      }
      return false;
    }
    try {
      const transaction = database.transaction(DB_STORE, "readonly");
      const request = transaction.objectStore(DB_STORE).openCursor();
      const saved = await new Promise((resolve, reject) => {
        let metadata = null;
        const chunks = [];
        request.onsuccess = () => {
          const cursor = request.result;
          if (!cursor) {
            if (metadata?.samples) resolve(metadata);
            else if (metadata) {
              chunks.sort((a, b) => a.start - b.start);
              resolve({ ...metadata, samples: chunks.flatMap(chunk => chunk.samples) });
            } else resolve(null);
            return;
          }
          if (cursor.key === DB_RECORD) metadata = cursor.value;
          else if (typeof cursor.key === "string" && cursor.key.startsWith("chunk:")) {
            chunks.push({ start: Number(cursor.key.slice(6)), samples: cursor.value });
          }
          cursor.continue();
        };
        request.onerror = () => reject(request.error || new Error("Lettura ASTRA non riuscita"));
      });
      const record = saved && Array.isArray(saved.samples) ? saved : this.legacyRecord;
      if (!this.hasStarted && record) {
        this.restoreRecord(record);
        this.persistedSampleCount = saved?.storage_layout === "chunked-v1"
          ? this.samples.length : 0;
        this.needsFullRewrite = saved?.storage_layout !== "chunked-v1";
        if (this.needsFullRewrite) this.persist();
      }
      return true;
    } catch {
      if (!this.hasStarted && this.legacyRecord) {
        this.restoreRecord(this.legacyRecord);
      } else this.storageAvailable = false;
      return false;
    }
  }

  start(metadata) {
    this.hasStarted = true;
    this.samples = [];
    this.totalCaptured = 0;
    this.metadata = { ...snapshotValue(metadata || {}), started_at_utc: new Date().toISOString() };
    this.lastTime = -Infinity;
    this.lastPhase = "";
    this.samplesSinceSave = 0;
    this.wasDownsampled = false;
    this.persistedSampleCount = 0;
    this.needsFullRewrite = true;
    this.persist();
  }

  capture(engineState) {
    if (!engineState?.mission_started || !Number.isFinite(engineState.time_s)) return false;
    const phase = String(engineState.phase || "UNKNOWN");
    const time = engineState.time_s;
    if (time < this.lastTime) return false;
    const phaseChanged = phase !== this.lastPhase;
    if (!phaseChanged && time - this.lastTime < 1.0) return false;

    const environment = engineState.environment || {};
    const missionMetrics = engineState.mission_metrics || {};
    const sample = {
      time_s: time,
      phase,
      altitude_m: finite(engineState.altitude_m),
      speed_m_s: finite(engineState.speed_m_s),
      dynamic_pressure_Pa: finite(environment.dynamic_pressure_Pa),
      load_factor_g: finite(engineState.load_factor_g),
      stagnation_point_convective_heat_flux_W_m2: finite(
        environment.stagnation_point_convective_heat_flux_W_m2),
      stagnation_point_convective_heat_load_J_m2: finite(
        missionMetrics.stagnation_point_convective_heat_load_J_m2),
      resource_percent: finite(engineState.battery_pct ?? engineState.propellant_pct),
      mass_kg: finite(engineState.mass_kg),
      propellant_kg: finite(engineState.propellant_kg),
      acs_propellant_kg: finite(engineState.acs_propellant_kg),
      attitude_error_deg: finite(engineState.attitude_error_deg),
      frame: engineState.frame || null,
      position_eci_m: copyVector(engineState.position_eci_m),
      velocity_eci_m_s: copyVector(engineState.velocity_eci_m_s),
      position_ned_m: Array.isArray(engineState.position_ned_m)
        ? engineState.position_ned_m.slice(0, 3).map(finite) : null,
      attitude_deg: Array.isArray(engineState.attitude_deg)
        ? engineState.attitude_deg.slice(0, 3).map(finite) : null,
      attitude_command_deg: Array.isArray(engineState.attitude_command_deg)
        ? engineState.attitude_command_deg.slice(0, 3).map(finite) : null,
      orbital_elements: snapshotValue(engineState.orbital_elements || null),
      orbit_type: engineState.orbital_elements?.orbit_type || null,
      density_kg_m3: finite(environment.density_kg_m3),
      temperature_K: finite(environment.temperature_K),
      pressure_Pa: finite(environment.pressure_Pa),
      active_stage: finite(engineState.active_stage),
      snapshot_complete: true,
      state: snapshotValue(engineState),
    };
    this.samples.push(sample);
    this.totalCaptured += 1;
    this.lastTime = time;
    this.lastPhase = phase;
    this.samplesSinceSave += 1;

    if (this.samples.length > MAX_SAMPLES) this.downsample();
    if (this.samples.length === 1 || phaseChanged || this.samplesSinceSave >= 8) this.persist();
    if (["LANDED", "CRASHED", "ABORTED"].includes(phase)) this.persist();
    return true;
  }

  downsample() {
    const reduced = this.samples.filter((sample, index, samples) =>
      index === 0 || index === samples.length - 1 || index % 2 === 0 ||
      sample.phase !== samples[index - 1].phase);
    this.samples = reduced.slice(-MAX_SAMPLES);
    this.wasDownsampled = true;
    this.needsFullRewrite = true;
  }

  persist() {
    this.samplesSinceSave = 0;
    if (this.persistTimer) clearTimeout(this.persistTimer);
    const record = this.storageRecord();
    this.persistTimer = setTimeout(() => {
      this.persistTimer = null;
      void this.writeRecord(record);
    }, 300);
  }

  storageRecord() {
    return {
      schema: SCHEMA,
      metadata: this.metadata,
      sampling: { downsampled: this.wasDownsampled, total_captured: this.totalCaptured },
      samples: this.samples.slice(),
    };
  }

  async writeRecord(record) {
    const database = await openRecorderDatabase();
    this.databaseAvailable = !!database;
    if (database) {
      try {
        const transaction = database.transaction(DB_STORE, "readwrite");
        const store = transaction.objectStore(DB_STORE);
        const rewrite = this.needsFullRewrite || record.samples.length < this.persistedSampleCount;
        if (rewrite) store.clear();
        store.put({ schema: record.schema, metadata: record.metadata,
          sampling: record.sampling, storage_layout: "chunked-v1" }, DB_RECORD);
        const first = rewrite ? 0 : this.persistedSampleCount;
        for (let index = first; index < record.samples.length; index += 32) {
          const chunkKey = `chunk:${String(index).padStart(6, "0")}`;
          store.put(record.samples.slice(index, index + 32), chunkKey);
        }
        await new Promise((resolve, reject) => {
          transaction.oncomplete = resolve;
          transaction.onerror = () => reject(transaction.error || new Error("Salvataggio ASTRA non riuscito"));
          transaction.onabort = () => reject(transaction.error || new Error("Salvataggio ASTRA interrotto"));
        });
        this.persistedSampleCount = record.samples.length;
        this.needsFullRewrite = false;
        this.storageAvailable = true;
        this.onStorageChange?.();
        return;
      } catch {
        this.storageAvailable = false;
      }
    }
    try {
      if (!this.storage) throw new Error("Storage locale non disponibile");
      if (record.samples.length) this.storage?.setItem(STORAGE_KEY, JSON.stringify(record));
      else this.storage?.removeItem(STORAGE_KEY);
      this.storageAvailable = true;
    } catch {
      this.storageAvailable = false;
    }
    this.onStorageChange?.();
  }

  exportObject() {
    return {
      schema: SCHEMA,
      snapshot_completeness: this.samples.length && this.samples.every(sample => sample.snapshot_complete && sample.state)
        ? "complete"
        : this.samples.some(sample => sample.state) ? "mixed" : "legacy_summary_only",
      api_schema: "ASTRA state endpoint v1.0; each sample.state preserves the complete returned state",
      state_value_convention: "Unità SI; le grandezze angolari sono espresse nel suffisso _deg o _rad, valori categoriali e booleani non hanno unità",
      metadata: this.metadata,
      sampling: {
        maximum_samples: MAX_SAMPLES,
        interval_strategy: "1 s of simulation time; phase transitions are always sampled",
        downsampled: this.wasDownsampled,
        total_captured: this.totalCaptured,
        retained_samples: this.samples.length,
      },
      data_dictionary: {
        scope: "All fields returned in each complete state API snapshot; null means unavailable, absent_samples means the field was not returned for that sample's vehicle or scenario.",
        fields: stateFieldCatalog(this.samples),
      },
      units: {
        time_s: "s", altitude_m: "m", speed_m_s: "m/s",
        dynamic_pressure_Pa: "Pa", load_factor_g: "g", resource_percent: "%", mass_kg: "kg",
        specific_force_magnitude_m_s2: "m/s^2",
        stagnation_point_convective_heat_flux_W_m2: "W/m^2",
        stagnation_point_convective_heat_load_J_m2: "J/m^2",
        propellant_kg: "kg", position_eci_m: "m", velocity_eci_m_s: "m/s",
        position_ned_m: "m", attitude_deg: "deg", density_kg_m3: "kg/m^3",
        temperature_K: "K", pressure_Pa: "Pa",
      },
      samples: this.samples,
    };
  }

  download(format) {
    if (!this.samples.length) return false;
    this.persist();
    const stem = `astra-mission-${new Date().toISOString().replaceAll(":", "-")}`;
    let content, mime, extension;
    if (format === "csv") {
      const flattened = this.samples.map((sample, index) => {
        const row = { sample_index: index, snapshot_complete: !!sample.state };
        flatten(this.metadata || {}, "mission", row);
        const summary = { ...sample };
        delete summary.state;
        flatten(summary, "sample", row);
        if (sample.state) flatten(sample.state, "state", row);
        return row;
      });
      const columns = [...new Set(flattened.flatMap(row => Object.keys(row)))];
      const rows = flattened.map(row => columns.map(column => csvCell(row[column])).join(","));
      content = [columns.join(","), ...rows].join("\r\n");
      mime = "text/csv;charset=utf-8";
      extension = "csv";
    } else {
      content = JSON.stringify(this.exportObject(), null, 2);
      mime = "application/json";
      extension = "json";
    }
    const url = URL.createObjectURL(new Blob([content], { type: mime }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${stem}.${extension}`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    return true;
  }
}

function timeLabel(seconds) {
  const value = Math.max(0, Math.floor(seconds || 0));
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor(value % 3600 / 60);
  const remainder = value % 60;
  return hours ? `T+ ${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`
    : `T+ ${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
}

function valueLabel(value, signal) {
  if (!Number.isFinite(value)) return "—";
  const decimals = Math.abs(value) >= 100 ? 0 : Math.abs(value) >= 10 ? 1 : 2;
  return `${value.toLocaleString("it-IT", { maximumFractionDigits: decimals })} ${SIGNALS[signal].unit}`;
}

export function bindMissionDataLab(recorder, options = {}) {
  const dialog = document.querySelector("#missionDataDialog");
  const canvas = document.querySelector("#missionPlot");
  const range = document.querySelector("#missionSampleRange");
  const signal = document.querySelector("#recorderSignal");
  const robustnessButton = document.querySelector("#runRobustness");
  const robustnessStatus = document.querySelector("#robustnessStatus");
  const robustnessResults = document.querySelector("#robustnessResults");
  const convergenceButton = document.querySelector("#runConvergence");
  const convergenceStatus = document.querySelector("#convergenceStatus");
  const convergenceResults = document.querySelector("#convergenceResults");
  const faultType = document.querySelector("#faultType");
  const faultSeverityWrap = document.querySelector("#faultSeverityWrap");
  const faultSeverity = document.querySelector("#faultSeverity");
  const faultSeverityOut = document.querySelector("#faultSeverityOut");
  const faultRotorWrap = document.querySelector("#faultRotorWrap");
  const faultRotorIndex = document.querySelector("#faultRotorIndex");
  const injectFaultButton = document.querySelector("#injectFault");
  const clearFaultsButton = document.querySelector("#clearInjectedFaults");
  const faultStatus = document.querySelector("#faultLabStatus");
  const faultEventLog = document.querySelector("#faultEventLog");
  let robustnessCampaign = null;
  let convergenceStudy = null;
  let faultUiVehicle = null;
  let faultUiRotorCount = 0;
  let faultEventKey = "";
  const samples = () => recorder.samples;
  const close = () => dialog?.close();

  function updateFaultManagement(data) {
    if (!faultStatus || !faultType) return;
    const config = options.faultConfig?.() || {};
    const vehicle = config.vehicle || data?.vehicle || "space";
    const management = data?.fault_management || {};
    const count = Math.max(1, Number(config.rotorCount ||
      data?.vehicle_parameters?.rotors || 4));
    if (count !== faultUiRotorCount) {
      const previousRotor = faultRotorIndex.value;
      faultRotorIndex.replaceChildren(...Array.from({ length: count }, (_, index) => {
        const option = document.createElement("option");
        option.value = String(index);
        option.textContent = `ROTORE ${String(index + 1).padStart(2, "0")}`;
        return option;
      }));
      if (previousRotor !== "" && Number(previousRotor) < count) faultRotorIndex.value = previousRotor;
      faultUiRotorCount = count;
    }
    if (vehicle !== faultUiVehicle) {
      for (const option of faultType.options) {
        option.hidden = option.dataset.vehicle !== vehicle;
      }
      const available = [...faultType.options].find(option => !option.hidden);
      if (available && faultType.selectedOptions[0]?.hidden) faultType.value = available.value;
      faultUiVehicle = vehicle;
    }
    const isDrone = vehicle === "drone";
    faultRotorWrap.hidden = !isDrone;
    faultSeverity.max = isDrone ? "100" : "95";
    const orbitalUnsupported = vehicle === "space" &&
      (config.scenario || data?.scenario) === "orbital";
    injectFaultButton.disabled = Boolean(management.active_faults?.length) || orbitalUnsupported;
    clearFaultsButton.disabled = !management.active_faults?.length;
    const active = management.active_faults?.[0];
    const sensorFault = active?.type === "barometer_dropout" ||
      active?.type === "gnss_dropout";
    faultSeverityWrap.hidden = sensorFault ||
      (!active && (faultType.value === "barometer_dropout" || faultType.value === "gnss_dropout"));
    faultSeverity.disabled = sensorFault;
    faultRotorWrap.hidden = !isDrone || faultType.value !== "rotor_thrust_loss";
    const residual = active?.last_residual_fraction;
    faultStatus.dataset.mode = management.mode || "NOMINAL";
    if (orbitalUnsupported) {
      faultStatus.textContent = "Guasto non disponibile in questo scenario: il rendezvous usa propulsori RCS distinti dal motore principale.";
    } else if (active) {
      const residualText = Number.isFinite(residual) ?
        ` · residuo ${(100 * residual).toFixed(1)}%` : "";
      const detectedAt = active.detection_time_s == null ? "" :
        ` · rilevato a T+${active.detection_time_s.toFixed(2)} s`;
      if (sensorFault) {
        const sensor = active.type === "barometer_dropout" ? "barometro" : "GNSS";
        if (management.recovery_automation === "AUTOMATIC_TAKEOFF_ABORT") {
          faultStatus.textContent = `FDIR · DECOLLO ANNULLATO PER PERDITA ${sensor.toUpperCase()}${detectedAt}. Il drone resta al suolo.`;
        } else if (management.recovery_automation === "AUTOMATIC_SENSOR_LANDING") {
          faultStatus.textContent = `FDIR · PERDITA GNSS${detectedAt}. Il drone sta atterrando sul punto stimato al momento del guasto; la guida usa INS e quota disponibile.`;
        } else if (management.recovery_automation === "SENSOR_FAILSAFE_LANDED") {
          faultStatus.textContent = `FDIR · ATTERRAGGIO LOCALE COMPLETATO${detectedAt}. Il drone è atterrato vicino al punto stimato quando è mancato il GNSS.`;
        } else if (management.recovery_automation === "SENSOR_FAILSAFE_FAILED") {
          faultStatus.textContent = `FDIR · ATTERRAGGIO LOCALE NON RIUSCITO${detectedAt}. Consulta velocità e posizione d’impatto nei dati missione.`;
        } else {
          faultStatus.textContent = active.detected ?
            `FDIR · PERDITA ${sensor.toUpperCase()} RILEVATA${detectedAt}. Il filtro dichiara la modalità degradata e mostra la sorgente alternativa o l’INS con la relativa incertezza.` :
            `PERDITA ${sensor.toUpperCase()} ATTIVA · FDIR attende due epoche senza fix; il filtro aggiorna l’incertezza della stima.`;
        }
      } else if (management.mode === "AUTOMATIC_ABORT") {
        const isSpace = vehicle === "space";
        faultStatus.textContent = isSpace ?
          `FDIR · GUASTO RILEVATO · LANCIO INIBITO${residualText}${detectedAt}. T/W ≤ 1: motore disattivato e veicolo trattenuto sulla rampa.` :
          `FDIR · GUASTO RILEVATO · DECOLLO ANNULLATO${residualText}${detectedAt}. Spinta azzerata e veicolo mantenuto a terra.`;
      } else if (management.mode === "AUTOMATIC_RECOVERY") {
        if (management.recovery_automation === "AUTOMATIC_FORCED_LANDING") {
          faultStatus.textContent =
            `FDIR · PLANATA D’EMERGENZA${residualText}${detectedAt}. Autopilota: velocità di massima efficienza e atterraggio forzato lungo la traccia GNSS stimata.`;
        } else if (management.recovery_automation === "FORCED_LANDING_COMPLETED") {
          faultStatus.textContent =
            `FDIR · ATTERRAGGIO FORZATO COMPLETATO${residualText}${detectedAt}. L’aereo ha arrestato la corsa dopo il contatto.`;
        } else if (management.recovery_automation === "FORCED_LANDING_FAILED") {
          faultStatus.textContent =
            `FDIR · ATTERRAGGIO FORZATO NON RIUSCITO${residualText}${detectedAt}. Verifica i dati di impatto della missione.`;
        } else if (management.recovery_automation === "RECOVERY_LANDED") {
          faultStatus.textContent =
            `FDIR · RIENTRO COMPLETATO${residualText}${detectedAt}. Atterraggio concluso dopo la riconfigurazione del mixer.`;
        } else if (management.recovery_automation === "RECOVERY_FAILED_IMPACT") {
          faultStatus.textContent =
            `FDIR · RISPOSTA AUTOMATICA NON RIUSCITA${residualText}${detectedAt}. L’impatto ha superato il limite di touchdown del modello.`;
        } else {
          faultStatus.textContent =
            `FDIR · GUASTO ISOLATO${residualText}${detectedAt}. Mixer compensato con i rotori sani; missione deviata al rientro e atterraggio automatico.`;
        }
      } else if (management.mode === "DETECTED_ADVISORY") {
        const recovery = management.recovery_automation || "ADVISORY_ONLY";
        const recoveryNote = recovery === "BEST_GLIDE_ADVISORY" ?
          " Risposta automatica non attiva: valutare la planata e il rientro manuale." :
          recovery.startsWith("ADVISORY_ONLY") ?
            " Perdita fuori dall’inviluppo di recupero automatico dichiarato; risposta consultiva." :
            " Le azioni in volo restano consultive.";
        faultStatus.textContent =
          `FDIR · GUASTO RILEVATO E ISOLATO${residualText}${detectedAt}.${recoveryNote}`;
      } else {
        faultStatus.textContent =
          `GUASTO ATTIVO · IN ATTESA DELLA FINESTRA DI RILEVAMENTO${residualText}${detectedAt}.`;
      }
    } else if (management.mode === "AUTOMATIC_ABORT") {
      faultStatus.textContent = vehicle === "space" ?
        "FDIR · LANCIO INIBITO: T/W residuo insufficiente. Riavvia la missione dopo il ripristino." :
        "FDIR · DECOLLO ANNULLATO: spinta anomala rilevata a terra. Riavvia la missione dopo aver ripristinato il veicolo.";
    } else if (management.recovery_automation === "RECOVERY_LANDED") {
      faultStatus.textContent = "FDIR · RIENTRO COMPLETATO: il veicolo è atterrato dopo la riconfigurazione del mixer.";
    } else if (management.recovery_automation === "RECOVERY_FAILED_IMPACT") {
      faultStatus.textContent = "FDIR · RISPOSTA AUTOMATICA NON RIUSCITA: l’impatto ha superato il limite di touchdown del modello.";
    } else if (management.recovery_automation === "FORCED_LANDING_COMPLETED") {
      faultStatus.textContent = "FDIR · ATTERRAGGIO FORZATO COMPLETATO: l’aereo è fermo dopo il rientro d’emergenza.";
    } else if (management.recovery_automation === "FORCED_LANDING_FAILED") {
      faultStatus.textContent = "FDIR · ATTERRAGGIO FORZATO NON RIUSCITO: consulta velocità e posizione nel Mission Data Lab.";
    } else if (management.recovery_automation === "AUTOMATIC_FORCED_LANDING") {
      faultStatus.textContent = "FDIR · PLANATA D’EMERGENZA: l’autopilota sta mantenendo la traccia GNSS stimata e prepara l’atterraggio forzato.";
    } else if (management.recovery_automation === "AUTOMATIC_SENSOR_LANDING") {
      faultStatus.textContent = "FDIR · ATTERRAGGIO LOCALE: il drone sta scendendo sul punto stimato dopo la perdita GNSS.";
    } else if (management.recovery_automation === "SENSOR_FAILSAFE_LANDED") {
      faultStatus.textContent = "FDIR · ATTERRAGGIO LOCALE COMPLETATO: il drone è atterrato sul punto stimato dopo la perdita GNSS.";
    } else if (management.recovery_automation === "SENSOR_FAILSAFE_FAILED") {
      faultStatus.textContent = "FDIR · ATTERRAGGIO LOCALE NON RIUSCITO: consulta velocità e posizione d’impatto nei dati missione.";
    } else {
      faultStatus.textContent = "Nessun guasto attivo. Inietta un guasto prima del lancio o durante la missione per osservare la risposta del monitor.";
    }
    const eventLabels = {
      FAULT_INJECTED: "Guasto iniettato",
      SENSOR_FAULT_DETECTED: "FDIR: perdita sensore rilevata",
      SENSOR_FAULT_CLEARED: "Segnale sensore ripristinato",
      SENSOR_FAILSAFE_LANDING_STARTED: "FDIR: atterraggio locale avviato",
      SENSOR_FAILSAFE_LANDING_COMPLETED: "FDIR: atterraggio locale completato",
      SENSOR_FAILSAFE_LANDING_FAILED: "FDIR: touchdown locale fuori limite",
      FAULT_DETECTED_AND_ISOLATED: "FDIR: anomalia rilevata e isolata",
      GROUND_HOLD_ABORT: "FDIR: spinta/peso insufficiente, lancio inibito",
      TAKEOFF_ABORT: "FDIR: decollo annullato in sicurezza",
      AUTOMATIC_RETURN_LAND: "FDIR: mixer riconfigurato, rientro automatico",
      AUTOMATIC_RECOVERY_FAILED: "FDIR: atterraggio automatico non riuscito",
      AUTOMATIC_FORCED_LANDING: "FDIR: planata e atterraggio forzato avviati",
      FORCED_LANDING_COMPLETED: "FDIR: atterraggio forzato completato",
      FAULT_CLEARED: "Effetto del guasto rimosso",
    };
    const events = (management.events || []).slice(-6);
    const eventKey = events.map(event => `${event.event}:${event.fault_id}:${event.time_s}`).join("|");
    if (eventKey !== faultEventKey) {
      faultEventLog.replaceChildren(...events.map(event => {
        const row = document.createElement("li");
        const time = document.createElement("time");
        time.textContent = `T+${Number(event.time_s || 0).toFixed(2)} s`;
        const message = document.createElement("span");
        const percent = Number.isFinite(event.residual_fraction) ?
          ` · residuo ${(100 * event.residual_fraction).toFixed(1)}%` : "";
        message.textContent = `${eventLabels[event.event] || event.event} · ${event.fault_id}${percent}`;
        row.append(time, message);
        return row;
      }));
      faultEventKey = eventKey;
    }
  }

  faultSeverity.addEventListener("input", () => {
    faultSeverityOut.value = `${faultSeverity.value}%`;
    faultSeverityOut.textContent = `${faultSeverity.value}%`;
  });
  faultType.addEventListener("change", () => {
    const sensorFault = faultType.value === "barometer_dropout" ||
      faultType.value === "gnss_dropout";
    const isDrone = faultType.value === "rotor_thrust_loss";
    faultSeverityWrap.hidden = sensorFault;
    faultSeverity.disabled = sensorFault;
    faultRotorWrap.hidden = !isDrone;
    faultSeverity.max = isDrone ? "100" : "95";
    if (Number(faultSeverity.value) > Number(faultSeverity.max)) {
      faultSeverity.value = faultSeverity.max;
      faultSeverityOut.value = `${faultSeverity.value}%`;
      faultSeverityOut.textContent = `${faultSeverity.value}%`;
    }
  });
  injectFaultButton.addEventListener("click", async () => {
    const config = options.faultConfig?.() || {};
    if (config.vehicle === "space" && config.scenario === "orbital") return;
    injectFaultButton.disabled = true;
    faultStatus.textContent = "INIEZIONE IN CORSO · aggiornamento del modello fisico…";
    try {
      const response = await options.injectFault?.({
        type: faultType.value,
        ...(!["barometer_dropout", "gnss_dropout"].includes(faultType.value) ?
          { severity_fraction: Number(faultSeverity.value) / 100 } : {}),
        ...(faultType.value === "rotor_thrust_loss" ?
          { rotor_index: Number(faultRotorIndex.value) } : {}),
      });
      options.onFaultState?.(response);
      updateFaultManagement(response);
    } catch (error) {
      faultStatus.textContent = `Guasto non applicato: ${error.message}`;
      faultStatus.dataset.mode = "ERROR";
      injectFaultButton.disabled = false;
    }
  });
  clearFaultsButton.addEventListener("click", async () => {
    clearFaultsButton.disabled = true;
    try {
      const response = await options.clearFaults?.();
      options.onFaultState?.(response);
      updateFaultManagement(response);
    } catch (error) {
      faultStatus.textContent = `Ripristino non completato: ${error.message}`;
      clearFaultsButton.disabled = false;
    }
  });
  updateFaultManagement(options.faultConfig?.());

  function render() {
    if (!dialog || !canvas || !dialog.open) return;
    const data = samples();
    const selected = Math.max(0, Math.min(data.length - 1, recorder.selectedIndex || 0));
    recorder.selectedIndex = selected;
    const empty = document.querySelector("#missionPlotEmpty");
    const status = document.querySelector("#recorderStatus");
    const exportJson = document.querySelector("#exportRecorderJson");
    const exportCsv = document.querySelector("#exportRecorderCsv");
    const fullSnapshotCount = data.reduce((count, sample) => count + (sample.state ? 1 : 0), 0);
    empty.hidden = data.length > 0;
    range.max = String(Math.max(0, data.length - 1));
    range.value = String(selected);
    range.disabled = data.length < 2;
    exportJson.disabled = exportCsv.disabled = data.length === 0;
    status.textContent = data.length
      ? `${data.length.toLocaleString("it-IT")} CAMPIONI · ${fullSnapshotCount.toLocaleString("it-IT")} SNAPSHOT COMPLETI · ${recorder.metadata?.vehicle || "MISSIONE ASTRA"}${recorder.storageAvailable === true ? " · SALVATO SUL DISPOSITIVO" : recorder.storageAvailable === false ? " · DATI IN MEMORIA, ARCHIVIAZIONE NON DISPONIBILE" : " · SALVATAGGIO SUL DISPOSITIVO IN CORSO"}`
      : "NESSUN VOLO REGISTRATO";

    const point = data[selected];
    document.querySelector("#recorderTime").textContent = point ? timeLabel(point.time_s) : "T+ 00:00";
    document.querySelector("#recorderPhase").textContent = point?.phase || "—";
    document.querySelector("#recorderAltitude").textContent = point
      ? valueLabel(point.altitude_m, "altitude_m") : "—";
    document.querySelector("#recorderSpeed").textContent = point
      ? valueLabel(point.speed_m_s, "speed_m_s") : "—";
    document.querySelector("#recorderQbar").textContent = point
      ? valueLabel(point.dynamic_pressure_Pa, "dynamic_pressure_Pa") : "—";
    const snapshot = point?.state || point;
    const phaseNode = document.querySelector("#recorderPhase");
    if (phaseNode) {
      const phase = snapshot?.phase || point?.phase || "—";
      phaseNode.textContent = snapshot?.fault
        ? `${phase} · FAULT ${snapshot.fault}` : phase;
      phaseNode.title = snapshot?.mission_started === false
        ? "Snapshot iniziale, missione non ancora avviata"
        : snapshot?.fault || "Stato del veicolo al campione selezionato";
    }
    const attitudeNode = document.querySelector("#recorderAttitude");
    const positionNode = document.querySelector("#recorderPosition");
    const orbitNode = document.querySelector("#recorderOrbit");
    if (attitudeNode) {
      const attitude = snapshot?.attitude_deg || snapshot?.attitude_command_deg;
      const commanded = !snapshot?.attitude_deg && !!snapshot?.attitude_command_deg;
      attitudeNode.textContent = Array.isArray(attitude)
        ? `${attitude.slice(0, 3).map(value => Number.isFinite(value)
          ? `${value.toLocaleString("it-IT", { maximumFractionDigits: 1 })}°` : "—").join(" / ")}${commanded ? " · CMD" : ""}`
        : "NON DISPONIBILE";
      attitudeNode.title = Array.isArray(attitude)
        ? `${commanded ? "Comando" : "Assetto misurato"} R/P/Y [deg]: ${attitude.join(", ")}`
        : "Assetto non restituito dal modello";
    }
    if (positionNode) {
      const position = snapshot?.position_eci_m || snapshot?.position_ned_m;
      const frame = snapshot?.frame || (snapshot?.position_eci_m ? "ECI" :
        snapshot?.position_ned_m ? "NED" : null);
      positionNode.textContent = Array.isArray(position)
        ? `${frame || "POS"} · ${position.slice(0, 3).map(value => Number.isFinite(value)
          ? value.toLocaleString("it-IT", { maximumSignificantDigits: 4 }) : "—").join(", ")} m`
        : "NON DISPONIBILE";
      positionNode.title = Array.isArray(position)
        ? `${frame || "POS"} [m]: ${position.join(", ")}` : "Posizione non restituita";
    }
    const loadFactorNode = document.querySelector("#recorderLoadFactor");
    if (loadFactorNode) {
      loadFactorNode.textContent = Number.isFinite(snapshot?.load_factor_g)
        ? `${snapshot.load_factor_g.toFixed(2)} g` : "NON DISPONIBILE";
      loadFactorNode.title = "Norma della forza specifica divisa per g₀; indicatore cinematico, non tensione strutturale.";
    }
    if (orbitNode) {
      const orbit = snapshot?.orbital_elements;
      const orbitType = orbit?.orbit_type || snapshot?.orbit_type;
      orbitNode.textContent = orbitType
        ? `${orbitType}${orbit?.conic_type ? ` · ${orbit.conic_type}` : ""}`
        : snapshot?.vehicle === "space" ? "NON CLASSIFICATA" : "NON APPLICABILE";
      orbitNode.title = orbitType
        ? `${orbitType}${orbit?.conic_type ? ` · ${orbit.conic_type}` : ""}`
        : snapshot?.vehicle === "space" ? "Stato orbitale non classificato" :
          "Classificazione orbitale non applicabile a questo veicolo";
    }
    const fullState = document.querySelector("#recorderFullState");
    if (fullState) {
      const value = point?.state || point;
      fullState.textContent = value
        ? JSON.stringify(value, null, 2)
        : "Seleziona un campione per ispezionare tutti i dati del veicolo.";
    }

    const rect = canvas.getBoundingClientRect();
    if (rect.width < 4 || rect.height < 4) return;
    const dpr = Math.min(2, globalThis.devicePixelRatio || 1);
    canvas.width = Math.round(rect.width * dpr);
    canvas.height = Math.round(rect.height * dpr);
    const context = canvas.getContext("2d");
    context.setTransform(dpr, 0, 0, dpr, 0, 0);
    context.clearRect(0, 0, rect.width, rect.height);
    context.fillStyle = "#0d1027";
    context.fillRect(0, 0, rect.width, rect.height);
    if (!data.length) return;

    const key = signal.value in SIGNALS ? signal.value : "altitude_m";
    const spec = SIGNALS[key];
    const pad = { left: 56, right: 18, top: 18, bottom: 29 };
    const plotWidth = Math.max(1, rect.width - pad.left - pad.right);
    const plotHeight = Math.max(1, rect.height - pad.top - pad.bottom);
    const values = data.map(item => item[key]).filter(Number.isFinite);
    const high = Math.max(1, ...values);
    const low = 0;
    const scaleHigh = high * 1.08;
    const x = index => pad.left + plotWidth * (data.length < 2 ? 0 : index / (data.length - 1));
    const y = value => pad.top + plotHeight * (1 - (value - low) / (scaleHigh - low));
    context.font = "10px ui-monospace, monospace";
    context.textBaseline = "middle";
    context.strokeStyle = "#8189b52d";
    context.fillStyle = "#b9bcdf";
    context.lineWidth = 1;
    for (let tick = 0; tick <= 4; tick++) {
      const yy = pad.top + plotHeight * tick / 4;
      context.beginPath(); context.moveTo(pad.left, yy); context.lineTo(rect.width - pad.right, yy); context.stroke();
      const value = scaleHigh * (1 - tick / 4);
      context.textAlign = "right";
      context.fillText(value.toLocaleString("it-IT", { maximumFractionDigits: 0 }), pad.left - 8, yy);
    }
    context.textAlign = "left";
    context.textBaseline = "top";
    context.fillStyle = "#8f96bf";
    context.fillText(spec.unit, 8, 5);
    context.textAlign = "left";
    context.fillText(timeLabel(data[0].time_s), pad.left, rect.height - 17);
    context.textAlign = "right";
    context.fillText(timeLabel(data[data.length - 1].time_s), rect.width - pad.right, rect.height - 17);

    context.strokeStyle = "#8c90bd55";
    context.setLineDash([3, 5]);
    for (let i = 1; i < data.length; i++) {
      if (data[i].phase === data[i - 1].phase) continue;
      context.beginPath(); context.moveTo(x(i), pad.top); context.lineTo(x(i), pad.top + plotHeight); context.stroke();
    }
    context.setLineDash([]);

    context.beginPath();
    let started = false;
    data.forEach((item, index) => {
      if (!Number.isFinite(item[key])) return;
      if (!started) { context.moveTo(x(index), y(item[key])); started = true; }
      else context.lineTo(x(index), y(item[key]));
    });
    context.strokeStyle = spec.color;
    context.lineWidth = 2;
    context.lineJoin = "round";
    context.lineCap = "round";
    context.shadowColor = spec.color;
    context.shadowBlur = 9;
    context.stroke();
    context.shadowBlur = 0;

    const selectedValue = data[selected]?.[key];
    const selectedX = x(selected);
    context.strokeStyle = "#e5ddf9b0";
    context.setLineDash([3, 4]);
    context.beginPath(); context.moveTo(selectedX, pad.top); context.lineTo(selectedX, pad.top + plotHeight); context.stroke();
    context.setLineDash([]);
    if (Number.isFinite(selectedValue)) {
      context.beginPath(); context.arc(selectedX, y(selectedValue), 4, 0, Math.PI * 2);
      context.fillStyle = spec.color; context.fill();
    }
  }

  const numberText = (value, digits = 1) => Number.isFinite(value)
    ? value.toLocaleString("it-IT", { maximumFractionDigits: digits }) : "—";
  const percentText = value => `${numberText(value * 100, 1)}%`;
  function renderRobustness(campaign) {
    const stats = document.querySelector("#robustnessStats");
    const table = document.querySelector("#robustnessRuns");
    const success = document.createElement("article");
    success.className = "robustness-stat robustness-stat-success";
    const interval = campaign.completion_fraction_wilson_95 || [0, 1];
    success.innerHTML = `<small>MISSIONI CON ATTERRAGGIO</small><b>${percentText(campaign.completion_fraction)}</b><span>${campaign.samples_completed} prove · intervallo Wilson 95% ${percentText(interval[0])}–${percentText(interval[1])}</span>`;
    const definitions = [
      ["q DINAMICA MASSIMA", "max_dynamic_pressure_Pa", "Pa", 0],
      ["FATTORE DI CARICO MASSIMO", "max_load_factor_g", "g", 2],
      ["FLUSSO TERMICO DI PICCO", "max_stagnation_point_convective_heat_flux_W_m2", "W/m²", 0],
      ["VELOCITÀ DI TOUCHDOWN", "touchdown_speed_m_s", "m/s", 1],
      ["RISORSA RESIDUA", "resource_remaining_pct", "%", 1],
    ];
    const cards = [success];
    for (const [label, key, unit, digits] of definitions) {
      const range = campaign.summary?.[key];
      if (!range) continue;
      const card = document.createElement("article");
      card.className = "robustness-stat";
      const fmt = value => `${numberText(value, digits)} ${unit}`;
      card.innerHTML = `<small>${label}</small><b>${fmt(range.p50)}</b><span>P05 ${fmt(range.p05)} · P95 ${fmt(range.p95)}</span>`;
      cards.push(card);
    }
    stats.replaceChildren(...cards);
    table.replaceChildren(...campaign.runs.map(run => {
      const row = document.createElement("tr");
      const factors = run.perturbations || {};
      const delta = key => `${((factors[key] ?? 1) - 1) >= 0 ? "+" : ""}${numberText(((factors[key] ?? 1) - 1) * 100, 1)}%`;
      const values = [
        String(run.sample).padStart(2, "0"),
        run.phase,
        delta("mass_factor"),
        delta("thrust_factor"),
        delta("drag_factor"),
        numberText(run.max_dynamic_pressure_Pa, 0),
        numberText(run.max_load_factor_g, 2),
        numberText(run.touchdown_speed_m_s, 1),
      ];
      for (const [index, value] of values.entries()) {
        const cell = document.createElement(index === 0 ? "th" : "td");
        cell.textContent = value;
        if (index === 1) cell.className = run.completed ? "robustness-run-success" : "robustness-run-failure";
        row.append(cell);
      }
      return row;
    }));
    robustnessResults.hidden = false;
    document.querySelector("#exportRobustnessJson").disabled = false;
    document.querySelector("#exportRobustnessCsv").disabled = false;
  }

  function renderConvergence(study) {
    const stats = document.querySelector("#convergenceStats");
    const table = document.querySelector("#convergenceRuns");
    const latest = study.adjacent_differences?.at(-1) || {};
    const statusNames = {
      CONVERGED_WITHIN_TOLERANCE: "CONVERGE ENTRO TOLLERANZA",
      REFINEMENT_IMPROVES: "L’AFFINAMENTO RIDUCE L’ERRORE",
      NOT_CONVERGED: "TOLLERANZE NON RAGGIUNTE",
      INCONCLUSIVE_PHASE_CHANGE: "INCONCLUSIVO · FASI DIVERSE",
      TERMINAL_BEFORE_HORIZON: "INCONCLUSIVO · MISSIONE TERMINATA",
      NON_FINITE_STATE: "ERRORE · STATO NON FINITO",
    };
    const status = document.createElement("article");
    status.className = `robustness-stat ${study.status === "CONVERGED_WITHIN_TOLERANCE" ? "robustness-stat-success" : ""}`;
    const title = document.createElement("small");
    title.textContent = "ESITO DEL CONFRONTO";
    const statusValue = document.createElement("b");
    statusValue.textContent = statusNames[study.status] || study.status;
    const statusNote = document.createElement("span");
    statusNote.textContent = `${study.levels} passi · h fino a ${numberText(study.step_sizes_s?.at(-1), 4)} s · GNC ${numberText(1/study.control_update_period_s, 0)} Hz · ${numberText(study.requested_horizon_s, 0)} s simulati`;
    status.append(title, statusValue, statusNote);
    const cards = [status];
    for (const [label, key, unit, digits] of [
      ["POSIZIONE · ULTIMO AFFINAMENTO", "position_m", "m", 3],
      ["VELOCITÀ · ULTIMO AFFINAMENTO", "velocity_m_s", "m/s", 4],
      ["QUOTA · ULTIMO AFFINAMENTO", "altitude_m", "m", 3],
      ["ASSETTO · ULTIMO AFFINAMENTO", "attitude_deg", "°", 3],
      ["RISORSE · ULTIMO AFFINAMENTO", "resource_remaining_pct", "%", 3],
      ["PRESSIONE DINAMICA · Δ RELATIVA", "peak_dynamic_pressure_relative_pct", "%", 4],
      ["TRANSIZIONE FASE · Δ t", "phase_transition_time_s", "s", 3],
      ["ORDINE OSSERVATO POSIZIONE", "position_m", "", 2],
    ]) {
      const card = document.createElement("article");
      card.className = "robustness-stat";
      const heading = document.createElement("small");
      heading.textContent = label;
      const value = document.createElement("b");
      const isOrder = label.startsWith("ORDINE");
      value.textContent = isOrder
        ? (study.observed_order?.[key] == null ? "—" : numberText(study.observed_order[key], digits))
        : (latest[key] == null ? "—" : `${numberText(latest[key], digits)} ${unit}`);
      const note = document.createElement("span");
      note.textContent = isOrder ? "≈ 4 in dinamiche regolari; GNC/eventi possono ridurlo" :
        `tolleranza ${numberText(study.tolerances?.[key], digits)} ${unit}`;
      card.append(heading, value, note);
      cards.push(card);
    }
    stats.replaceChildren(...cards);
    table.replaceChildren(...(study.runs || []).map((run, index) => {
      const row = document.createElement("tr");
      const delta = study.adjacent_differences?.[index];
      const values = [
        numberText(run.step_s, 5),
        run.phase,
        numberText(run.time_s, 2),
        delta ? numberText(delta.position_m, 3) : "riferimento fine",
        delta ? numberText(delta.velocity_m_s, 4) : "—",
        delta ? numberText(delta.altitude_m, 3) : "—",
        delta ? `${numberText(delta.peak_dynamic_pressure_relative_pct, 4)}%` : "—",
      ];
      for (const [cellIndex, value] of values.entries()) {
        const cell = document.createElement(cellIndex === 0 ? "th" : "td");
        cell.textContent = value;
        row.append(cell);
      }
      return row;
    }));
    convergenceResults.hidden = false;
    document.querySelector("#exportConvergenceJson").disabled = false;
    document.querySelector("#exportConvergenceCsv").disabled = false;
  }

  function downloadConvergence(format) {
    if (!convergenceStudy) return;
    let content, mime, extension;
    if (format === "csv") {
      const columns = ["step_s", "phase", "time_s", "frame", "position_m",
        "velocity_m_s", "altitude_m", "attitude_quaternion", "phase_transitions",
        "resource_remaining_pct", "delta_position_m", "delta_velocity_m_s",
        "delta_altitude_m", "delta_attitude_deg", "delta_phase_transition_time_s",
        "delta_resource_remaining_pct", "delta_peak_dynamic_pressure_Pa",
        "delta_peak_dynamic_pressure_relative_pct"];
      const rows = convergenceStudy.runs.map((run, index) => {
        const difference = convergenceStudy.adjacent_differences?.[index] || {};
        const values = {...run, delta_position_m: difference.position_m,
          delta_velocity_m_s: difference.velocity_m_s, delta_altitude_m: difference.altitude_m,
          delta_attitude_deg: difference.attitude_deg,
          delta_phase_transition_time_s: difference.phase_transition_time_s,
          delta_resource_remaining_pct: difference.resource_remaining_pct,
          delta_peak_dynamic_pressure_Pa: difference.peak_dynamic_pressure_Pa,
          delta_peak_dynamic_pressure_relative_pct:
            difference.peak_dynamic_pressure_relative_pct};
        return columns.map(column => csvCell(Array.isArray(values[column])
          ? JSON.stringify(values[column]) : values[column])).join(",");
      });
      content = [columns.join(","), ...rows].join("\r\n");
      mime = "text/csv;charset=utf-8";
      extension = "csv";
    } else {
      content = JSON.stringify(convergenceStudy, null, 2);
      mime = "application/json";
      extension = "json";
    }
    const url = URL.createObjectURL(new Blob([content], { type: mime }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `astra-convergence-${new Date().toISOString().replaceAll(":", "-")}.${extension}`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function downloadRobustness(format) {
    if (!robustnessCampaign) return;
    let content, mime, extension;
    if (format === "csv") {
      const columns = ["sample", "seed", "phase", "completed", "time_s", "altitude_m",
        "speed_m_s", "max_dynamic_pressure_Pa", "max_load_factor_g",
        "max_stagnation_point_convective_heat_flux_W_m2", "touchdown_speed_m_s",
        "resource_remaining_pct", "orbit_type", "perturbations.mass_factor",
        "perturbations.thrust_factor", "perturbations.drag_factor",
        "perturbations.lift_factor", "perturbations.battery_factor",
        "perturbations.wind_north_m_s", "perturbations.wind_east_m_s"];
      const rows = robustnessCampaign.runs.map(run => columns.map(column => {
        const [root, leaf] = column.split(".");
        return csvCell(leaf ? run[root]?.[leaf] : run[root]);
      }).join(","));
      content = [columns.join(","), ...rows].join("\r\n");
      mime = "text/csv;charset=utf-8";
      extension = "csv";
    } else {
      content = JSON.stringify(robustnessCampaign, null, 2);
      mime = "application/json";
      extension = "json";
    }
    const url = URL.createObjectURL(new Blob([content], { type: mime }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `astra-robustness-${new Date().toISOString().replaceAll(":", "-")}.${extension}`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function selectSample(index) {
    recorder.selectedIndex = Math.max(0, Math.min(samples().length - 1, index));
    render();
  }

  recorder.onStorageChange = () => { if (dialog.open) render(); };
  const openRecorder = () => { if (!dialog.open) dialog.showModal(); render(); };
  document.querySelector("#export").addEventListener("click", openRecorder);
  document.querySelector("#missionDataShortcut").addEventListener("click", openRecorder);
  document.querySelector("#closeMissionData").addEventListener("click", close);
  document.querySelector("#exportRecorderJson").addEventListener("click", () => {
    if (!recorder.download("json")) render();
  });
  document.querySelector("#exportRecorderCsv").addEventListener("click", () => {
    if (!recorder.download("csv")) render();
  });
  robustnessButton.addEventListener("click", async () => {
    const seed = Number(document.querySelector("#robustnessSeed").value);
    if (!Number.isSafeInteger(seed) || seed < 0 || seed > 4_294_967_295) {
      robustnessStatus.textContent = "Seed non valido: inserisci un intero da 0 a 4294967295.";
      return;
    }
    const config = options.campaignConfig?.();
    if (!config?.vehicle) {
      robustnessStatus.textContent = "Il motore locale non ha ancora caricato il veicolo selezionato.";
      return;
    }
    const selectedCount = Number(document.querySelector("#robustnessSamples").value);
    const sampleCount = Math.min(selectedCount, config.scenario === "leo-return" ? 4 : 24);
    if (sampleCount !== selectedCount) {
      document.querySelector("#robustnessSamples").value = String(sampleCount);
    }
    robustnessButton.disabled = true;
    document.querySelector("#exportRobustnessJson").disabled = true;
    document.querySelector("#exportRobustnessCsv").disabled = true;
    robustnessStatus.textContent = "CAMPAGNA IN CORSO · ASTRA integra ogni prova in locale; il tempo dipende dal profilo e dal dispositivo.";
    try {
      robustnessCampaign = await options.runCampaign?.({
        ...config,
        samples: sampleCount,
        seed,
      });
      if (!robustnessCampaign?.runs?.length) throw new Error("La campagna non ha restituito prove.");
      const interval = robustnessCampaign.completion_fraction_wilson_95;
      robustnessStatus.textContent = `${robustnessCampaign.samples_completed} PROVE COMPLETATE · ${robustnessCampaign.integrator} · SEED ${robustnessCampaign.seed} · intervallo al 95% ${percentText(interval[0])}–${percentText(interval[1])}.`;
      renderRobustness(robustnessCampaign);
    } catch (error) {
      robustnessStatus.textContent = `Campagna non completata: ${error.message}`;
    } finally {
      robustnessButton.disabled = false;
      document.querySelector("#exportRobustnessJson").disabled = !robustnessCampaign;
      document.querySelector("#exportRobustnessCsv").disabled = !robustnessCampaign;
    }
  });
  document.querySelector("#exportRobustnessJson").addEventListener("click", () => downloadRobustness("json"));
  document.querySelector("#exportRobustnessCsv").addEventListener("click", () => downloadRobustness("csv"));
  convergenceButton.addEventListener("click", async () => {
    const config = options.campaignConfig?.();
    const horizon = Number(document.querySelector("#convergenceHorizon").value);
    const levels = Number(document.querySelector("#convergenceLevels").value);
    const tolerances = {
      position_m: Number(document.querySelector("#tolerancePosition").value),
      velocity_m_s: Number(document.querySelector("#toleranceVelocity").value),
      altitude_m: Number(document.querySelector("#toleranceAltitude").value),
      attitude_deg: Number(document.querySelector("#toleranceAttitude").value),
      resource_remaining_pct: Number(document.querySelector("#toleranceResource").value),
      phase_transition_time_s: Number(document.querySelector("#tolerancePhase").value),
      peak_dynamic_pressure_relative_pct:
        Number(document.querySelector("#toleranceDynamicPressure").value),
    };
    if (!config?.vehicle) {
      convergenceStatus.textContent = "Il motore locale non ha ancora caricato il veicolo selezionato.";
      convergenceStatus.dataset.result = "warn";
      return;
    }
    if (!Number.isFinite(horizon) || horizon < 1 || horizon > 600) {
      convergenceStatus.textContent = "Inserisci un orizzonte tra 1 e 600 secondi.";
      convergenceStatus.dataset.result = "warn";
      return;
    }
    if (Object.values(tolerances).some(value => !Number.isFinite(value) || value <= 0)) {
      convergenceStatus.textContent = "Ogni soglia deve essere un numero positivo e finito.";
      convergenceStatus.dataset.result = "warn";
      return;
    }
    convergenceButton.disabled = true;
    document.querySelector("#exportConvergenceJson").disabled = true;
    document.querySelector("#exportConvergenceCsv").disabled = true;
    convergenceStatus.textContent = "CONFRONTO IN CORSO · ASTRA ripete il profilo a passi dimezzati su motori isolati.";
    convergenceStatus.dataset.result = "";
    try {
      convergenceStudy = await options.runConvergence?.({
        ...config,
        horizon_s: horizon,
        levels,
        tolerances,
      });
      if (!convergenceStudy?.runs?.length) throw new Error("Lo studio non ha restituito integrazioni.");
      const latest = convergenceStudy.adjacent_differences?.at(-1) || {};
      const statusText = {
        CONVERGED_WITHIN_TOLERANCE: "CONVERGE ENTRO LE TOLLERANZE DICHIARATE",
        REFINEMENT_IMPROVES: "L’AFFINAMENTO RIDUCE L’ERRORE; LE TOLLERANZE NON SONO ANCORA RAGGIUNTE",
        NOT_CONVERGED: "IL CONFRONTO NON È CONVERGENTE A QUESTI PASSI",
        INCONCLUSIVE_PHASE_CHANGE: "INCONCLUSIVO · LE INTEGRAZIONI TERMINANO IN FASI DIVERSE",
        TERMINAL_BEFORE_HORIZON: "INCONCLUSIVO · UNA O PIÙ MISSIONI TERMINANO PRIMA DELL’ORIZZONTE",
        NON_FINITE_STATE: "ERRORE NUMERICO · È STATO RILEVATO UNO STATO NON FINITO",
      };
      convergenceStatus.textContent = `${statusText[convergenceStudy.status] || convergenceStudy.status} · Δ r finale ${numberText(latest.position_m, 3)} m · Δv ${numberText(latest.velocity_m_s, 4)} m/s · Δq max ${numberText(latest.peak_dynamic_pressure_relative_pct, 4)}%.`;
      convergenceStatus.dataset.result = convergenceStudy.status === "CONVERGED_WITHIN_TOLERANCE"
        ? "good" : ["REFINEMENT_IMPROVES", "INCONCLUSIVE_PHASE_CHANGE", "TERMINAL_BEFORE_HORIZON"].includes(convergenceStudy.status)
          ? "warn" : "bad";
      renderConvergence(convergenceStudy);
    } catch (error) {
      convergenceStudy = null;
      convergenceStatus.textContent = `Studio non completato: ${error.message}`;
      convergenceStatus.dataset.result = "bad";
    } finally {
      convergenceButton.disabled = false;
      document.querySelector("#exportConvergenceJson").disabled = !convergenceStudy;
      document.querySelector("#exportConvergenceCsv").disabled = !convergenceStudy;
    }
  });
  document.querySelector("#exportConvergenceJson").addEventListener("click", () => downloadConvergence("json"));
  document.querySelector("#exportConvergenceCsv").addEventListener("click", () => downloadConvergence("csv"));
  range.addEventListener("input", () => selectSample(Number(range.value)));
  signal.addEventListener("change", render);
  canvas.addEventListener("pointerdown", event => {
    if (samples().length < 2) return;
    const rect = canvas.getBoundingClientRect();
    const left = 56;
    const right = rect.width - 18;
    const fraction = Math.max(0, Math.min(1, (event.clientX - rect.left - left) / Math.max(1, right - left)));
    selectSample(Math.round(fraction * (samples().length - 1)));
  });
  window.addEventListener("resize", () => { if (dialog.open) render(); });
  dialog.addEventListener("close", () => document.querySelector("#export").blur());
  recorder.ready?.then(() => { if (dialog.open) render(); });
  render();
  return { render, updateFaultManagement };
}
