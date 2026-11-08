// The Maestro card: the time of day now, the day as a timeline, pinning and adjusting a day.

const shared = await import(new URL(`./maestro-shared.js${new URL(import.meta.url).search}`, import.meta.url).href);
const {
  TIMELINE_STYLE,
  addDays,
  clockOf,
  esc,
  fmtDate,
  fmtDuration,
  fmtTime,
  icon,
  inkOn,
  isDark,
  localParts,
  minutesOf,
  timelineHTML,
  tr,
} = shared;

const STYLE = `
:host { display: block; }
.card { padding: 16px; display: grid; gap: 12px; color: var(--mae-ink); container-type: inline-size;
  --mae-ink: var(--primary-text-color, #171d2d); --mae-muted: var(--secondary-text-color, #566077); --mae-surface: var(--ha-card-background, var(--card-background-color, #fff));
  --mae-line: var(--divider-color, #d4dae6); --mae-accent: var(--primary-color, #2f5fd0); --mae-accent-ink: var(--text-primary-color, #fff);
  --mae-accent-soft: color-mix(in srgb, var(--mae-accent) 16%, transparent); --mae-well: color-mix(in srgb, var(--mae-ink) 9%, var(--mae-surface));
  --mae-warn: #8a5300; --mae-warn-soft: #fbeed6; }
:host([dark]) .card { --mae-warn: #f0bd6a; --mae-warn-soft: #3a2b12; }
* { box-sizing: border-box; }
[hidden] { display: none !important; }
button, input, select { font: inherit; color: inherit; }
button { cursor: pointer; }
:focus-visible { outline: 2px solid var(--mae-accent); outline-offset: 2px; }
.head { display: flex; gap: 12px; align-items: center; min-width: 0; }
.badge { flex: none; width: 48px; height: 48px; border-radius: 14px; display: grid; place-items: center; }
.badge.small { width: 38px; height: 38px; border-radius: 11px; }
.what { min-width: 0; display: grid; gap: 1px; flex: 1; }
.rhythm { font-size: 13px; color: var(--mae-muted); display: flex; flex-wrap: wrap; gap: 4px 8px; align-items: center; }
.name { font-size: 21px; font-weight: 650; line-height: 1.2; overflow-wrap: anywhere; }
.small .name, .compact .name { font-size: 17px; }
.when { font-size: 13.5px; color: var(--mae-muted); font-variant-numeric: tabular-nums; }
.chip { display: inline-flex; align-items: center; gap: 3px; padding: 1px 8px; border-radius: 99px; font-size: 12px; font-weight: 600; background: var(--mae-accent-soft); color: var(--mae-ink); }
.rowlabel { font-size: 12.5px; color: var(--mae-muted); margin-bottom: 4px; }
.actions { display: flex; flex-wrap: wrap; gap: 8px; }
.btn { border: 1px solid var(--mae-line); background: transparent; border-radius: 10px; min-height: 36px; padding: 5px 12px; font-weight: 550; font-size: 14px; display: inline-flex; gap: 6px; align-items: center; }
.btn:hover { border-color: var(--mae-accent); }
.btn.primary { background: var(--mae-accent); border-color: var(--mae-accent); color: var(--mae-accent-ink); }
.btn.on { background: var(--mae-accent-soft); border-color: var(--mae-accent); }
.btn:disabled { opacity: .5; cursor: not-allowed; }
.sheet { border-top: 1px solid var(--mae-line); padding-top: 12px; display: grid; gap: 12px; }
.sheet h3 { margin: 0; font-size: 15px; font-weight: 650; display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.x { border: 0; background: transparent; color: var(--mae-muted); width: 30px; height: 30px; border-radius: 8px; font-size: 18px; line-height: 1; }
.x:hover { background: var(--mae-well); color: var(--mae-ink); }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.tod { border: 2px solid transparent; border-radius: 10px; min-height: 36px; padding: 4px 10px 4px 6px; display: inline-flex; gap: 6px; align-items: center; font-weight: 600; font-size: 13.5px; }
.tod[aria-pressed="true"] { border-color: var(--mae-ink); box-shadow: 0 0 0 2px var(--mae-surface) inset; }
.tod .now { font-size: 11px; font-weight: 500; opacity: .85; }
.ends { display: grid; gap: 4px; }
.end { display: flex; flex-wrap: wrap; gap: 6px 10px; align-items: center; padding: 6px 8px; border-radius: 8px; font-size: 14px; }
.end:has(input[type="radio"]:checked) { background: var(--mae-accent-soft); }
.end input[type="radio"] { accent-color: var(--mae-accent); margin: 0; }
.field { background: var(--mae-surface); border: 1px solid var(--mae-line); border-radius: 8px; min-height: 34px; padding: 4px 8px; }
input.num { width: 72px; }
.info { font-size: 13.5px; color: var(--mae-muted); }
.warn { padding: 8px 10px; border-radius: 9px; background: var(--mae-warn-soft); color: var(--mae-warn); font-size: 13.5px; }
.error { padding: 8px 10px; border-radius: 9px; background: var(--mae-warn-soft); color: var(--mae-warn); font-size: 13.5px; }
.shift { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.compact { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.compact .what { flex: 1 1 140px; }
.daytabs { display: inline-flex; gap: 2px; padding: 3px; background: var(--mae-well); border-radius: 10px; }
.daytabs button { border: 0; background: transparent; padding: 4px 12px; border-radius: 8px; font-size: 13.5px; color: var(--mae-muted); }
.daytabs button[aria-pressed="true"] { background: var(--mae-surface); color: var(--mae-ink); font-weight: 600; }
${TIMELINE_STYLE}
`;

