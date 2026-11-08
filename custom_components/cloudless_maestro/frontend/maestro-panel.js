// The Maestro page in the sidebar: rhythms, times of day, day models, week plan, calendar and diagnostics.

const shared = await import(new URL(`./maestro-shared.js${new URL(import.meta.url).search}`, import.meta.url).href);
const { addDays, clamp, clockOf, esc, fmtDate, fmtTime, icon, inkOn, isDark, langOf, localParts, makeKey, minutesOf, tr } = shared;

const STYLE = `
:host { display: block; min-height: 100%; background: var(--primary-background-color, #eef1f5); color: var(--ink); font: 400 15px/1.45 var(--paper-font-body1_-_font-family, var(--ha-font-family-body, system-ui, sans-serif));
  --ink: var(--primary-text-color, #171d2d); --muted: var(--secondary-text-color, #566077); --surface: var(--card-background-color, #fff); --field: var(--card-background-color, #fff); --line: var(--divider-color, #d4dae6); --accent: var(--primary-color, #2f5fd0); --accent-ink: var(--text-primary-color, #fff); --accent-soft: color-mix(in srgb, var(--accent) 16%, transparent); --well: color-mix(in srgb, var(--ink) 9%, var(--surface));
  --warn: #8a5300; --warn-soft: #fbeed6; --good: #1f6f47; --good-soft: #dcf1e5; }
:host([dark]) { --warn: #f0bd6a; --warn-soft: #3a2b12; --good: #7fd6a6; --good-soft: #15352a; }
* { box-sizing: border-box; }
[hidden] { display: none !important; }
h1, h2, h3, p { margin: 0; }
button, input, select { font: inherit; color: inherit; }
button { cursor: pointer; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.shell { container-type: inline-size; max-width: 1280px; margin: 0 auto; padding-block: 16px 56px; padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); display: grid; gap: 16px; }
.top { display: flex; flex-wrap: wrap; align-items: center; gap: 12px 20px; }
.menu { border: 0; background: transparent; width: 36px; height: 36px; border-radius: 50%; display: grid; place-items: center; padding: 0; }
.mark { font-size: 22px; font-weight: 750; letter-spacing: -.01em; }
.tabs, .seg { display: inline-flex; flex-wrap: wrap; gap: 2px; padding: 3px; background: var(--line); border-radius: 10px; }
.tabs button, .seg button { border: 0; background: transparent; padding: 6px 14px; border-radius: 8px; font-weight: 500; color: var(--muted); }
.tabs button[aria-selected="true"], .seg button[aria-pressed="true"] { background: var(--surface); color: var(--ink); font-weight: 600; }
.layout { display: grid; grid-template-columns: 200px minmax(0, 1fr); gap: 20px; align-items: start; }
.rhythms h2 { font-size: 12px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); }
.rlist { display: grid; gap: 2px; margin-top: 6px; }
.rlist button { text-align: left; border: 0; background: transparent; padding: 8px 10px; border-radius: 8px; overflow-wrap: anywhere; }
.rlist button:hover { background: var(--line); }
.rlist button[aria-current="true"] { background: var(--accent-soft); font-weight: 600; }
.rnew { display: grid; gap: 6px; margin-top: 12px; }
.rnew input, .rnew select { width: 100%; }
.sheet { background: var(--surface); border: 1px solid var(--line); border-radius: 14px; padding: 18px; display: grid; grid-template-columns: minmax(0, 1fr); gap: 28px; min-width: 0; }
.sec { display: grid; grid-template-columns: minmax(0, 1fr); gap: 12px; min-width: 0; }
.sec > h2 { font-size: 17px; font-weight: 650; }
.sub { font-size: 14.5px; font-weight: 600; }
.note { font-size: 13.5px; color: var(--muted); max-width: 76ch; }
.row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.row.space { justify-content: space-between; }
.field { background: var(--field); border: 1px solid var(--line); border-radius: 8px; min-height: 36px; padding: 5px 9px; max-width: 100%; }
.field.title { font-size: 21px; font-weight: 650; width: min(100%, 360px); }
input.num { width: 76px; font-variant-numeric: tabular-nums; }
input.time { width: 112px; font-variant-numeric: tabular-nums; }
input.color { width: 44px; height: 34px; padding: 2px; min-height: 0; }
input.icon { width: 190px; }
.btn { border: 1px solid var(--line); background: var(--field); border-radius: 8px; min-height: 36px; padding: 5px 12px; font-weight: 500; display: inline-flex; gap: 6px; align-items: center; }
.btn:hover { border-color: var(--accent); }
.btn:disabled { opacity: .5; cursor: not-allowed; }
.btn.primary { background: var(--accent); border-color: var(--accent); color: var(--accent-ink); font-weight: 600; }
.btn.danger { color: var(--warn); }
.x { border: 0; background: transparent; color: var(--muted); width: 28px; height: 28px; border-radius: 6px; font-size: 17px; line-height: 1; flex: none; padding: 0; }
.x:hover { background: var(--line); color: var(--ink); }
.x:disabled { opacity: .3; cursor: default; }
.notice { display: grid; gap: 6px; padding: 9px 12px; border-radius: 9px; background: var(--warn-soft); color: var(--warn); font-size: 13.5px; }
.notice.calm { background: var(--accent-soft); color: var(--ink); }
.wrapx { overflow-x: auto; border: 1px solid var(--line); border-radius: 10px; }
table { border-collapse: separate; border-spacing: 0; width: 100%; }
.tbl th { font-size: 12.5px; font-weight: 500; color: var(--muted); text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line); white-space: nowrap; }
.tbl td { padding: 6px 10px; border-bottom: 1px solid var(--line); vertical-align: middle; }
.tbl tr:last-child td { border-bottom: 0; }
.tbl td.res { font-variant-numeric: tabular-nums; white-space: nowrap; font-size: 13.5px; }
.tbl td.res.off { color: var(--warn); }
.tbl .opt { display: inline-flex; gap: 5px; align-items: center; font-size: 13px; color: var(--muted); white-space: nowrap; }
.key { font: 500 12.5px/1 ui-monospace, Menlo, monospace; color: var(--muted); background: var(--well); padding: 3px 6px; border-radius: 5px; white-space: nowrap; }
.spec { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.swatch { display: inline-grid; place-items: center; width: 28px; height: 28px; border-radius: 8px; flex: none; }
.models { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.models button.m { border: 1px solid var(--line); background: var(--field); border-radius: 99px; padding: 5px 14px; font-weight: 500; }
.models button.m[aria-pressed="true"] { background: var(--accent); border-color: var(--accent); color: var(--accent-ink); font-weight: 600; }
.axis { position: relative; padding: 0 0 26px; touch-action: none; user-select: none; -webkit-user-select: none; }
.axis .bar { position: relative; height: 44px; border-radius: 10px; background: var(--well); overflow: hidden; }
.axis .seg { position: absolute; top: 0; bottom: 0; display: flex; align-items: center; gap: 4px; padding: 0 8px; font-size: 12.5px; font-weight: 600; overflow: hidden; white-space: nowrap; border-right: 2px solid var(--surface); }
.axis .seg span { overflow: hidden; text-overflow: ellipsis; }
.axis .grid { position: absolute; top: 0; bottom: 0; width: 1px; background: color-mix(in srgb, var(--ink) 12%, transparent); pointer-events: none; }
.axis .hour { position: absolute; top: 52px; transform: translateX(-50%); font-size: 11px; color: var(--muted); pointer-events: none; font-variant-numeric: tabular-nums; }
.axis .handle { position: absolute; top: -6px; height: 56px; width: 18px; margin-left: -9px; display: grid; justify-items: center; cursor: ew-resize; touch-action: none; }
.axis .handle::before { content: ""; width: 4px; height: 56px; border-radius: 3px; background: var(--ink); opacity: .8; }
.axis .handle.sun { cursor: default; }
.axis .handle.sun::before { background: repeating-linear-gradient(var(--ink) 0 5px, transparent 5px 9px); opacity: .6; }
.axis .handle.drag::before { background: var(--accent); opacity: 1; }
.axis .tip { position: absolute; top: 50px; z-index: 1; transform: translateX(-50%); font-size: 11.5px; font-weight: 600; background: var(--surface); border: 1px solid var(--line); padding: 0 5px; border-radius: 5px; white-space: nowrap; font-variant-numeric: tabular-nums; pointer-events: none; }
.week { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 8px; }
.week label { display: grid; gap: 4px; font-size: 13px; color: var(--muted); }
.week select { width: 100%; }
.month { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 4px; }
.month .wd { font-size: 12px; color: var(--muted); text-align: center; padding: 2px 0; }
.month button.d { min-height: 64px; border: 1px solid var(--line); background: var(--field); border-radius: 9px; padding: 5px 6px; text-align: left; display: grid; align-content: start; gap: 2px; min-width: 0; }
.month button.d.other { opacity: .45; }
.month button.d.today { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent) inset; }
.month button.d.sel { background: var(--accent-soft); }
.month .n { font-size: 12.5px; font-weight: 650; display: flex; justify-content: space-between; gap: 4px; }
.month .mname { font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.month .src { color: var(--accent); }
.legend { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 13px; color: var(--muted); }
.legend span { display: inline-flex; gap: 5px; align-items: center; }
.facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
.fact { background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 12px 14px; display: grid; gap: 4px; }
.fact h3 { font-size: 13px; font-weight: 500; color: var(--muted); }
.fact b { font-size: 18px; font-weight: 600; }
.pill { display: inline-block; padding: 2px 9px; border-radius: 99px; font-size: 12.5px; white-space: nowrap; }
.pill.ok { background: var(--good-soft); color: var(--good); }
.pill.warn { background: var(--warn-soft); color: var(--warn); }
pre { margin: 0; padding: 12px 14px; font: 400 12.5px/1.55 ui-monospace, Menlo, monospace; background: #11152a; color: #dfe4f2; border-radius: 10px; overflow-x: auto; }
.toast { position: fixed; left: 50%; transform: translateX(-50%); bottom: calc(16px + env(safe-area-inset-bottom, 0px)); z-index: 20; max-width: calc(100vw - 32px); padding: 9px 14px; border-radius: 10px; background: var(--ink); color: var(--surface); font-size: 14px; }
@container (max-width: 900px) {
  .layout { grid-template-columns: minmax(0, 1fr); }
  .rlist { display: flex; flex-wrap: wrap; }
  .rnew { display: flex; flex-wrap: wrap; }
  .rnew input, .rnew select { width: auto; flex: 1 1 140px; }
  .sheet { padding: 14px; }
}
@container (max-width: 640px) {
  .week { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .month button.d { min-height: 52px; }
  .month .mname { font-size: 10.5px; }
}
`;

const MENU_ICON = '<svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M3 6h18v2H3zm0 5h18v2H3zm0 5h18v2H3z"/></svg>';
const WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
const DAY_NAMES = { mon: ["Mon", "Mo"], tue: ["Tue", "Di"], wed: ["Wed", "Mi"], thu: ["Thu", "Do"], fri: ["Fri", "Fr"], sat: ["Sat", "Sa"], sun: ["Sun", "So"] };
const EVENTS = {
  dawn: ["Dawn (civil)", "Morgendämmerung"],
  sunrise: ["Sunrise", "Sonnenaufgang"],
  noon: ["Solar noon", "Sonnenhöchststand"],
  sunset: ["Sunset", "Sonnenuntergang"],
  dusk: ["Dusk (civil)", "Abenddämmerung"],
};
const AXIS_MIN = 0,
  AXIS_MAX = 30 * 60;
const clone = (x) => JSON.parse(JSON.stringify(x));

class MaestroPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._rhythms = [];
    this._i = 0;
    this._view = "setup";
    this._model = null;
    this._previewDate = null;
    this._preview = null;
    this._month = null;
    this._monthStart = null;
    this._selDay = null;
    this._dayPlan = null;
    this._diag = null;
    this._templates = [];
    this._confirm = null;
    this._error = null;
    this._drag = null;
    const r = this.shadowRoot;
    r.addEventListener("click", (e) => this._onClick(e));
    r.addEventListener("change", (e) => this._onChange(e));
    r.addEventListener("input", (e) => this._onInput(e));
    r.addEventListener("pointerdown", (e) => this._onDown(e));
    r.addEventListener("pointermove", (e) => this._onMove(e));
    r.addEventListener("pointerup", (e) => this._onUp(e));
    r.addEventListener("pointercancel", () => {
      this._drag = null;
      this._renderAxis();
    });
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    const dark = isDark(this.isConnected ? this : null, hass);
    if (dark !== this._dark) {
      this._dark = dark;
      this.toggleAttribute("dark", dark);
    }
    if (first) this._load();
  }

  set narrow(v) {
    this._narrow = v;
    const m = this.shadowRoot.querySelector(".menu");
    if (m) m.hidden = !v;
  }

  set panel(_v) {}
  set route(_v) {}

  connectedCallback() {
    // Home Assistant can set these before this script has loaded. They would then hide the setters above.
    for (const name of ["hass", "narrow", "panel", "route"]) {
      if (Object.hasOwn(this, name)) {
        const value = this[name];
        delete this[name];
        this[name] = value;
      }
    }
  }

  get _t() {
    return tr(this._hass);
  }

  get _r() {
    return this._rhythms[this._i];
  }

  get _w() {
    return this._r?.work;
  }

  async _load(select) {
    const list = await this._hass.callWS({ type: "cloudless_maestro/rhythms" });
    this._rhythms = list.map((r) => ({ ...r, work: clone(r.options) }));
    if (select) this._i = Math.max(0, this._rhythms.findIndex((r) => r.entry_id === select));
    this._i = Math.min(this._i, Math.max(0, this._rhythms.length - 1));
    try {
      this._templates = await this._hass.callWS({ type: "cloudless_maestro/templates", language: langOf(this._hass) });
    } catch {
      this._templates = [];
    }
    this._resetSelection();
    this._render();
  }

  _resetSelection() {
    this._model = this._w?.models[0]?.key || null;
    this._previewDate = localParts(this._hass, new Date().toISOString()).date;
    this._preview = null;
    this._month = null;
    this._monthStart = null;
    this._selDay = null;
    this._dayPlan = null;
    this._diag = null;
    this._confirm = null;
    this._error = null;
    if (this._r) this._fetchPreview();
  }

  // -- saving -----------------------------------------------------------------------------------------

  _changed({ render = true, preview = true } = {}) {
    clearTimeout(this._saveTimer);
    this._saveTimer = setTimeout(() => this._save(), 500);
    if (preview) {
      clearTimeout(this._previewTimer);
      this._previewTimer = setTimeout(() => this._fetchPreview(), 250);
    }
    if (render) this._renderMain();
  }

  async _save() {
    const r = this._r;
    if (!r) return;
    try {
      const res = await this._hass.callWS({ type: "cloudless_maestro/rhythm/save", entry_id: r.entry_id, title: r.title, options: r.work });
      r.options = res.options;
      this._setError(null);
      this._toast(this._t("Saved", "Gespeichert"));
    } catch (err) {
      this._setError(err?.message || String(err));
    }
  }

  _setError(message) {
    if (message === this._error) return;
    this._error = message;
    const box = this.shadowRoot.getElementById("saveError");
    if (box) {
      box.hidden = !message;
      box.textContent = message ? `${this._t("Not saved", "Nicht gespeichert")}: ${message}` : "";
    }
  }

  _toast(text) {
    const el = this.shadowRoot.getElementById("toast");
    if (!el) return;
    el.textContent = text;
    el.hidden = false;
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => (el.hidden = true), 1600);
  }

  async _fetchPreview() {
    const r = this._r;
    if (!r || !this._model || !r.work.models.some((m) => m.key === this._model)) {
      this._preview = null;
      return;
    }
    const year = this._previewDate.slice(0, 4);
    const dates = [this._previewDate, `${year}-06-21`, `${year}-12-21`];
    try {
      const result = await this._hass.callWS({ type: "cloudless_maestro/preview", entry_id: r.entry_id, options: r.work, model: this._model, dates });
      this._preview = result;
    } catch {
      this._preview = null;
    }
    this._renderModelResults();
  }

  // -- lookups ----------------------------------------------------------------------------------------

  _look(key) {
    const w = this._w;
    if (!w) return null;
    if (key === w.base.key) return w.base;
    return w.times_of_day.find((t) => t.key === key) || { key, name: key, color: "#7a8599" };
  }

  _usedKeys() {
    const w = this._w;
    return [w.base.key, ...w.times_of_day.map((t) => t.key)];
  }

  _currentModel() {
    return this._w?.models.find((m) => m.key === this._model) || null;
  }

  // -- rendering --------------------------------------------------------------------------------------

  _render() {
    const t = this._t;
    this.shadowRoot.innerHTML = `<style>${STYLE}</style><div class="shell">
      <header class="top">
        <button class="menu" data-act="menu" aria-label="Menu" ${this._narrow ? "" : "hidden"}>${MENU_ICON}</button>
        <h1 class="mark">Maestro</h1>
        <div class="tabs" role="tablist">
          <button role="tab" data-act="tab" data-v="setup" aria-selected="${this._view === "setup"}">${esc(t("Setup", "Einrichtung"))}</button>
          <button role="tab" data-act="tab" data-v="calendar" aria-selected="${this._view === "calendar"}">${esc(t("Calendar", "Kalender"))}</button>
          <button role="tab" data-act="tab" data-v="diag" aria-selected="${this._view === "diag"}">${esc(t("Diagnostics", "Diagnose"))}</button>
        </div>
      </header>
      <div class="layout">
        <aside class="rhythms"><h2>${esc(t("Rhythms", "Rhythmen"))}</h2><div class="rlist">${this._rhythms
          .map((r, i) => `<button data-act="pick" data-i="${i}" aria-current="${i === this._i}">${esc(r.title)}</button>`)
          .join("")}</div>
          <div class="rnew"><input class="field" id="newName" placeholder="${esc(t("New rhythm", "Neuer Rhythmus"))}" aria-label="${esc(t("Name of the new rhythm", "Name des neuen Rhythmus"))}">
            <select class="field" id="newTemplate" aria-label="${esc(t("Start with", "Beginnen mit"))}"><option value="day">${esc(t("A typical day", "Typischer Tag"))}</option><option value="empty">${esc(t("One time of day", "Eine Tageszeit"))}</option></select>
            <button class="btn" data-act="create">${esc(t("Create", "Anlegen"))}</button></div></aside>
        <main id="main"></main>
      </div></div><div class="toast" id="toast" hidden></div>`;
    this._renderMain();
  }

  _renderMain() {
    const main = this.shadowRoot.getElementById("main");
    if (!main) return;
    const t = this._t;
    if (!this._r) {
      main.innerHTML = `<div class="sheet"><div class="sec"><h2>${esc(t("No rhythm yet", "Noch kein Rhythmus"))}</h2><p class="note">${esc(t("Enter a name on the left and create your first rhythm, for example for your flat.", "Gib links einen Namen ein und lege deinen ersten Rhythmus an, zum Beispiel für deine Wohnung."))}</p></div></div>`;
      return;
    }
    if (this._view === "calendar") return this._renderCalendar(main);
    if (this._view === "diag") return this._renderDiag(main);
    const w = this._w;
    main.innerHTML = `<div class="sheet">
      <div class="notice" id="saveError" ${this._error ? "" : "hidden"}>${esc(this._error ? `${t("Not saved", "Nicht gespeichert")}: ${this._error}` : "")}</div>
      ${this._rhythmSection()}
      ${this._todSection()}
      ${this._modelSection()}
      <section class="sec"><h2>${esc(t("Week plan", "Wochenplan"))}</h2>
        <p class="note">${esc(t("Every weekday gets a day model. A calendar link or a day adjustment can override single dates.", "Jeder Wochentag bekommt ein Tagesmodell. Eine Kalender-Verknüpfung oder eine Tagesanpassung kann einzelne Daten übersteuern."))}</p>
        <div class="week">${WEEKDAYS.map((d) => `<label>${esc(t(...DAY_NAMES[d]))}<select class="field" data-week="${d}">${this._modelOptions(w.week[d], true)}</select></label>`).join("")}</div></section>
      ${this._linkSection()}
      ${this._automationSection()}
    </div>`;
    this._renderAxis();
    this._renderModelResults();
  }

  _modelOptions(selected, allowNone = false) {
    const t = this._t;
    const none = allowNone ? `<option value=""${!selected ? " selected" : ""}>${esc(t("— only the base state", "— nur Grundzustand"))}</option>` : "";
    return none + this._w.models.map((m) => `<option value="${esc(m.key)}"${m.key === selected ? " selected" : ""}>${esc(m.name)}</option>`).join("");
  }

  _rhythmSection() {
    const t = this._t;
    const r = this._r,
      w = this._w,
      loc = w.location;
    const confirming = this._confirm === "rhythm";
    return `<section class="sec">
      <div class="row space"><input class="field title" id="title" value="${esc(r.title)}" aria-label="${esc(t("Name of the rhythm", "Name des Rhythmus"))}">
        <span class="row">${confirming ? `<span class="note">${esc(t("Delete this rhythm with everything in it?", "Diesen Rhythmus mit allem darin löschen?"))}</span><button class="btn danger" data-act="delete-rhythm">${esc(t("Delete", "Löschen"))}</button><button class="btn" data-act="confirm" data-v="">${esc(t("Keep", "Behalten"))}</button>` : `<button class="btn" data-act="confirm" data-v="rhythm">${esc(t("Delete rhythm", "Rhythmus löschen"))}</button>`}</span></div>
      <div class="row"><span class="sub">${esc(t("Base state", "Grundzustand"))}</span>
        <input class="field color" type="color" data-base="color" value="${esc(w.base.color)}" aria-label="${esc(t("Color", "Farbe"))}">
        <input class="field icon" data-base="icon" value="${esc(w.base.icon)}" aria-label="${esc(t("Icon", "Symbol"))}">
        <input class="field" data-base="name" value="${esc(w.base.name)}" aria-label="${esc(t("Name of the base state", "Name des Grundzustands"))}">
        <span class="key" title="${esc(t("Key for automations", "Schlüssel für Automationen"))}">${esc(w.base.key)}</span></div>
      <p class="note">${esc(t("The base state applies between the end of one day and the start of the next.", "Der Grundzustand gilt vom Ende eines Tages bis zum Beginn des nächsten."))}</p>
      <div class="row"><label class="row"><input type="checkbox" id="locHa"${loc ? "" : " checked"}> ${esc(t("Sun times for the location of Home Assistant", "Sonnenzeiten für den Standort von Home Assistant"))}</label>
        ${loc ? `<input class="field num" id="lat" type="number" step="0.0001" min="-90" max="90" value="${esc(loc.latitude)}" aria-label="${esc(t("Latitude", "Breitengrad"))}"><input class="field num" id="lon" type="number" step="0.0001" min="-180" max="180" value="${esc(loc.longitude)}" aria-label="${esc(t("Longitude", "Längengrad"))}">` : ""}</div>
    </section>`;
  }

  _todSection() {
    const t = this._t;
    const w = this._w;
    const rows = w.times_of_day
      .map((tod, i) => {
        const used = w.models.filter((m) => m.entries.some((e) => e.tod === tod.key)).map((m) => m.name);
        const confirming = this._confirm === `tod:${tod.key}`;
        return `<tr>
          <td><span class="row" style="flex-wrap:nowrap"><input class="field color" type="color" data-tod="${i}" data-field="color" value="${esc(tod.color)}" aria-label="${esc(t("Color", "Farbe"))}">
            <span class="swatch" style="background:${esc(tod.color)};color:${inkOn(tod.color)}">${icon(tod.icon, 18)}</span></span></td>
          <td><input class="field" data-tod="${i}" data-field="name" value="${esc(tod.name)}" aria-label="${esc(t("Name", "Name"))}"></td>
          <td><input class="field icon" data-tod="${i}" data-field="icon" value="${esc(tod.icon)}" aria-label="${esc(t("Icon", "Symbol"))}"></td>
          <td><span class="key">${esc(tod.key)}</span></td>
          <td><input class="field num" type="number" min="0" max="3600" data-tod="${i}" data-field="transition" value="${esc(tod.transition)}" aria-label="${esc(t("Transition in seconds", "Übergang in Sekunden"))}"></td>
          <td>${confirming ? `<span class="row"><span class="note">${esc(used.length ? `${t("Used in", "Genutzt in")} ${used.join(", ")}.` : "")}</span><button class="btn danger" data-act="delete-tod" data-key="${esc(tod.key)}">${esc(t("Delete", "Löschen"))}</button><button class="btn" data-act="confirm" data-v="">${esc(t("Keep", "Behalten"))}</button></span>` : `<button class="x" data-act="confirm" data-v="tod:${esc(tod.key)}" aria-label="${esc(t("Delete", "Löschen"))}">×</button>`}</td>
        </tr>`;
      })
      .join("");
    const free = this._templates.filter((tpl) => !w.times_of_day.some((x) => x.name === tpl.name));
    return `<section class="sec"><h2>${esc(t("Times of day", "Tageszeiten"))}</h2>
      <p class="note">${esc(t("Each time of day has a name, an icon and a color. Its key stays the same when you rename it, so automations keep working. The transition applies when the time of day begins.", "Jede Tageszeit hat Name, Symbol und Farbe. Ihr Schlüssel bleibt beim Umbenennen gleich, damit Automationen weiterlaufen. Der Übergang gilt, wenn die Tageszeit beginnt."))}</p>
      <div class="wrapx"><table class="tbl"><thead><tr><th>${esc(t("Color", "Farbe"))}</th><th>${esc(t("Name", "Name"))}</th><th>${esc(t("Icon", "Symbol"))}</th><th>${esc(t("Key", "Schlüssel"))}</th><th>${esc(t("Transition (s)", "Übergang (s)"))}</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>
      <div class="row">${free.length ? `<select class="field" id="tplSel" aria-label="${esc(t("Template", "Vorlage"))}">${free.map((tpl, i) => `<option value="${i}">${esc(tpl.name)}</option>`).join("")}</select><button class="btn" data-act="add-tpl">${esc(t("Add template", "Vorlage hinzufügen"))}</button>` : ""}
        <input class="field" id="newTod" placeholder="${esc(t("New time of day", "Neue Tageszeit"))}" aria-label="${esc(t("Name of the new time of day", "Name der neuen Tageszeit"))}">
        <select class="field" id="newTodFrom" aria-label="${esc(t("Take the look from", "Aussehen übernehmen von"))}"><option value="">${esc(t("New look", "Neues Aussehen"))}</option>${w.times_of_day.map((x) => `<option value="${esc(x.key)}">${esc(t("Like", "Wie"))} ${esc(x.name)}</option>`).join("")}</select>
        <button class="btn" data-act="add-tod">${esc(t("Add", "Hinzufügen"))}</button></div>
    </section>`;
  }

  _modelSection() {
    const t = this._t;
    const w = this._w;
    const model = this._currentModel();
    const chips = w.models
      .map((m) => `<button class="m" data-act="model" data-key="${esc(m.key)}" aria-pressed="${m.key === this._model}">${esc(m.name)}</button>`)
      .join("");
    let body = "";
    if (model) {
      const usedIn = WEEKDAYS.filter((d) => w.week[d] === model.key).length + w.calendar_links.filter((l) => l.model === model.key).length;
      const confirming = this._confirm === `model:${model.key}`;
      const free = w.times_of_day.filter((x) => !model.entries.some((e) => e.tod === x.key));
      body = `<div class="row space"><span class="row"><input class="field" id="modelName" value="${esc(model.name)}" aria-label="${esc(t("Name of the day model", "Name des Tagesmodells"))}"><span class="key">${esc(model.key)}</span></span>
          <span class="row"><button class="btn" data-act="copy-model">${esc(t("Copy", "Kopieren"))}</button>
          ${confirming ? `<button class="btn danger" data-act="delete-model">${esc(t("Delete", "Löschen"))}</button><button class="btn" data-act="confirm" data-v="">${esc(t("Keep", "Behalten"))}</button>` : `<button class="btn" data-act="confirm" data-v="model:${esc(model.key)}" ${usedIn ? `disabled title="${esc(t("Used in the week plan or a calendar link", "Wird im Wochenplan oder in einer Kalender-Verknüpfung genutzt"))}"` : ""}>${esc(t("Delete", "Löschen"))}</button>`}</span></div>
        <div class="row"><label class="row">${esc(t("Preview for", "Vorschau für"))} <input class="field" type="date" id="previewDate" value="${esc(this._previewDate)}"></label>
          <button class="btn" data-act="preview-today">${esc(t("Today", "Heute"))}</button></div>
        <div class="axis" id="axis"></div>
        <p class="note">${esc(t("Drag the marks of fixed times. Dashed marks follow the sun. A time after midnight belongs to the same day and shows +1.", "Ziehe die Markierungen fester Zeiten. Gestrichelte folgen der Sonne. Eine Zeit nach Mitternacht gehört zum selben Tag und zeigt +1."))}</p>
        <div class="notice calm" id="dropNote" hidden></div>
        <div class="wrapx"><table class="tbl" id="entries">${this._entryRows(model)}</table></div>
        <div class="row">${free.length ? `<select class="field" id="addEntry" aria-label="${esc(t("Time of day", "Tageszeit"))}">${free.map((x) => `<option value="${esc(x.key)}">${esc(x.name)}</option>`).join("")}</select><button class="btn" data-act="add-entry">${esc(t("Add to the model", "Zum Modell hinzufügen"))}</button>` : `<span class="note">${esc(t("All times of day are in this model.", "Alle Tageszeiten sind in diesem Modell."))}</span>`}</div>`;
    }
    return `<section class="sec"><h2>${esc(t("Day models", "Tagesmodelle"))}</h2>
      <p class="note">${esc(t("A day model lists which times of day happen with which start, and when the day ends. Changes apply at once, also to the running day.", "Ein Tagesmodell legt fest, welche Tageszeiten mit welcher Startzeit stattfinden und wann der Tag endet. Änderungen gelten sofort, auch für den laufenden Tag."))}</p>
      <div class="models">${chips}<input class="field" id="newModel" placeholder="${esc(t("New day model", "Neues Tagesmodell"))}" aria-label="${esc(t("Name of the new day model", "Name des neuen Tagesmodells"))}"><button class="btn" data-act="add-model">${esc(t("Add", "Hinzufügen"))}</button></div>
      ${body}</section>`;
  }

  _specEditor(spec, ref) {
    const t = this._t;
    const kind = `<select class="field" data-entry="${ref}" data-field="kind" aria-label="${esc(t("Kind", "Art"))}"><option value="fixed"${spec.kind === "fixed" ? " selected" : ""}>${esc(t("Fixed", "Fest"))}</option><option value="sun"${spec.kind === "sun" ? " selected" : ""}>${esc(t("Sun", "Sonne"))}</option></select>`;
    const plus = `<label class="opt"><input type="checkbox" data-entry="${ref}" data-field="next_day"${spec.next_day ? " checked" : ""}> +1</label>`;
    if (spec.kind === "fixed") {
      return `<span class="spec">${kind}<input class="field time" type="time" data-entry="${ref}" data-field="time" value="${esc(spec.time)}" aria-label="${esc(t("Time", "Uhrzeit"))}">${plus}</span>`;
    }
    const events = Object.entries(EVENTS)
      .map(([k, names]) => `<option value="${k}"${spec.event === k ? " selected" : ""}>${esc(t(...names))}</option>`)
      .join("");
    return `<span class="spec">${kind}<select class="field" data-entry="${ref}" data-field="event" aria-label="${esc(t("Sun event", "Sonnenstand"))}">${events}</select>
      <span class="opt"><input class="field num" type="number" min="-720" max="720" step="5" data-entry="${ref}" data-field="offset" value="${esc(spec.offset)}" aria-label="${esc(t("Offset in minutes", "Versatz in Minuten"))}"> min</span>
      <label class="opt">${esc(t("earliest", "frühestens"))} <input class="field time" type="time" data-entry="${ref}" data-field="earliest" value="${esc(spec.earliest || "")}"></label>
      <label class="opt">${esc(t("latest", "spätestens"))} <input class="field time" type="time" data-entry="${ref}" data-field="latest" value="${esc(spec.latest || "")}"></label>${plus}</span>`;
  }

  _entryRows(model) {
    const t = this._t;
    const w = this._w;
    const year = this._previewDate.slice(0, 4);
    const heads = [fmtDate(this._hass, this._previewDate), fmtDate(this._hass, `${year}-06-21`, { day: "numeric", month: "short" }), fmtDate(this._hass, `${year}-12-21`, { day: "numeric", month: "short" })];
    const rows = model.entries
      .map((e, i) => {
        const tod = this._look(e.tod);
        return `<tr><td><span class="row" style="flex-wrap:nowrap"><button class="x" data-act="move" data-i="${i}" data-d="-1" ${i ? "" : "disabled"} aria-label="${esc(t("Up", "Nach oben"))}">↑</button><button class="x" data-act="move" data-i="${i}" data-d="1" ${i < model.entries.length - 1 ? "" : "disabled"} aria-label="${esc(t("Down", "Nach unten"))}">↓</button>
          <span class="swatch" style="background:${esc(tod.color)};color:${inkOn(tod.color)}">${icon(tod.icon, 16)}</span><b>${esc(tod.name)}</b></span></td>
          <td>${this._specEditor(e.at, i)}</td>
          ${[0, 1, 2].map((n) => `<td class="res" data-res="${n}" data-key="${esc(e.tod)}"></td>`).join("")}
          <td><button class="x" data-act="remove-entry" data-i="${i}" aria-label="${esc(t("Remove", "Entfernen"))}">×</button></td></tr>`;
      })
      .join("");
    return `<thead><tr><th>${esc(t("Time of day", "Tageszeit"))}</th><th>${esc(t("Start", "Start"))}</th>${heads.map((h) => `<th>${esc(h)}</th>`).join("")}<th></th></tr></thead>
      <tbody>${rows}<tr><td><span class="row" style="flex-wrap:nowrap"><span class="swatch" style="background:${esc(w.base.color)};color:${inkOn(w.base.color)}">${icon(w.base.icon, 16)}</span><b>${esc(w.base.name)} ${esc(t("from", "ab"))}</b></span></td>
        <td>${this._specEditor(model.end, "end")}</td>${[0, 1, 2].map((n) => `<td class="res" data-res="${n}" data-key=""></td>`).join("")}<td></td></tr></tbody>`;
  }

  // Minutes since midnight of the preview date, beyond 1440 for the following day.
  _axisMinutes(iso, date) {
    const p = localParts(this._hass, iso);
    const days = Math.round((new Date(`${p.date}T12:00:00Z`) - new Date(`${date}T12:00:00Z`)) / 86400000);
    return days * 1440 + minutesOf(p.time);
  }

  _renderModelResults() {
    const table = this.shadowRoot.getElementById("entries");
    if (!table || !this._preview) return;
    const t = this._t;
    this._preview.forEach((res, n) => {
      const starts = Object.fromEntries(res.entries.map((e) => [e.key, e.start]));
      table.querySelectorAll(`td[data-res="${n}"]`).forEach((td) => {
        const key = td.dataset.key;
        const iso = key ? starts[key] : res.end;
        if (iso) {
          const mins = this._axisMinutes(iso, res.day);
          td.textContent = `${fmtTime(this._hass, iso)}${mins >= 1440 ? " +1" : ""}`;
          td.classList.remove("off");
        } else {
          td.textContent = res.entries.length || key ? t("does not happen", "fällt aus") : "—";
          td.classList.toggle("off", !!key);
        }
      });
    });
    const first = this._preview[0];
    const note = this.shadowRoot.getElementById("dropNote");
    if (note) {
      note.hidden = !first.dropped.length;
      note.textContent = first.dropped.length
        ? `${t("On this date, these times of day do not happen because they would start before the previous one or after the day end:", "An diesem Datum fallen diese Tageszeiten aus, weil sie vor der vorherigen oder nach dem Tagesende beginnen würden:")} ${first.dropped.map((k) => this._look(k).name).join(", ")}`
        : "";
    }
    this._renderAxis();
  }

  _renderAxis() {
    const box = this.shadowRoot.getElementById("axis");
    const model = this._currentModel();
    if (!box || !model) return;
    const res = this._preview?.[0];
    const date = res?.day || this._previewDate;
    const pos = (m) => (clamp(m, AXIS_MIN, AXIS_MAX) / AXIS_MAX) * 100;
    const marks = [];
    if (res) {
      for (const e of res.entries) marks.push({ key: e.key, m: this._axisMinutes(e.start, date) });
      if (res.end && res.entries.length) marks.push({ key: "", m: this._axisMinutes(res.end, date) });
    }
    if (this._drag) {
      const mark = marks.find((x) => x.key === this._drag.key);
      if (mark) mark.m = this._drag.m;
      marks.sort((a, b) => a.m - b.m);
    }
    let segs = "";
    const ends = marks.filter((x) => x.key);
    const endMark = marks.find((x) => !x.key);
    ends.forEach((mark, i) => {
      const stop = i + 1 < ends.length ? ends[i + 1].m : endMark ? endMark.m : AXIS_MAX;
      if (stop <= mark.m) return;
      const tod = this._look(mark.key);
      segs += `<div class="seg" style="left:${pos(mark.m)}%;width:${pos(stop) - pos(mark.m)}%;background:${esc(tod.color)};color:${inkOn(tod.color)}">${pos(stop) - pos(mark.m) > 7 ? `${icon(tod.icon, 15)}<span>${esc(tod.name)}</span>` : ""}</div>`;
    });
    let grid = "",
      hours = "";
    for (let h = 3; h < 30; h += 3) {
      grid += `<div class="grid" style="left:${pos(h * 60)}%"></div>`;
      hours += `<span class="hour" style="left:${pos(h * 60)}%">${h % 24}${h >= 24 ? "+1" : ""}</span>`;
    }
    const handles = marks
      .map((mark) => {
        const spec = mark.key ? model.entries.find((e) => e.tod === mark.key)?.at : model.end;
        const sun = spec?.kind === "sun";
        const drag = this._drag?.key === mark.key;
        return `<div class="handle${sun ? " sun" : ""}${drag ? " drag" : ""}" data-handle="${esc(mark.key)}" style="left:${pos(mark.m)}%" title="${esc(mark.key ? this._look(mark.key).name : this._w.base.name)}"></div>${drag ? `<span class="tip" style="left:${pos(mark.m)}%">${clockOf(mark.m)}${mark.m >= 1440 ? " +1" : ""}</span>` : ""}`;
      })
      .join("");
    box.innerHTML = `<div class="bar">${segs}${grid}</div>${hours}${handles}`;
  }

  _linkSection() {
    const t = this._t;
    const w = this._w;
    const calendars = Object.keys(this._hass.states).filter((e) => e.startsWith("calendar."));
    const calOptions = (selected) =>
      calendars
        .concat(selected && !calendars.includes(selected) ? [selected] : [])
        .map((c) => `<option value="${esc(c)}"${c === selected ? " selected" : ""}>${esc(this._hass.states[c]?.attributes?.friendly_name || c)}</option>`)
        .join("");
    const rows = w.calendar_links
      .map(
        (l, i) => `<tr><td><span class="row" style="flex-wrap:nowrap"><button class="x" data-act="move-link" data-i="${i}" data-d="-1" ${i ? "" : "disabled"}>↑</button><button class="x" data-act="move-link" data-i="${i}" data-d="1" ${i < w.calendar_links.length - 1 ? "" : "disabled"}>↓</button></span></td>
          <td><select class="field" data-link="${i}" data-field="calendar">${calOptions(l.calendar)}</select></td>
          <td><input class="field" data-link="${i}" data-field="match" value="${esc(l.match)}" placeholder="${esc(t("every event", "jeder Termin"))}"></td>
          <td><select class="field" data-link="${i}" data-field="model">${this._modelOptions(l.model)}</select></td>
          <td><button class="x" data-act="remove-link" data-i="${i}" aria-label="${esc(t("Remove", "Entfernen"))}">×</button></td></tr>`,
      )
      .join("");
    return `<section class="sec"><h2>${esc(t("Calendar links", "Kalender-Verknüpfungen"))}</h2>
      <p class="note">${esc(t("A calendar from Home Assistant sets the day model on the dates of its events. Use it for public holidays, shift plans or holidays. All-day events count for each of their dates, events with a time for the date they start on. The upper link wins.", "Ein Kalender aus Home Assistant legt an den Daten seiner Termine das Tagesmodell fest. So lassen sich Feiertage, Schichtpläne und Urlaub abbilden. Ganztägige Termine gelten für jedes ihrer Daten, Termine mit Uhrzeit für das Datum, an dem sie beginnen. Die obere Verknüpfung gewinnt."))}</p>
      ${w.calendar_links.length ? `<div class="wrapx"><table class="tbl"><thead><tr><th></th><th>${esc(t("Calendar", "Kalender"))}</th><th>${esc(t("Title contains", "Titel enthält"))}</th><th>${esc(t("Day model", "Tagesmodell"))}</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>` : ""}
      <div class="row">${calendars.length ? `<button class="btn" data-act="add-link">${esc(t("Add link", "Verknüpfung hinzufügen"))}</button>` : `<span class="note">${esc(t("There is no calendar in Home Assistant yet. The integrations Holiday and Local calendar add one.", "In Home Assistant gibt es noch keinen Kalender. Die Integrationen Feiertage (Holiday) und Lokaler Kalender legen einen an."))}</span>`}
        ${w.calendar_links.length ? `<button class="btn" data-act="refresh-cal">${esc(t("Read calendars now", "Kalender jetzt lesen"))}</button>` : ""}</div>
    </section>`;
  }

  _automationSection() {
    const t = this._t;
    const r = this._r;
    const w = this._w;
    const sensor = r.entities?.time_of_day || "sensor.…";
    const example = w.times_of_day.at(-1)?.key || "einschlafen";
    return `<details class="sec"><summary class="sub">${esc(t("In automations", "In Automationen"))}</summary>
      <p class="note">${esc(t("The rhythm is a device. In the automation editor it offers the triggers “A time of day begins”, “A time of day ends” and “The time of day changes”, and the conditions “The time of day is one of” and “The plan is overridden”. The sensor’s state is the key of the time of day.", "Der Rhythmus ist ein Gerät. Im Automationseditor bietet er die Trigger „Eine Tageszeit beginnt“, „Eine Tageszeit endet“ und „Die Tageszeit wechselt“ sowie die Bedingungen „Die Tageszeit ist eine von“ und „Der Plan ist übersteuert“. Der Zustand des Sensors ist der Schlüssel der Tageszeit."))}</p>
      <pre>${esc(`action: cloudless_maestro.pin
target:
  entity_id: ${sensor}
data:
  time_of_day: ${example}
  until: next_change

action: cloudless_maestro.adjust_day
target:
  entity_id: ${sensor}
data:
  times:
    ${example}: "23:30"`)}</pre></details>`;
  }

  // -- calendar view ----------------------------------------------------------------------------------

  async _renderCalendar(main) {
    const t = this._t;
    const today = localParts(this._hass, new Date().toISOString()).date;
    if (!this._monthStart) this._monthStart = `${today.slice(0, 7)}-01`;
    const first = this._monthStart;
    const weekday = (new Date(`${first}T12:00:00Z`).getUTCDay() + 6) % 7;
    const gridStart = addDays(first, -weekday);
    if (!this._month || this._month.start !== gridStart) {
      main.innerHTML = `<div class="sheet"><p class="note">${esc(t("Loading …", "Wird geladen …"))}</p></div>`;
      try {
        const days = await this._hass.callWS({ type: "cloudless_maestro/month", entry_id: this._r.entry_id, start: gridStart, days: 42 });
        this._month = { start: gridStart, days };
      } catch (err) {
        main.innerHTML = `<div class="sheet"><div class="notice">${esc(err?.message || String(err))}</div></div>`;
        return;
      }
    }
    const month = first.slice(0, 7);
    const name = (key) => this._r.options.models.find((m) => m.key === key)?.name || "—";
    const srcIcon = { calendar: "mdi:calendar-star", adjustment: "mdi:calendar-edit" };
    const cells = this._month.days
      .map((d) => {
        const cls = `d${d.day.slice(0, 7) !== month ? " other" : ""}${d.day === today ? " today" : ""}${d.day === this._selDay ? " sel" : ""}`;
        const mark = d.adjustment ? srcIcon.adjustment : srcIcon[d.source];
        return `<button class="${cls}" data-act="day" data-day="${d.day}"><span class="n">${Number(d.day.slice(8))}${mark ? `<span class="src">${icon(mark, 14)}</span>` : ""}</span><span class="mname">${esc(name(d.model))}</span></button>`;
      })
      .join("");
    const heads = WEEKDAYS.map((d) => `<div class="wd">${esc(t(...DAY_NAMES[d]))}</div>`).join("");
    main.innerHTML = `<div class="sheet"><section class="sec">
      <div class="row space"><h2>${esc(fmtDate(this._hass, first, { month: "long", year: "numeric" }))}</h2>
        <span class="row"><button class="btn" data-act="month" data-d="-1" aria-label="${esc(t("Previous month", "Voriger Monat"))}">‹</button><button class="btn" data-act="month" data-d="0">${esc(t("Today", "Heute"))}</button><button class="btn" data-act="month" data-d="1" aria-label="${esc(t("Next month", "Nächster Monat"))}">›</button></span></div>
      <div class="legend"><span>${icon("mdi:calendar-star", 14)} ${esc(t("from a calendar", "aus einem Kalender"))}</span><span>${icon("mdi:calendar-edit", 14)} ${esc(t("adjusted", "angepasst"))}</span></div>
      <div class="month">${heads}${cells}</div></section>
      <section class="sec" id="dayEditor"></section></div>`;
    this._renderDayEditor();
  }

  async _selectDay(day) {
    this._selDay = day;
    this._dayPlan = null;
    this.shadowRoot.querySelectorAll(".month button.d").forEach((b) => b.classList.toggle("sel", b.dataset.day === day));
    const info = this._month.days.find((d) => d.day === day);
    if (info?.model) {
      try {
        const [plan] = await this._hass.callWS({ type: "cloudless_maestro/preview", entry_id: this._r.entry_id, options: this._r.options, model: info.model, dates: [day] });
        this._dayPlan = plan;
      } catch {
        this._dayPlan = null;
      }
    }
    this._renderDayEditor();
  }

  _renderDayEditor() {
    const box = this.shadowRoot.getElementById("dayEditor");
    if (!box) return;
    const t = this._t;
    const info = this._selDay && this._month?.days.find((d) => d.day === this._selDay);
    if (!info) {
      box.innerHTML = `<p class="note">${esc(t("Choose a date to give it another day model or other times. The change applies only to this date.", "Wähle ein Datum, um ihm ein anderes Tagesmodell oder andere Zeiten zu geben. Die Änderung gilt nur für dieses Datum."))}</p>`;
      return;
    }
    const opts = this._r.options;
    const adj = info.adjustment || {};
    const model = opts.models.find((m) => m.key === info.model);
    const src =
      info.source === "calendar" ? `${t("From the calendar", "Aus dem Kalender")}${info.detail ? `: ${info.detail}` : ""}` : info.source === "adjustment" ? t("Chosen for this date", "Für dieses Datum gewählt") : t("From the week plan", "Aus dem Wochenplan");
    const planned = Object.fromEntries((this._dayPlan?.entries || []).map((e) => [e.key, e.start]));
    const rows = (model?.entries || [])
      .map((e) => {
        const tod = opts.times_of_day.find((x) => x.key === e.tod) || { name: e.tod, color: "#7a8599" };
        const own = adj.times?.[e.tod];
        const value = own?.kind === "fixed" ? own.time : planned[e.tod] ? localParts(this._hass, planned[e.tod]).time : "";
        return `<tr><td><span class="row" style="flex-wrap:nowrap"><span class="swatch" style="background:${esc(tod.color)};color:${inkOn(tod.color)}">${icon(tod.icon, 16)}</span>${esc(tod.name)}</span></td>
          <td><input class="field time" type="time" data-daytime="${esc(e.tod)}" value="${esc(value)}"></td>
          <td>${own ? `<button class="btn" data-act="day-reset" data-key="${esc(e.tod)}">${esc(t("Back to the model", "Zurück zum Modell"))}</button>` : `<span class="note">${planned[e.tod] ? "" : esc(t("does not happen", "fällt aus"))}</span>`}</td></tr>`;
      })
      .join("");
    const endValue = adj.end?.kind === "fixed" ? adj.end.time : this._dayPlan?.end ? localParts(this._hass, this._dayPlan.end).time : "";
    box.innerHTML = `<h2>${esc(fmtDate(this._hass, info.day, { weekday: "long", day: "numeric", month: "long" }))}</h2>
      <div class="row"><label class="row">${esc(t("Day model", "Tagesmodell"))} <select class="field" id="dayModel"><option value="">${esc(t("As planned", "Wie geplant"))}</option>${opts.models.map((m) => `<option value="${esc(m.key)}"${adj.model === m.key ? " selected" : ""}>${esc(m.name)}</option>`).join("")}</select></label><span class="note">${esc(src)}</span></div>
      ${model ? `<div class="wrapx"><table class="tbl"><tbody>${rows}<tr><td><b>${esc(opts.base.name)} ${esc(t("from", "ab"))}</b></td><td><input class="field time" type="time" data-dayend="1" value="${esc(endValue)}"></td><td>${adj.end ? `<button class="btn" data-act="day-reset-end">${esc(t("Back to the model", "Zurück zum Modell"))}</button>` : ""}</td></tr></tbody></table></div>` : ""}
      <p class="note">${esc(t("A time earlier than the first start of the day counts for the following day.", "Eine Uhrzeit vor dem ersten Start des Tages gilt für den Folgetag."))}</p>
      ${info.adjustment ? `<div class="row"><button class="btn" data-act="day-clear">${icon("mdi:calendar-remove", 18)}${esc(t("Remove the adjustment", "Anpassung entfernen"))}</button></div>` : ""}`;
  }

  async _adjust(msg) {
    try {
      await this._hass.callWS({ type: "cloudless_maestro/adjust", entry_id: this._r.entry_id, day: this._selDay, ...msg });
      this._toast(this._t("Saved", "Gespeichert"));
    } catch (err) {
      this._toast(err?.message || String(err));
    }
    const keep = this._selDay;
    this._month = null;
    await this._renderCalendar(this.shadowRoot.getElementById("main"));
    await this._selectDay(keep);
  }

  _dayValue(key, clock) {
    const first = this._dayPlan?.entries?.[0];
    if (!first) return clock;
    const firstLocal = localParts(this._hass, first.start);
    if (key === first.key) return clock;
    const before = key ? minutesOf(clock) < minutesOf(firstLocal.time) : minutesOf(clock) <= minutesOf(firstLocal.time);
    return before ? `${clock}+1` : clock;
  }

  // -- diagnostics ------------------------------------------------------------------------------------

  async _renderDiag(main) {
    const t = this._t;
    main.innerHTML = `<div class="sheet"><p class="note">${esc(t("Loading …", "Wird geladen …"))}</p></div>`;
    try {
      this._diag = await this._hass.callWS({ type: "cloudless_maestro/diagnostics", entry_id: this._r.entry_id });
    } catch (err) {
      main.innerHTML = `<div class="sheet"><div class="notice">${esc(err?.message || String(err))}</div></div>`;
      return;
    }
    const name = (k) => (k ? this._look(k)?.name || k : "—");
    const reasons = { plan: t("plan", "Plan"), pin: t("pinned", "festgesetzt"), resume: t("back to the plan", "zurück zum Plan"), adjustment: t("day adjusted", "Tag angepasst"), calendar: t("calendar", "Kalender"), config: t("settings", "Einstellungen"), restart: t("restart", "Neustart") };
    const until = { next_change: t("until the next change", "bis zum nächsten Wechsel"), duration: t("for a duration", "für eine Dauer"), time: t("until a time", "bis Uhrzeit"), next_day: t("until the next day", "bis zum nächsten Tag"), reset: t("until reset", "bis zurückgesetzt") };
    const text = (item) => {
      if (item.kind === "change") return `${name(item.from)} → ${name(item.to)} · ${reasons[item.reason] || item.reason}`;
      if (item.kind === "pin") return `${t("Pinned", "Festgesetzt")}: ${name(item.to)}, ${until[item.mode] || item.mode}${item.until ? ` (${fmtTime(this._hass, item.until)})` : ""}`;
      if (item.kind === "resume") return t("Back to the plan", "Zurück zum Plan");
      if (item.kind === "pin_ended") return t("The pin ended", "Die Festsetzung ist abgelaufen");
      if (item.kind === "adjust") return `${item.adjustment ? t("Day adjusted", "Tag angepasst") : t("Day adjustment removed", "Tagesanpassung entfernt")}: ${fmtDate(this._hass, item.day)}`;
      if (item.kind === "calendar_error") return `${t("Calendar not readable", "Kalender nicht lesbar")}: ${item.calendar} · ${item.error}`;
      return item.kind;
    };
    const rows = this._diag.log
      .map((item) => `<tr><td class="res">${esc(fmtDate(this._hass, item.at, { day: "numeric", month: "short" }))} ${esc(fmtTime(this._hass, item.at))}</td><td>${esc(text(item))}</td></tr>`)
      .join("");
    const cals = Object.entries(this._diag.calendars)
      .map(([cal, s]) => `<div class="fact"><h3>${esc(this._hass.states[cal]?.attributes?.friendly_name || cal)}</h3><b>${s.error ? `<span class="pill warn">${esc(t("not readable", "nicht lesbar"))}</span>` : `<span class="pill ok">${esc(t("read", "gelesen"))}</span>`}</b><p class="note">${esc(s.fetched ? `${s.events} ${t("events", "Termine")} · ${fmtDate(this._hass, s.fetched, { day: "numeric", month: "short" })} ${fmtTime(this._hass, s.fetched)}` : "")}${s.error ? ` ${esc(s.error)}` : ""}</p></div>`)
      .join("");
    main.innerHTML = `<div class="sheet">
      <section class="sec"><h2>${esc(t("What happened", "Was passiert ist"))}</h2>
        <p class="note">${esc(t("The latest changes and decisions, newest first, to answer “Why is it evening already?”.", "Die letzten Wechsel und Entscheidungen, neueste zuerst, damit sich „Warum ist schon Abend?“ beantworten lässt."))}</p>
        ${rows ? `<div class="wrapx"><table class="tbl"><tbody>${rows}</tbody></table></div>` : `<p class="note">${esc(t("Nothing yet.", "Noch nichts."))}</p>`}</section>
      ${cals ? `<section class="sec"><h2>${esc(t("Calendars", "Kalender"))}</h2><div class="facts">${cals}</div></section>` : ""}</div>`;
  }

  // -- events -----------------------------------------------------------------------------------------

  async _onClick(e) {
    const el = e.target.closest("[data-act]");
    if (!el || el.disabled) return;
    const act = el.dataset.act;
    const t = this._t;
    const w = this._w;
    if (act === "menu") {
      this.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }));
    } else if (act === "tab") {
      this._view = el.dataset.v;
      this._month = null;
      this._render();
    } else if (act === "pick") {
      this._i = Number(el.dataset.i);
      this._resetSelection();
      this._render();
    } else if (act === "create") {
      const input = this.shadowRoot.getElementById("newName");
      const title = input.value.trim();
      if (!title) return input.focus();
      try {
        const res = await this._hass.callWS({ type: "cloudless_maestro/rhythm/create", title, template: this.shadowRoot.getElementById("newTemplate").value });
        await this._load(res.entry_id);
      } catch (err) {
        this._toast(err?.message || String(err));
      }
    } else if (act === "confirm") {
      this._confirm = el.dataset.v || null;
      this._renderMain();
    } else if (act === "delete-rhythm") {
      await this._hass.callWS({ type: "cloudless_maestro/rhythm/delete", entry_id: this._r.entry_id });
      this._i = 0;
      await this._load();
    } else if (act === "add-tpl") {
      const tpl = this._templates.filter((x) => !w.times_of_day.some((y) => y.name === x.name))[Number(this.shadowRoot.getElementById("tplSel").value)];
      if (!tpl) return;
      w.times_of_day.push({ ...tpl, key: makeKey(tpl.name, this._usedKeys()) });
      this._changed();
    } else if (act === "add-tod") {
      const input = this.shadowRoot.getElementById("newTod");
      const name = input.value.trim();
      if (!name) return input.focus();
      const from = w.times_of_day.find((x) => x.key === this.shadowRoot.getElementById("newTodFrom").value);
      w.times_of_day.push({
        key: makeKey(name, this._usedKeys()),
        name,
        icon: from?.icon || "mdi:clock-outline",
        color: from?.color || "#7a8599",
        transition: from?.transition ?? 60,
      });
      this._changed();
    } else if (act === "delete-tod") {
      const key = el.dataset.key;
      w.times_of_day = w.times_of_day.filter((x) => x.key !== key);
      for (const m of w.models) m.entries = m.entries.filter((x) => x.tod !== key);
      this._confirm = null;
      this._changed();
    } else if (act === "model") {
      this._model = el.dataset.key;
      this._confirm = null;
      this._preview = null;
      this._renderMain();
      this._fetchPreview();
    } else if (act === "add-model") {
      const input = this.shadowRoot.getElementById("newModel");
      const name = input.value.trim();
      if (!name) return input.focus();
      const key = makeKey(name, w.models.map((m) => m.key));
      w.models.push({ key, name, entries: w.times_of_day.slice(0, 1).map((x) => ({ tod: x.key, at: { kind: "fixed", time: "08:00", next_day: false } })), end: { kind: "fixed", time: "22:00", next_day: false } });
      this._model = key;
      this._changed();
    } else if (act === "copy-model") {
      const model = this._currentModel();
      const name = `${model.name} ${t("copy", "Kopie")}`;
      const key = makeKey(name, w.models.map((m) => m.key));
      w.models.push({ ...clone(model), key, name });
      this._model = key;
      this._changed();
    } else if (act === "delete-model") {
      w.models = w.models.filter((m) => m.key !== this._model);
      this._model = w.models[0]?.key || null;
      this._confirm = null;
      this._changed();
    } else if (act === "add-entry") {
      const model = this._currentModel();
      const key = this.shadowRoot.getElementById("addEntry").value;
      const last = model.entries.at(-1);
      const time = last?.at.kind === "fixed" ? clockOf(minutesOf(last.at.time) + 60) : "12:00";
      model.entries.push({ tod: key, at: { kind: "fixed", time, next_day: !!last?.at.next_day } });
      this._changed();
    } else if (act === "remove-entry") {
      this._currentModel().entries.splice(Number(el.dataset.i), 1);
      this._changed();
    } else if (act === "move") {
      const list = this._currentModel().entries;
      const i = Number(el.dataset.i),
        j = i + Number(el.dataset.d);
      [list[i], list[j]] = [list[j], list[i]];
      this._changed();
    } else if (act === "preview-today") {
      this._previewDate = localParts(this._hass, new Date().toISOString()).date;
      this._renderMain();
      this._fetchPreview();
    } else if (act === "add-link") {
      const cal = Object.keys(this._hass.states).find((x) => x.startsWith("calendar."));
      w.calendar_links.push({ calendar: cal, match: "", model: w.models[w.models.length - 1]?.key || w.models[0]?.key });
      this._changed({ preview: false });
    } else if (act === "remove-link") {
      w.calendar_links.splice(Number(el.dataset.i), 1);
      this._changed({ preview: false });
    } else if (act === "move-link") {
      const list = w.calendar_links;
      const i = Number(el.dataset.i),
        j = i + Number(el.dataset.d);
      [list[i], list[j]] = [list[j], list[i]];
      this._changed({ preview: false });
    } else if (act === "refresh-cal") {
      try {
        await this._hass.callWS({ type: "cloudless_maestro/refresh_calendars", entry_id: this._r.entry_id });
        this._toast(t("Calendars read", "Kalender gelesen"));
      } catch (err) {
        this._toast(err?.message || String(err));
      }
    } else if (act === "month") {
      const d = Number(el.dataset.d);
      const today = localParts(this._hass, new Date().toISOString()).date;
      if (!d) this._monthStart = `${today.slice(0, 7)}-01`;
      else {
        const [y, m] = this._monthStart.split("-").map(Number);
        const next = new Date(Date.UTC(y, m - 1 + d, 1));
        this._monthStart = next.toISOString().slice(0, 10);
      }
      this._selDay = null;
      this._renderCalendar(this.shadowRoot.getElementById("main"));
    } else if (act === "day") {
      this._selectDay(el.dataset.day);
    } else if (act === "day-reset") {
      this._adjust({ clear_times: [el.dataset.key] });
    } else if (act === "day-reset-end") {
      this._adjust({ clear_end: true });
    } else if (act === "day-clear") {
      try {
        await this._hass.callWS({ type: "cloudless_maestro/clear_day", entry_id: this._r.entry_id, day: this._selDay });
      } catch (err) {
        this._toast(err?.message || String(err));
      }
      const keep = this._selDay;
      this._month = null;
      await this._renderCalendar(this.shadowRoot.getElementById("main"));
      await this._selectDay(keep);
    }
  }

  _setSpec(spec, field, el) {
    if (field === "kind") {
      if (el.value === spec.kind) return spec;
      if (el.value === "sun") return { kind: "sun", event: "sunset", offset: 0, earliest: null, latest: null, next_day: false };
      return { kind: "fixed", time: spec.latest || spec.earliest || "12:00", next_day: !!spec.next_day };
    }
    const next = { ...spec };
    if (field === "next_day") next.next_day = el.checked;
    else if (field === "offset") next.offset = Math.round(Number(el.value) || 0);
    else if (field === "earliest" || field === "latest") next[field] = el.value || null;
    else next[field] = el.value;
    return next;
  }

  _onChange(e) {
    const el = e.target;
    const w = this._w;
    if (!w) return;
    if (el.id === "title") {
      const title = el.value.trim();
      if (!title) return;
      this._r.title = title;
      const btn = this.shadowRoot.querySelector(`.rlist button[data-i="${this._i}"]`);
      if (btn) btn.textContent = title;
      this._changed({ render: false, preview: false });
    } else if (el.dataset.base) {
      const field = el.dataset.base;
      if (field === "name" && !el.value.trim()) return;
      w.base[field] = field === "name" ? el.value.trim() : el.value;
      this._changed({ preview: false, render: field !== "name" });
    } else if (el.id === "locHa") {
      w.location = el.checked ? null : { latitude: this._hass.config.latitude, longitude: this._hass.config.longitude };
      this._changed();
    } else if (el.id === "lat" || el.id === "lon") {
      w.location = { latitude: Number(this.shadowRoot.getElementById("lat").value), longitude: Number(this.shadowRoot.getElementById("lon").value) };
      this._changed({ render: false });
    } else if (el.dataset.tod !== undefined) {
      const tod = w.times_of_day[Number(el.dataset.tod)];
      const field = el.dataset.field;
      if (field === "name" && !el.value.trim()) return;
      tod[field] = field === "transition" ? Math.round(Number(el.value) || 0) : field === "name" ? el.value.trim() : el.value;
      this._changed({ preview: false, render: field !== "name" });
    } else if (el.id === "modelName") {
      const model = this._currentModel();
      if (!el.value.trim()) return;
      model.name = el.value.trim();
      this._changed({ preview: false });
    } else if (el.dataset.entry !== undefined) {
      const model = this._currentModel();
      const ref = el.dataset.entry;
      if (ref === "end") {
        model.end = this._setSpec(model.end, el.dataset.field, el);
        if (model.end.kind === "sun" && !model.end.latest) model.end.latest = "23:30";
      } else {
        const entry = model.entries[Number(ref)];
        entry.at = this._setSpec(entry.at, el.dataset.field, el);
      }
      this._changed({ render: el.dataset.field === "kind" });
    } else if (el.id === "previewDate") {
      if (!el.value) return;
      this._previewDate = el.value;
      this._renderMain();
      this._fetchPreview();
    } else if (el.dataset.week) {
      w.week[el.dataset.week] = el.value || null;
      this._changed({ render: false, preview: false });
    } else if (el.dataset.link !== undefined) {
      w.calendar_links[Number(el.dataset.link)][el.dataset.field] = el.dataset.field === "match" ? el.value.trim() : el.value;
      this._changed({ render: false, preview: false });
    } else if (el.id === "dayModel") {
      this._adjust(el.value ? { model: el.value } : { clear_model: true });
    } else if (el.dataset.daytime) {
      if (!el.value) return;
      this._adjust({ times: { [el.dataset.daytime]: this._dayValue(el.dataset.daytime, el.value) } });
    } else if (el.dataset.dayend) {
      if (!el.value) return;
      this._adjust({ end: this._dayValue("", el.value) });
    }
  }

  _onInput(e) {
    const el = e.target;
    // A name shows in the table header and elsewhere only after leaving the field, so typing keeps its focus.
    if (el.dataset.field === "icon" || el.dataset.base === "icon") {
      const swatch = el.closest("tr")?.querySelector(".swatch ha-icon");
      if (swatch) swatch.setAttribute("icon", el.value);
    }
  }

  // -- dragging fixed times on the axis ---------------------------------------------------------------

  _axisMinute(clientX) {
    const bar = this.shadowRoot.querySelector("#axis .bar");
    const rect = bar.getBoundingClientRect();
    const m = ((clientX - rect.left) / rect.width) * AXIS_MAX;
    return clamp(Math.round(m / 5) * 5, AXIS_MIN, AXIS_MAX - 5);
  }

  _onDown(e) {
    const handle = e.target.closest("[data-handle]");
    if (!handle || handle.classList.contains("sun")) return;
    const key = handle.dataset.handle;
    this._drag = { key, m: this._axisMinute(e.clientX), pointer: e.pointerId };
    handle.setPointerCapture?.(e.pointerId);
    e.preventDefault();
    this._renderAxis();
  }

  _onMove(e) {
    if (!this._drag || e.pointerId !== this._drag.pointer) return;
    const m = this._axisMinute(e.clientX);
    if (m !== this._drag.m) {
      this._drag.m = m;
      this._renderAxis();
    }
  }

  _onUp(e) {
    if (!this._drag || e.pointerId !== this._drag.pointer) return;
    const { key, m } = this._drag;
    this._drag = null;
    const model = this._currentModel();
    const spec = { kind: "fixed", time: clockOf(m), next_day: m >= 1440 };
    if (key) {
      const entry = model.entries.find((x) => x.tod === key);
      if (entry) entry.at = spec;
    } else model.end = spec;
    this._changed();
  }
}

if (!customElements.get("maestro-panel")) customElements.define("maestro-panel", MaestroPanel);