const DEFAULTS = { variant: "full", tomorrow: false };
const PRESETS = [60, 120, 240];

class MaestroCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement("maestro-card-editor");
  }

  static getStubConfig(hass) {
    const id = Object.keys(hass?.states || {}).find((e) => e.startsWith("sensor.") && hass.states[e].attributes?.rhythm);
    return { entity: id || "", variant: "full" };
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._sheet = null;
    this._pin = { key: null, mode: null, hours: 3, time: "" };
    this._tick = null;
    this._dayTab = 0;
    this.shadowRoot.addEventListener("click", (e) => this._onClick(e));
    this.shadowRoot.addEventListener("change", (e) => this._onChange(e));
    this.shadowRoot.addEventListener("input", (e) => this._onInput(e));
  }

  setConfig(config) {
    if (!config || !config.entity) throw new Error("Please choose a Maestro rhythm");
    const changed = config.entity !== this._config?.entity;
    this._config = { ...DEFAULTS, ...config };
    if (changed) {
      this._unsubscribe();
      this._snap = null;
      this._subscribe();
    }
    this._render();
  }

  getCardSize() {
    return this._config?.variant === "compact" ? 2 : this._config?.tomorrow ? 6 : 5;
  }

  getGridOptions() {
    return this._config?.variant === "compact"
      ? { columns: 6, min_columns: 4, rows: "auto" }
      : { columns: 12, min_columns: 6, rows: "auto" };
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._subscribe();
    const dark = isDark(this.shadowRoot.querySelector(".card"), hass);
    if (dark !== this._dark) {
      this._dark = dark;
      this.toggleAttribute("dark", dark);
    }
  }

  connectedCallback() {
    this._subscribe();
    this._timer = setInterval(() => {
      if (!this._sheet) this._render();
    }, 30000);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
    this._unsubscribe();
  }

  get _t() {
    return tr(this._hass);
  }

  async _subscribe() {
    if (this._unsub || this._subscribing || !this._hass || !this._config?.entity || !this.isConnected) return;
    this._subscribing = true;
    try {
      this._unsub = await this._hass.connection.subscribeMessage(
        (snap) => {
          this._snap = snap;
          this._error = null;
          this._render();
        },
        { type: "cloudless_maestro/subscribe", entity_id: this._config.entity },
      );
    } catch (err) {
      this._error = err?.message || String(err);
      this._render();
    } finally {
      this._subscribing = false;
    }
  }

  _unsubscribe() {
    const unsub = this._unsub;
    this._unsub = null;
    if (unsub) Promise.resolve(unsub()).catch(() => {});
  }

  async _ws(msg) {
    try {
      await this._hass.callWS({ entity_id: this._config.entity, ...msg });
      this._error = null;
      return true;
    } catch (err) {
      this._error = err?.message || String(err);
      this._render();
      return false;
    }
  }

  // -- looking things up ------------------------------------------------------------------------------

  _look(key) {
    const s = this._snap;
    if (!s) return null;
    if (key === s.base.key) return s.base;
    return s.times_of_day.find((t) => t.key === key) || { key, name: key, color: "#7a8599" };
  }

  _modelName(key) {
    return this._snap?.models.find((m) => m.key === key)?.name || key || "—";
  }

  // Where a segment begins: a time of day of one of the shown days, or the end of a day.
  _boundaryOf(seg) {
    const s = this._snap;
    const nowMs = new Date(s.now).getTime();
    const future = new Date(seg.start).getTime() > nowMs;
    if (seg.day) {
      const day = s.days.find((d) => d.day === seg.day);
      if (!day || !day.entries.some((e) => e.key === seg.key && e.start === seg.start)) return null;
      return {
        id: `${seg.day}|${seg.key}`,
        clickable: future,
        adjusted: !!day.adjustment?.times?.[seg.key],
      };
    }
    const day = s.days.find((d) => d.window && d.window.end === seg.start);
    if (!day) return null;
    return { id: `${day.day}|`, clickable: future, adjusted: !!day.adjustment?.end };
  }

  _range(day) {
    const s = this._snap;
    const now = new Date(s.now).getTime();
    let start, end;
    if (day?.window) {
      start = new Date(day.window.start).getTime() - 45 * 60000;
      end = new Date(day.window.end).getTime() + 45 * 60000;
    } else {
      start = now - 6 * 3600000;
      end = now + 6 * 3600000;
    }
    if (day === s.days[0]) {
      start = Math.min(start, now - 30 * 60000);
      end = Math.max(end, now + 30 * 60000);
    }
    return [new Date(start).toISOString(), new Date(end).toISOString()];
  }

  // -- rendering --------------------------------------------------------------------------------------

  _render() {
    if (!this._config) return;
    const t = this._t;
    const s = this._snap;
    if (!s) {
      const msg = this._error
        ? `<div class="error">${esc(t("Not available", "Nicht verfügbar"))}: ${esc(this._error)}</div>`
        : `<div class="info">${esc(t("Loading …", "Wird geladen …"))}</div>`;
      this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card class="card">${msg}</ha-card>`;
      return;
    }
    const st = s.state;
    const item = this._look(st.key);
    const color = item.color || "#7a8599";
    const today = s.days[0];
    const adjusted = !!today.adjustment;
    const chips = `${st.pinned ? `<span class="chip">${icon("mdi:pin", 13)}${esc(t("Pinned", "Festgesetzt"))}</span>` : ""}${adjusted ? `<span class="chip">${icon("mdi:calendar-edit", 13)}${esc(t("Today adjusted", "Heute angepasst"))}</span>` : ""}`;
    const when = this._whenText();
    const error = this._error ? `<div class="error">${esc(this._error)}</div>` : "";
    if (this._config.variant === "compact") {
      this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card class="card">
        <div class="compact">
          <div class="badge small" style="background:${esc(color)};color:${inkOn(color)}">${icon(item.icon, 22)}</div>
          <div class="what"><div class="rhythm">${esc(s.title)} ${chips}</div><div class="name">${esc(item.name)}</div><div class="when">${esc(when)}</div></div>
          <div class="actions">${st.pinned ? `<button class="btn" data-act="resume">${icon("mdi:calendar-sync", 18)}${esc(t("Back to plan", "Zurück zum Plan"))}</button>` : ""}
            <button class="btn${this._sheet === "pin" ? " on" : ""}" data-act="open" data-sheet="pin">${icon("mdi:pin-outline", 18)}${esc(st.pinned ? t("Change", "Ändern") : t("Pin", "Festsetzen"))}</button></div>
        </div>${error}${this._sheet === "pin" ? this._pinSheet() : ""}</ha-card>`;
      return;
    }
    const tomorrow = s.days[1];
    const line = (day, label) => {
      const [start, end] = this._range(day);
      return `<div><div class="rowlabel">${esc(label)} · ${esc(this._modelName(day.model))}${day.adjustment ? ` · ${esc(t("adjusted", "angepasst"))}` : ""}</div>${timelineHTML({
        hass: this._hass,
        segments: s.segments,
        start,
        end,
        now: s.now,
        look: (k) => this._look(k),
        boundary: (seg) => this._boundaryOf(seg),
        selected: this._tick,
        base: s.base.key,
      })}</div>`;
    };
    const sheet = this._sheet === "pin" ? this._pinSheet() : this._sheet === "shift" ? this._shiftSheet() : this._sheet === "day" ? this._daySheet() : "";
    this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card class="card">
      <div class="head">
        <div class="badge" style="background:${esc(color)};color:${inkOn(color)}">${icon(item.icon, 26)}</div>
        <div class="what"><div class="rhythm">${esc(s.title)} ${chips}</div><div class="name">${esc(item.name)}</div><div class="when">${esc(when)}</div></div>
      </div>
      ${line(today, this._dayLabel(today.day))}
      ${this._config.tomorrow ? line(tomorrow, this._dayLabel(tomorrow.day)) : ""}
      <div class="actions">
        <button class="btn${this._sheet === "pin" ? " on" : ""}" data-act="open" data-sheet="pin">${icon("mdi:pin-outline", 18)}${esc(t("Choose time of day", "Tageszeit wählen"))}</button>
        <button class="btn${this._sheet === "day" ? " on" : ""}" data-act="open" data-sheet="day">${icon("mdi:calendar-edit", 18)}${esc(t("Adjust day", "Tag anpassen"))}</button>
        ${st.pinned ? `<button class="btn" data-act="resume">${icon("mdi:calendar-sync", 18)}${esc(t("Back to plan", "Zurück zum Plan"))}</button>` : ""}
      </div>
      ${error}${sheet}
    </ha-card>`;
  }

  _dayLabel(day) {
    const t = this._t;
    const today = this._snap.state.today;
    const name = day === today ? t("Today", "Heute") : day === addDays(today, 1) ? t("Tomorrow", "Morgen") : "";
    return `${name ? `${name}, ` : ""}${fmtDate(this._hass, day)}`;
  }

  _whenText() {
    const t = this._t;
    const st = this._snap.state;
    const since = `${t("since", "seit")} ${fmtTime(this._hass, st.since)}`;
    if (!st.until) return `${since} · ${t("until reset", "bis zurückgesetzt")}`;
    const next = this._look(st.next_key);
    return `${since} · ${t("then", "dann")} ${next?.name || ""} ${t("at", "um")} ${fmtTime(this._hass, st.until)}`;
  }

  // -- pin --------------------------------------------------------------------------------------------

  _pinSheet() {
    const t = this._t;
    const s = this._snap;
    const p = this._pin;
    const key = p.key ?? s.state.key;
    const holding = key === s.state.key && !s.state.pinned;
    const mode = p.mode ?? (holding ? "preset:120" : "next_change");
    const chips = s.choosable
      .map((k) => {
        const it = this._look(k);
        const c = it.color || "#7a8599";
        return `<button class="tod" style="background:${esc(c)};color:${inkOn(c)}" data-act="pin-key" data-key="${esc(k)}" aria-pressed="${k === key}">${icon(it.icon, 18)}${esc(it.name)}${k === s.state.key ? `<span class="now">· ${esc(t("now", "jetzt"))}</span>` : ""}</button>`;
      })
      .join("");
    const radio = (value, label, extra = "") =>
      `<label class="end"><input type="radio" name="end" value="${esc(value)}"${mode === value ? " checked" : ""}> ${esc(label)}${extra}</label>`;
    const options = [
      holding ? "" : radio("next_change", t("Until the next change", "Bis zum nächsten Wechsel")),
      ...PRESETS.map((m) => radio(`preset:${m}`, `${t("For", "Für")} ${fmtDuration(this._hass, m)}`)),
      radio(
        "duration",
        t("For", "Für"),
        ` <input class="field num" type="number" min="0.25" max="48" step="0.25" id="hours" value="${esc(p.hours)}" aria-label="${esc(t("Hours", "Stunden"))}"> ${esc(t("hours", "Stunden"))}`,
      ),
      radio(
        "time",
        t("Until", "Bis"),
        ` <input class="field" type="time" id="untilTime" value="${esc(p.time || this._suggestTime())}" aria-label="${esc(t("Time", "Uhrzeit"))}">`,
      ),
      radio("next_day", t("Until the next day", "Bis zum nächsten Tag")),
      radio("reset", t("Until reset", "Bis zurückgesetzt")),
    ].join("");
    const info = this._pinInfo(key, mode);
    const label = mode === "reset" ? t("Pin anyway", "Trotzdem festsetzen") : t("Pin", "Festsetzen");
    return `<div class="sheet"><h3>${esc(holding ? t("Hold the time of day", "Tageszeit halten") : t("Pin a time of day", "Tageszeit festsetzen"))}<button class="x" data-act="close" aria-label="${esc(t("Close", "Schließen"))}">×</button></h3>
      <div class="chips">${chips}</div>
      <div class="ends" role="radiogroup">${options}</div>
      ${info}
      <div class="actions"><button class="btn primary" data-act="pin">${icon("mdi:pin", 18)}${esc(label)}</button></div></div>`;
  }

  _suggestTime() {
    const now = localParts(this._hass, this._snap.now).time;
    return clockOf(Math.ceil((minutesOf(now) + 60) / 30) * 30);
  }

  // When the plan reaches a later time of day today, or the day ends.
  _nextChangeEnd(key) {
    const s = this._snap;
    const today = s.days[0];
    const now = new Date(s.now).getTime();
    if (key === s.base.key) {
      const coming = s.days.find((d) => d.window && new Date(d.window.start).getTime() > now);
      return coming ? coming.window.start : null;
    }
    const rank = today.order.indexOf(key);
    const later = today.entries.find((e) => today.order.indexOf(e.key) > rank && new Date(e.start).getTime() > now);
    if (later && (!today.window || new Date(later.start) < new Date(today.window.end))) return later.start;
    return today.window?.end || null;
  }

  _pinInfo(key, mode) {
    const t = this._t;
    const s = this._snap;
    const nextDay = s.next_day_start;
    const firstTomorrow = nextDay ? this._look(s.segments.find((x) => x.start === nextDay)?.key)?.name : null;
    const at = (iso) => fmtTime(this._hass, iso);
    if (mode === "reset") {
      const what = nextDay
        ? `${firstTomorrow || t("The next day", "Der nächste Tag")} ${this._relativeDay(nextDay)} ${t("at", "um")} ${at(nextDay)} ${t("will not start", "entfällt")}`
        : t("The plan stops", "Der Plan pausiert");
      return `<div class="warn">${icon("mdi:alarm-off", 16)} ${esc(what)}, ${esc(t("until you return to the plan.", "bis du zum Plan zurückkehrst."))}</div>`;
    }
    if (mode === "next_change") {
      const end = this._nextChangeEnd(key);
      return end ? `<div class="info">${esc(t("Ends at", "Endet um"))} ${esc(at(end))}.</div>` : "";
    }
    if (mode === "next_day") {
      return nextDay
        ? `<div class="info">${esc(t("Ends at", "Endet um"))} ${esc(at(nextDay))}${firstTomorrow ? ` ${esc(t("with", "mit"))} ${esc(firstTomorrow)}` : ""}.</div>`
        : "";
    }
    const end = this._pinUntil(mode);
    if (!end) return "";
    if (nextDay && end.getTime() > new Date(nextDay).getTime()) {
      return `<div class="info">${esc(t("Ends at", "Endet um"))} ${esc(at(nextDay))} ${esc(t("at the latest, when the next day begins", "spätestens, wenn der nächste Tag beginnt"))}${firstTomorrow ? ` (${esc(firstTomorrow)})` : ""}.</div>`;
    }
    return `<div class="info">${esc(t("Ends at", "Endet um"))} ${esc(at(end.toISOString()))}.</div>`;
  }

  // "tomorrow" or a weekday, seen from the current date.
  _relativeDay(iso) {
    const t = this._t;
    const now = localParts(this._hass, this._snap.now).date;
    const day = localParts(this._hass, iso).date;
    if (day === now) return t("today", "heute");
    if (day === addDays(now, 1)) return t("tomorrow", "morgen");
    return fmtDate(this._hass, day, { weekday: "long" });
  }

  _pinUntil(mode) {
    const now = new Date(this._snap.now);
    if (mode.startsWith("preset:")) return new Date(now.getTime() + Number(mode.slice(7)) * 60000);
    if (mode === "duration") return new Date(now.getTime() + Math.max(0.25, Number(this._pin.hours) || 0) * 3600000);
    if (mode === "time") {
      const clock = this._pin.time || this._suggestTime();
      const parts = localParts(this._hass, this._snap.now);
      let diff = minutesOf(clock) - minutesOf(parts.time);
      if (diff <= 0) diff += 1440;
      return new Date(now.getTime() + diff * 60000);
    }
    return null;
  }

  async _doPin() {
    const s = this._snap;
    const key = this._pin.key ?? s.state.key;
    const holding = key === s.state.key && !s.state.pinned;
    const mode = this._pin.mode ?? (holding ? "preset:120" : "next_change");
    const msg = { type: "cloudless_maestro/pin", time_of_day: key };
    if (mode.startsWith("preset:")) Object.assign(msg, { until: "duration", minutes: Number(mode.slice(7)) });
    else if (mode === "duration") Object.assign(msg, { until: "duration", minutes: Math.round(Math.max(0.25, Number(this._pin.hours) || 0) * 60) });
    else if (mode === "time") Object.assign(msg, { until: "time", time: `${this._pin.time || this._suggestTime()}:00` });
    else msg.until = mode;
    if (await this._ws(msg)) {
      this._sheet = null;
      this._pin = { key: null, mode: null, hours: 3, time: "" };
      this._render();
    }
  }

  // -- shift one change -------------------------------------------------------------------------------

  _shiftTarget() {
    if (!this._tick) return null;
    const [day, key] = this._tick.split("|");
    const d = this._snap.days.find((x) => x.day === day);
    if (!d) return null;
    const iso = key ? d.entries.find((e) => e.key === key)?.start : d.end;
    return iso ? { day: d, key, iso } : null;
  }

  _shiftSheet() {
    const t = this._t;
    const target = this._shiftTarget();
    if (!target) return "";
    const s = this._snap;
    const name = target.key ? this._look(target.key).name : `${s.base.name} ${t("from", "ab")}`;
    const clock = this._shiftClock ?? localParts(this._hass, target.iso).time;
    const adjusted = target.key ? !!target.day.adjustment?.times?.[target.key] : !!target.day.adjustment?.end;
    return `<div class="sheet"><h3>${esc(name)} · ${esc(this._dayLabel(target.day.day))}<button class="x" data-act="close" aria-label="${esc(t("Close", "Schließen"))}">×</button></h3>
      <div class="shift"><button class="btn" data-act="shift-by" data-min="-15">−15</button>
        <input class="field" type="time" id="shiftTime" value="${esc(clock)}" aria-label="${esc(t("New time", "Neue Uhrzeit"))}">
        <button class="btn" data-act="shift-by" data-min="15">+15</button></div>
      <div class="info">${esc(t("Only on this date. The day model stays as it is.", "Nur an diesem Datum. Das Tagesmodell bleibt, wie es ist."))}</div>
      <div class="actions"><button class="btn primary" data-act="shift-save">${esc(t("Save", "Übernehmen"))}</button>
        ${adjusted ? `<button class="btn" data-act="shift-reset">${esc(t("Back to the model", "Zurück zum Modell"))}</button>` : ""}</div></div>`;
  }

  // A time earlier than the day's first start belongs to the following day, as does a first start already there.
  _withDay(day, key, clock) {
    const first = day.entries[0];
    if (!first) return clock;
    const firstLocal = localParts(this._hass, first.start);
    const firstNextDay = firstLocal.date > day.day;
    if (key === first.key) return firstNextDay ? `${clock}+1` : clock;
    const start = minutesOf(firstLocal.time);
    const before = key ? minutesOf(clock) < start : minutesOf(clock) <= start;
    return before || firstNextDay ? `${clock}+1` : clock;
  }

  async _saveShift() {
    const target = this._shiftTarget();
    if (!target) return;
    const clock = this.shadowRoot.getElementById("shiftTime")?.value;
    if (!clock) return;
    const value = this._withDay(target.day, target.key, clock);
    const msg = { type: "cloudless_maestro/adjust", day: target.day.day };
    if (target.key) msg.times = { [target.key]: value };
    else msg.end = value;
    if (await this._ws(msg)) this._closeSheet();
  }

  async _resetShift() {
    const target = this._shiftTarget();
    if (!target) return;
    const msg = { type: "cloudless_maestro/adjust", day: target.day.day };
    if (target.key) msg.clear_times = [target.key];
    else msg.clear_end = true;
    if (await this._ws(msg)) this._closeSheet();
  }

  // -- the whole day ----------------------------------------------------------------------------------

  _daySheet() {
    const t = this._t;
    const s = this._snap;
    const day = s.days[this._dayTab] || s.days[0];
    const options = s.models
      .map((m) => `<option value="${esc(m.key)}"${m.key === day.model ? " selected" : ""}>${esc(m.name)}</option>`)
      .join("");
    const source =
      day.source === "calendar"
        ? `${t("From the calendar", "Aus dem Kalender")}${day.detail ? `: ${day.detail}` : ""}`
        : day.source === "adjustment"
          ? t("Chosen for this date", "Für dieses Datum gewählt")
          : t("From the week plan", "Aus dem Wochenplan");
    const dropped = day.dropped.length
      ? `<div class="info">${esc(t("Does not happen on this date:", "Fällt an diesem Datum aus:"))} ${esc(day.dropped.map((k) => this._look(k).name).join(", "))}</div>`
      : "";
    return `<div class="sheet"><h3><span class="daytabs" role="group">
        <button data-act="day-tab" data-i="0" aria-pressed="${this._dayTab === 0}">${esc(t("Today", "Heute"))}</button>
        <button data-act="day-tab" data-i="1" aria-pressed="${this._dayTab === 1}">${esc(t("Tomorrow", "Morgen"))}</button></span>
        <button class="x" data-act="close" aria-label="${esc(t("Close", "Schließen"))}">×</button></h3>
      <label class="shift">${esc(t("Day model", "Tagesmodell"))} <select class="field" id="dayModel">${options}</select></label>
      <div class="info">${esc(source)}. ${esc(t("Tap a time in the timeline to move a single change.", "Tippe in der Zeitleiste auf eine Uhrzeit, um einen einzelnen Wechsel zu verschieben."))}</div>
      ${dropped}
      ${day.adjustment ? `<div class="actions"><button class="btn" data-act="day-clear">${icon("mdi:calendar-remove", 18)}${esc(t("Remove the adjustment", "Anpassung entfernen"))}</button></div>` : ""}</div>`;
  }

  // -- events -----------------------------------------------------------------------------------------

  _closeSheet() {
    this._sheet = null;
    this._tick = null;
    this._shiftClock = null;
    this._render();
  }

  _onClick(e) {
    const el = e.target.closest("[data-act]");
    if (!el) return;
    const act = el.dataset.act;
    if (act === "open") {
      const next = el.dataset.sheet;
      this._tick = null;
      this._sheet = this._sheet === next ? null : next;
      this._render();
    } else if (act === "close") this._closeSheet();
    else if (act === "resume") this._ws({ type: "cloudless_maestro/resume" });
    else if (act === "pin-key") {
      this._pin.key = el.dataset.key;
      this._pin.mode = null;
      this._render();
    } else if (act === "pin") this._doPin();
    else if (act === "tick") {
      this._tick = this._tick === el.dataset.id ? null : el.dataset.id;
      this._shiftClock = null;
      this._sheet = this._tick ? "shift" : null;
      this._render();
    } else if (act === "shift-by") {
      const input = this.shadowRoot.getElementById("shiftTime");
      this._shiftClock = clockOf(minutesOf(input.value || "00:00") + Number(el.dataset.min));
      input.value = this._shiftClock;
    } else if (act === "shift-save") this._saveShift();
    else if (act === "shift-reset") this._resetShift();
    else if (act === "day-tab") {
      this._dayTab = Number(el.dataset.i);
      this._render();
    } else if (act === "day-clear") this._ws({ type: "cloudless_maestro/clear_day", day: this._snap.days[this._dayTab].day });
  }

  _onChange(e) {
    const el = e.target;
    if (el.name === "end") {
      this._pin.mode = el.value;
      this._render();
    } else if (el.id === "dayModel") {
      const day = this._snap.days[this._dayTab];
      this._ws({ type: "cloudless_maestro/adjust", day: day.day, model: el.value });
    } else if (el.id === "shiftTime") this._shiftClock = el.value;
  }

  _onInput(e) {
    const el = e.target;
    if (el.id === "hours") {
      this._pin.hours = el.value;
      this._pin.mode = "duration";
      this._refreshPinInfo();
    } else if (el.id === "untilTime") {
      this._pin.time = el.value;
      this._pin.mode = "time";
      this._refreshPinInfo();
    }
  }

  // Typing must not lose focus, so only the info line and the chosen end change.
  _refreshPinInfo() {
    const radios = this.shadowRoot.querySelectorAll('input[name="end"]');
    radios.forEach((r) => (r.checked = r.value === this._pin.mode));
    const info = this.shadowRoot.querySelector(".sheet .info, .sheet .warn");
    const s = this._snap;
    const html = this._pinInfo(this._pin.key ?? s.state.key, this._pin.mode);
    if (info) info.outerHTML = html || "<div class=\"info\"></div>";
  }
}

// -- the card editor ----------------------------------------------------------------------------------

class MaestroCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.shadowRoot.addEventListener("change", (e) => this._onChange(e));
  }

  setConfig(config) {
    this._config = { ...DEFAULTS, ...config };
    this._render();
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._render();
  }

  _render() {
    if (!this._config || !this._hass) return;
    const t = tr(this._hass);
    const rhythms = Object.keys(this._hass.states).filter(
      (e) => e.startsWith("sensor.") && this._hass.states[e].attributes?.rhythm,
    );
    const options = rhythms
      .map((e) => {
        const st = this._hass.states[e];
        const name = st.attributes.friendly_name || e;
        return `<option value="${esc(e)}"${e === this._config.entity ? " selected" : ""}>${esc(name)}</option>`;
      })
      .join("");
    this.shadowRoot.innerHTML = `<style>
      .ed { display: grid; gap: 14px; padding: 4px 0; font: 14px/1.4 var(--ha-font-family-body, system-ui, sans-serif); color: var(--primary-text-color); }
      label { display: grid; gap: 4px; } .check { display: flex; gap: 8px; align-items: center; }
      select { min-height: 36px; border-radius: 8px; border: 1px solid var(--divider-color, #ccc); background: var(--card-background-color, #fff); color: inherit; padding: 4px 8px; font: inherit; }
      .hint { font-size: 13px; color: var(--secondary-text-color); }</style>
      <div class="ed">
        <label>${esc(t("Rhythm", "Rhythmus"))}<select id="entity">${options || `<option value="">${esc(t("No rhythm yet", "Noch kein Rhythmus"))}</option>`}</select></label>
        <label>${esc(t("Variant", "Variante"))}<select id="variant">
          <option value="full"${this._config.variant === "full" ? " selected" : ""}>${esc(t("Full", "Voll"))}</option>
          <option value="compact"${this._config.variant === "compact" ? " selected" : ""}>${esc(t("Compact", "Kompakt"))}</option></select></label>
        <label class="check"><input type="checkbox" id="tomorrow"${this._config.tomorrow ? " checked" : ""}> ${esc(t("Also show tomorrow", "Auch morgen zeigen"))}</label>
        <div class="hint">${esc(t("The compact variant shows only the time of day and pinning.", "Die kompakte Variante zeigt nur Tageszeit und Festsetzen."))}</div>
      </div>`;
  }

  _onChange(e) {
    const el = e.target;
    const next = { ...this._config };
    if (el.id === "entity") next.entity = el.value;
    if (el.id === "variant") next.variant = el.value;
    if (el.id === "tomorrow") next.tomorrow = el.checked;
    this._config = next;
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: next }, bubbles: true, composed: true }));
  }
}

// Home Assistant replaces its element registry while its app starts; define only after that.
const define = () => {
  if (!customElements.get("maestro-card-editor")) customElements.define("maestro-card-editor", MaestroCardEditor);
  if (!customElements.get("maestro-card")) customElements.define("maestro-card", MaestroCard);
};
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "maestro-card")) {
  window.customCards.push({
    type: "maestro-card",
    name: "Maestro",
    description: "The time of day of a rhythm, its day as a timeline, and pinning or adjusting it.",
    preview: true,
    documentationURL: "https://github.com/MadisonMedia/cloudless-maestro",
  });
}
if (!document.querySelector("home-assistant")) define();
else {
  const whenReady = () => (window.customElements.get("home-assistant") ? define() : setTimeout(whenReady, 50));
  whenReady();
}
