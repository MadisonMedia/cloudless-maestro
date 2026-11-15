// The Maestro page in the sidebar: times of day, day models, the week plan, rules, the calendar and diagnostics.

const shared = await import(new URL(`./maestro-shared.js${new URL(import.meta.url).search}`, import.meta.url).href);
const {
  PALETTES,
  addDays,
  areaOf,
  clamp,
  clockOf,
  esc,
  fmtDate,
  fmtTime,
  friendly,
  hueRgb,
  icon,
  inkOn,
  isDark,
  kelvinColor,
  langOf,
  loadIconPicker,
  localParts,
  makeKey,
  minutesOf,
  paletteOf,
  rgbHue,
  tr,
} = shared;

const STYLE = `
:host { display: block; min-height: 100%; background: var(--primary-background-color, #eef1f5); color: var(--ink); font: 400 15px/1.45 var(--paper-font-body1_-_font-family, var(--ha-font-family-body, system-ui, sans-serif));
  --ink: var(--primary-text-color, #171d2d); --muted: var(--secondary-text-color, #566077); --surface: var(--card-background-color, #fff); --field: var(--card-background-color, #fff); --line: var(--divider-color, #d4dae6); --accent: var(--primary-color, #2f5fd0); --accent-ink: var(--text-primary-color, #fff);
  --accent-soft: color-mix(in srgb, var(--accent) 14%, transparent); --well: color-mix(in srgb, var(--ink) 8%, var(--surface)); --bg: var(--primary-background-color, #eef1f5);
  --warn: #8a5300; --warn-soft: #fbeed6; --good: #1f6f47; --good-soft: #dcf1e5; --code: #11152a; --code-ink: #dfe4f2; }
:host([dark]) { --warn: #f0bd6a; --warn-soft: #3a2b12; --good: #7fd6a6; --good-soft: #15352a; --code: #0d1020; }
* { box-sizing: border-box; }
[hidden] { display: none !important; }
h1, h2, h3, p { margin: 0; }
button, input, select { font: inherit; color: inherit; }
button { cursor: pointer; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.shell { container-type: inline-size; max-width: 1280px; margin: 0 auto; padding-block: 14px 96px; padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); display: grid; gap: 14px; }
.top { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 16px; }
.menu { border: 0; background: transparent; width: 36px; height: 36px; border-radius: 50%; display: grid; place-items: center; padding: 0; }
.mark { font-size: 22px; font-weight: 750; letter-spacing: -.01em; }
.tabs { display: inline-flex; gap: 2px; padding: 3px; background: var(--well); border-radius: 10px; }
.tabs button { border: 0; background: transparent; padding: 6px 14px; border-radius: 8px; font-weight: 500; color: var(--muted); }
.tabs button[aria-selected="true"] { background: var(--surface); color: var(--ink); font-weight: 600; box-shadow: 0 1px 2px rgba(0,0,0,.08); }
.layout { display: grid; grid-template-columns: 180px minmax(0, 1fr); gap: 20px; align-items: start; }
.jump { position: sticky; top: 12px; display: grid; gap: 2px; align-content: start; }
.jump a { text-decoration: none; color: var(--muted); padding: 7px 10px; border-left: 2px solid transparent; border-radius: 0 8px 8px 0; font-size: 14.5px; }
.jump a.on { color: var(--ink); font-weight: 600; border-left-color: var(--accent); background: var(--accent-soft); }
.jump a:hover { color: var(--ink); }
.sheet { background: var(--surface); border: 1px solid var(--line); border-radius: 14px; padding: 20px; display: grid; grid-template-columns: minmax(0, 1fr); gap: 34px; min-width: 0; }
.sheet > *, .sec > *, .rule, .rule .body > *, .rule .body > * > * { min-width: 0; }
.sec { display: grid; grid-template-columns: minmax(0, 1fr); gap: 12px; scroll-margin-top: 12px; }
.hrow { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.hrow h2 { font-size: 19px; font-weight: 700; letter-spacing: -.005em; }
.sub { font-size: 15px; font-weight: 600; }
.info { border: 1px solid var(--line); background: transparent; color: var(--muted); width: 20px; height: 20px; border-radius: 50%; padding: 0; font: italic 600 12px/1 Georgia, "Times New Roman", serif; display: inline-grid; place-items: center; flex: none; }
.info[aria-expanded="true"] { background: var(--accent-soft); border-color: var(--accent); color: var(--accent); }
.note { font-size: 13.5px; color: var(--muted); max-width: 78ch; }
.row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.row.space { justify-content: space-between; }
.grow { flex: 1 1 auto; }
.field { background: var(--field); border: 1px solid var(--line); border-radius: 8px; min-height: 36px; padding: 5px 9px; max-width: 100%; }
.field.title { font-size: 21px; font-weight: 600; width: min(100%, 340px); }
input.num { width: 72px; font-variant-numeric: tabular-nums; }
input.time { width: 104px; font-variant-numeric: tabular-nums; }
.field.quiet { border-color: transparent; background: transparent; padding-left: 4px; font-weight: 600; }
.field.quiet:hover, .field.quiet:focus { border-color: var(--line); background: var(--field); }
.btn { border: 1px solid var(--line); background: var(--field); border-radius: 8px; min-height: 36px; padding: 5px 12px; font-weight: 500; display: inline-flex; gap: 6px; align-items: center; white-space: nowrap; }
.btn:hover { border-color: var(--accent); }
.btn:disabled { opacity: .5; cursor: not-allowed; }
.btn.primary { background: var(--accent); border-color: var(--accent); color: var(--accent-ink); font-weight: 600; }
.btn.danger { color: var(--warn); }
.btn.sm { min-height: 30px; padding: 3px 10px; font-size: 13.5px; }
.link { border: 0; background: transparent; color: var(--muted); padding: 6px 4px; font-weight: 500; text-align: left; }
.link:hover { color: var(--accent); }
.more { border: 0; background: transparent; color: var(--muted); font-size: 13px; padding: 4px 6px; white-space: nowrap; }
.more::after { content: " ▸"; }
.more[aria-expanded="true"]::after { content: " ▾"; }
.more:hover { color: var(--ink); }
.x { border: 0; background: transparent; color: var(--muted); width: 28px; height: 28px; border-radius: 6px; font-size: 17px; line-height: 1; flex: none; padding: 0; display: inline-grid; place-items: center; }
.x:hover { background: var(--well); color: var(--ink); }
.x:disabled { opacity: .3; cursor: default; }
.key { font: 500 12px/1 ui-monospace, Menlo, monospace; color: var(--muted); background: var(--well); padding: 3px 6px; border-radius: 5px; white-space: nowrap; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.chip { border: 1px solid var(--line); background: transparent; color: var(--muted); border-radius: 999px; padding: 4px 11px; font-size: 13px; display: inline-flex; align-items: center; gap: 5px; }
.chip:hover { color: var(--ink); border-color: var(--accent); }
.pill { display: inline-block; padding: 2px 9px; border-radius: 99px; font-size: 12.5px; white-space: nowrap; }
.pill.ok { background: var(--good-soft); color: var(--good); }
.pill.warn { background: var(--warn-soft); color: var(--warn); }
.pill.soft { background: var(--accent-soft); color: var(--ink); }
.notice { padding: 9px 12px; border-radius: 9px; background: var(--warn-soft); color: var(--warn); font-size: 13.5px; }
.notice.calm { background: var(--accent-soft); color: var(--ink); }
.rows { display: grid; }
.r { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 10px 12px; padding: 8px 4px; border-bottom: 1px solid var(--line); }
.r:last-child { border-bottom: 0; }
.r .meta { font-size: 13px; color: var(--muted); }
.r .tools { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
.sub-r { grid-column: 1 / -1; display: grid; gap: 10px; padding: 6px 4px 10px 46px; }
.tile { display: inline-grid; place-items: center; width: 34px; height: 34px; border-radius: 9px; flex: none; }
.tile.sm { width: 26px; height: 26px; border-radius: 7px; }
.add { display: flex; flex-wrap: wrap; gap: 6px 12px; align-items: center; padding: 8px 4px; }
.add .tpl { font-size: 13px; color: var(--muted); }
.wrapx { overflow-x: auto; border: 1px solid var(--line); border-radius: 10px; }
table { border-collapse: separate; border-spacing: 0; width: 100%; }
.tbl th { font-size: 12.5px; font-weight: 500; color: var(--muted); text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line); white-space: nowrap; }
.tbl td { padding: 6px 10px; border-bottom: 1px solid var(--line); vertical-align: middle; }
.tbl tr:last-child td { border-bottom: 0; }
.tbl td.res { font-variant-numeric: tabular-nums; white-space: nowrap; font-size: 13.5px; }
.tbl td.res.off { color: var(--warn); }
.tbl tr.open > td { background: color-mix(in srgb, var(--accent-soft) 45%, transparent); }
.tbl tr.detail td { background: color-mix(in srgb, var(--accent-soft) 45%, transparent); padding: 4px 10px 12px 56px; }
.tbl tr.base td { background: color-mix(in srgb, var(--well) 60%, transparent); }
.tbl select.field { max-width: 230px; }
.cell { display: flex; align-items: center; gap: 8px; white-space: nowrap; }
.cell b { font-weight: 600; }
.opt { display: inline-flex; gap: 6px; align-items: center; font-size: 13px; color: var(--muted); white-space: nowrap; }
.spec { display: inline-flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.spec .sum { font-size: 13.5px; color: var(--muted); }
.detail-grid { display: flex; flex-wrap: wrap; gap: 10px 22px; align-items: center; }
.detail-grid label { display: inline-flex; align-items: center; gap: 6px; font-size: 13.5px; color: var(--muted); }
.detail-grid label input.field, .detail-grid label select.field { color: var(--ink); }
.strip { display: flex; gap: 2px; height: 6px; }
.strip i { display: block; height: 100%; border-radius: 3px; min-width: 3px; }
.pal { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.pal button, .pal .own { width: 26px; height: 26px; border-radius: 50%; border: 2px solid transparent; padding: 0; box-shadow: 0 0 0 1px color-mix(in srgb, var(--ink) 15%, transparent) inset; background-clip: padding-box; }
.pal button[aria-pressed="true"] { border-color: var(--ink); }
.pal .own { position: relative; overflow: hidden; background: conic-gradient(#f44336, #ffc107, #4caf50, #03a9f4, #673ab7, #f44336); cursor: pointer; }
.pal .own input { position: absolute; inset: -10px; opacity: 0; cursor: pointer; }
.mchip { border: 1px solid var(--line); background: transparent; border-radius: 10px; padding: 6px 12px 7px; display: grid; gap: 5px; min-width: 120px; text-align: left; font-weight: 500; }
.mchip[aria-pressed="true"] { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent) inset; font-weight: 600; }
.mchip.new { display: grid; place-items: center; color: var(--muted); border-style: dashed; min-height: 56px; }
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
.axis .tip { position: absolute; top: 50px; z-index: 1; transform: translateX(-50%); font-size: 11.5px; font-weight: 600; background: var(--surface); border: 1px solid var(--line); padding: 0 5px; border-radius: 5px; white-space: nowrap; font-variant-numeric: tabular-nums; }
.week { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 8px; }
.week .d { display: grid; gap: 6px; padding: 8px; border: 1px solid var(--line); border-radius: 10px; font-size: 13px; color: var(--muted); min-width: 0; }
.week .d b { color: var(--ink); font-size: 13px; }
.week .d select { width: 100%; min-height: 32px; padding: 3px 6px; font-size: 13.5px; }
.rule { border: 1px solid var(--line); border-radius: 12px; overflow: hidden; }
.rule > .head { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 14px; padding: 10px 14px; cursor: pointer; }
.rule > .head:hover { background: color-mix(in srgb, var(--well) 50%, transparent); }
.rule > .head .name { font-weight: 600; font-size: 16px; }
.rule > .head .sum { font-size: 13px; color: var(--muted); }
.rule .body { border-top: 1px solid var(--line); padding: 14px; display: grid; gap: 18px; }
.switch { display: inline-flex; align-items: center; gap: 8px; font-size: 13.5px; color: var(--muted); }
.switch input { appearance: none; width: 36px; height: 20px; border-radius: 10px; background: var(--line); position: relative; margin: 0; cursor: pointer; }
.switch input::after { content: ""; position: absolute; top: 2px; left: 2px; width: 16px; height: 16px; border-radius: 50%; background: var(--surface); transition: left .15s; }
.switch input:checked { background: var(--accent); }
.switch input:checked::after { left: 18px; }
.light { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 12px; padding: 6px 4px; border-bottom: 1px solid var(--line); }
.light:last-of-type { border-bottom: 0; }
.light .kind { font-size: 12.5px; color: var(--muted); }
.light .state { margin-left: auto; font-size: 12.5px; color: var(--muted); }
.trig { display: grid; grid-template-columns: 170px minmax(0, 1fr); gap: 10px 14px; align-items: center; }
.trig .lbl { font-size: 13.5px; color: var(--muted); }
.tag { display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--line); border-radius: 8px; padding: 4px 8px; font-size: 13.5px; background: var(--field); }
.tag .x { width: 20px; height: 20px; font-size: 14px; }
.swatchbtn { border: 1px solid var(--line); border-radius: 8px; background: var(--field); padding: 3px 8px 3px 4px; display: inline-flex; align-items: center; gap: 6px; font-size: 13.5px; font-variant-numeric: tabular-nums; }
.swatchbtn i { width: 18px; height: 18px; border-radius: 5px; display: inline-block; }
.bar-k, .bar-h { -webkit-appearance: none; appearance: none; width: min(100%, 300px); height: 14px; border-radius: 7px; outline-offset: 4px; }
.bar-k { background: linear-gradient(90deg, #ff9d3c, #ffd2a1, #fff6ea, #d9ecff, #bcd8ff); }
.bar-h { background: linear-gradient(90deg, #f00, #ff0, #0f0, #0ff, #00f, #f0f, #f00); }
.bar-k::-webkit-slider-thumb, .bar-h::-webkit-slider-thumb { -webkit-appearance: none; width: 18px; height: 22px; border-radius: 6px; background: var(--surface); border: 2px solid var(--ink); }
.bar-k::-moz-range-thumb, .bar-h::-moz-range-thumb { width: 14px; height: 18px; border-radius: 6px; background: var(--surface); border: 2px solid var(--ink); }
.presets { display: inline-flex; gap: 4px; }
.presets button { border: 1px solid var(--line); background: transparent; border-radius: 6px; padding: 2px 7px; font-size: 12px; color: var(--muted); }
.presets button:hover { color: var(--ink); border-color: var(--accent); }
.pick { border: 1px solid var(--line); border-radius: 10px; padding: 10px; display: grid; gap: 8px; background: color-mix(in srgb, var(--well) 40%, transparent); }
.picklist { display: grid; max-height: 280px; overflow: auto; border-top: 1px solid var(--line); }
.picklist button { border: 0; border-bottom: 1px solid var(--line); background: transparent; text-align: left; padding: 7px 8px; display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 2px 10px; align-items: center; }
.picklist button:hover { background: var(--accent-soft); }
.picklist .pname { font-weight: 500; }
.picklist .pmeta { font-size: 12px; color: var(--muted); grid-column: 1; }
.picklist .pstate { font-size: 12px; color: var(--muted); grid-row: 1 / span 2; }
.facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; }
.fact { border: 1px solid var(--line); border-radius: 12px; padding: 12px 14px; display: grid; gap: 4px; }
.fact h3 { font-size: 13px; font-weight: 500; color: var(--muted); }
.fact b { font-size: 18px; font-weight: 600; display: flex; align-items: center; gap: 8px; }
.fact .meta { font-size: 13px; color: var(--muted); }
.month { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 4px; }
.month .wd { font-size: 12px; color: var(--muted); text-align: center; padding: 2px 0; }
.month button.d { min-height: 68px; border: 1px solid var(--line); background: var(--field); border-radius: 9px; padding: 6px 7px 7px; text-align: left; display: grid; align-content: space-between; gap: 6px; min-width: 0; }
.month button.d.other { opacity: .45; }
.month button.d.today { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent) inset; }
.month button.d.sel { background: var(--accent-soft); }
.month .n { font-size: 12.5px; font-weight: 650; display: flex; justify-content: space-between; align-items: center; gap: 4px; }
.month .mn { font-size: 12px; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex: none; }
.legend { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 13px; color: var(--muted); }
.legend span { display: inline-flex; gap: 6px; align-items: center; }
.log td:first-child { color: var(--muted); font-variant-numeric: tabular-nums; white-space: nowrap; width: 1%; font-size: 13.5px; }
pre { margin: 0; padding: 12px 14px; font: 400 12.5px/1.55 ui-monospace, Menlo, monospace; background: var(--code); color: var(--code-ink); border-radius: 10px; overflow-x: auto; }
details > summary { cursor: pointer; font-weight: 600; font-size: 15px; }
.livebar { position: fixed; left: 0; right: 0; bottom: 0; z-index: 5; padding: 8px max(16px, env(safe-area-inset-right, 0px)) calc(8px + env(safe-area-inset-bottom, 0px)) max(16px, env(safe-area-inset-left, 0px)); pointer-events: none; }
.livebar .in { pointer-events: auto; max-width: 1248px; margin: 0 auto; background: var(--surface); border: 1px solid var(--line); border-radius: 12px; box-shadow: 0 6px 24px rgba(0,0,0,.12); padding: 8px 12px; display: flex; flex-wrap: wrap; align-items: center; gap: 8px 18px; }
.livebar .now { display: flex; align-items: center; gap: 10px; font-size: 14px; }
.livebar .now b { font-weight: 600; }
.livebar .now .meta { color: var(--muted); }
.toast { position: fixed; left: 50%; transform: translateX(-50%); bottom: calc(72px + env(safe-area-inset-bottom, 0px)); z-index: 20; max-width: calc(100vw - 32px); padding: 9px 14px; border-radius: 10px; background: var(--ink); color: var(--surface); font-size: 14px; box-shadow: 0 6px 24px rgba(0,0,0,.2); }
.scrim { padding: 10px 12px; border: 1px solid var(--line); border-radius: 10px; font-size: 13px; color: var(--muted); }
ha-icon-picker { width: min(100%, 320px); }
@container (max-width: 900px) {
  .layout { grid-template-columns: minmax(0, 1fr); }
  .jump { position: sticky; top: 0; z-index: 6; display: flex; flex-wrap: wrap; gap: 2px 4px; padding: 6px 0; background: var(--bg); }
  .jump a { border-left: 0; border-bottom: 2px solid transparent; border-radius: 8px 8px 0 0; padding: 5px 8px; font-size: 13.5px; }
  .jump a.on { border-bottom-color: var(--accent); background: transparent; }
  .sheet { padding: 14px; gap: 28px; }
  .trig { grid-template-columns: minmax(0, 1fr); }
  .week { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  .sub-r { padding-left: 4px; }
  .tbl tr.detail td { padding-left: 10px; }
}
@container (max-width: 560px) {
  .week { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .month button.d { min-height: 54px; }
  .month .mn { display: none; }
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
const DEVICE_DOMAINS = ["cover", "climate", "media_player", "fan", "switch", "input_boolean", "number", "input_number", "scene", "script"];
const DEVICE_UNITS = { cover: "%", climate: "°", media_player: "%", fan: "%", number: "", input_number: "" };
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
    this._strips = {};
    this._month = null;
    this._monthStart = null;
    this._selDay = null;
    this._dayPlan = null;
    this._diag = null;
    this._templates = [];
    this._confirm = null;
    this._error = null;
    this._drag = null;
    this._infos = new Set();
    this._open = new Set();
    this._undo = [];
    this._snap = null;
    this._pick = null;
    this._pickQuery = "";
    this._creating = false;
    this._import = null;
    this._sidebar = true;
    this._check = null;
    const r = this.shadowRoot;
    r.addEventListener("click", (e) => this._onClick(e));
    r.addEventListener("change", (e) => this._onChange(e));
    r.addEventListener("input", (e) => this._onInput(e));
    r.addEventListener("value-changed", (e) => this._onPicker(e));
    r.addEventListener("pointerdown", (e) => this._onDown(e));
    r.addEventListener("pointermove", (e) => this._onMove(e));
    r.addEventListener("pointerup", (e) => this._onUp(e));
    r.addEventListener("pointercancel", () => {
      this._drag = null;
      this._renderAxis();
    });
    this._onScroll = () => this._markJump();
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
    for (const name of ["hass", "narrow", "panel", "route"]) {
      if (Object.hasOwn(this, name)) {
        const value = this[name];
        delete this[name];
        this[name] = value;
      }
    }
    window.addEventListener("scroll", this._onScroll, { passive: true });
  }

  disconnectedCallback() {
    window.removeEventListener("scroll", this._onScroll);
    this._unsubscribe();
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

  // -- loading and live state -------------------------------------------------------------------------

  async _load(select) {
    const list = await this._hass.callWS({ type: "cloudless_maestro/rhythms" });
    this._rhythms = list.map((r) => ({ ...r, work: clone(r.options) }));
    if (select) this._i = Math.max(0, this._rhythms.findIndex((r) => r.entry_id === select));
    this._i = Math.min(this._i, Math.max(0, this._rhythms.length - 1));
    try {
      this._sidebar = (await this._hass.callWS({ type: "cloudless_maestro/sidebar" })).sidebar;
    } catch {
      this._sidebar = true;
    }
    await this._loadTemplates();
    this._resetSelection();
    this._render();
    this._subscribe();
  }

  async _loadTemplates() {
    try {
      this._templates = await this._hass.callWS({ type: "cloudless_maestro/templates", language: langOf(this._hass), palette: paletteOf(this._w) });
    } catch {
      this._templates = [];
    }
  }

  _resetSelection() {
    this._model = this._w?.models[0]?.key || null;
    this._previewDate = localParts(this._hass, new Date().toISOString()).date;
    this._preview = null;
    this._strips = {};
    this._month = null;
    this._monthStart = null;
    this._selDay = null;
    this._dayPlan = null;
    this._diag = null;
    this._confirm = null;
    this._error = null;
    this._undo = [];
    this._pick = null;
    this._import = null;
    this._creating = false;
    this._open = new Set();
    if (this._r) {
      this._fetchPreview();
      this._fetchStrips();
    }
  }

  async _subscribe() {
    this._unsubscribe();
    const r = this._r;
    if (!r) return;
    try {
      this._unsub = await this._hass.connection.subscribeMessage(
        (snap) => {
          this._snap = snap;
          this._renderLive();
        },
        { type: "cloudless_maestro/subscribe", entry_id: r.entry_id },
      );
    } catch {
      this._snap = null;
    }
  }

  _unsubscribe() {
    if (this._unsub) {
      const unsub = this._unsub;
      this._unsub = null;
      Promise.resolve(unsub).then((f) => typeof f === "function" && f()).catch(() => {});
    }
  }

  // -- saving -----------------------------------------------------------------------------------------

  _edit(fn, opts = {}) {
    const w = this._w;
    if (!w) return;
    this._undo.push(JSON.stringify(w));
    if (this._undo.length > 40) this._undo.shift();
    fn(w);
    this._changed(opts);
  }

  _changed({ render = true, preview = true } = {}) {
    clearTimeout(this._saveTimer);
    this._saveTimer = setTimeout(() => this._save(), 500);
    if (preview) {
      clearTimeout(this._previewTimer);
      this._previewTimer = setTimeout(() => {
        this._fetchPreview();
        this._fetchStrips();
      }, 250);
    }
    if (render) this._renderMain();
    else this._renderUndo();
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
    this._toastTimer = setTimeout(() => (el.hidden = true), 1800);
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
      this._preview = await this._hass.callWS({ type: "cloudless_maestro/preview", entry_id: r.entry_id, options: r.work, model: this._model, dates });
    } catch {
      this._preview = null;
    }
    this._renderModelResults();
  }

  // One resolved day per model for the preview date, for the small strips.
  async _fetchStrips() {
    const r = this._r;
    if (!r) return;
    const date = this._previewDate;
    const out = {};
    await Promise.all(
      r.work.models.map(async (m) => {
        try {
          const [plan] = await this._hass.callWS({ type: "cloudless_maestro/preview", entry_id: r.entry_id, options: r.work, model: m.key, dates: [date] });
          out[m.key] = plan;
        } catch {
          out[m.key] = null;
        }
      }),
    );
    this._strips = out;
    this.shadowRoot.querySelectorAll("[data-strip]").forEach((el) => {
      el.innerHTML = this._stripHTML(el.dataset.strip);
    });
  }

  _stripHTML(modelKey, plan = this._strips[modelKey]) {
    if (!plan || !plan.entries?.length || !plan.end) return `<span class="strip"></span>`;
    const t0 = new Date(plan.entries[0].start).getTime(),
      t1 = new Date(plan.end).getTime(),
      span = Math.max(1, t1 - t0);
    return `<span class="strip" aria-hidden="true">${plan.entries
      .map((e, i) => {
        const a = new Date(e.start).getTime(),
          b = i + 1 < plan.entries.length ? new Date(plan.entries[i + 1].start).getTime() : t1;
        return `<i style="flex:${(b - a) / span};background:${esc(this._look(e.key).color)}"></i>`;
      })
      .join("")}</span>`;
  }

  // -- lookups ----------------------------------------------------------------------------------------

  _look(key) {
    const w = this._w;
    if (!w) return { key, name: key, color: "#7a8599" };
    if (key === w.base.key) return w.base;
    return w.times_of_day.find((t) => t.key === key) || { key, name: key, color: "#7a8599" };
  }

  _allTods() {
    const w = this._w;
    return [...w.times_of_day, w.base];
  }

  _usedKeys() {
    const w = this._w;
    return [w.base.key, ...w.times_of_day.map((t) => t.key)];
  }

  _currentModel() {
    return this._w?.models.find((m) => m.key === this._model) || null;
  }

  _rule(id) {
    return this._w?.rules.find((r) => r.id === id) || null;
  }

  _tile(tod, sm = false) {
    return `<span class="tile${sm ? " sm" : ""}" style="background:${esc(tod.color)};color:${inkOn(tod.color)}">${icon(tod.icon, sm ? 15 : 20)}</span>`;
  }

  _info(id) {
    return `<button class="info" data-act="info" data-id="${esc(id)}" aria-expanded="${this._infos.has(id)}" aria-label="${esc(this._t("Explanation", "Erklärung"))}">i</button>`;
  }

  _infoText(id, text) {
    return `<p class="note" ${this._infos.has(id) ? "" : "hidden"}>${esc(text)}</p>`;
  }

  _more(id, label = this._t("More", "Mehr")) {
    return `<button class="more" data-act="more" data-id="${esc(id)}" aria-expanded="${this._open.has(id)}">${esc(label)}</button>`;
  }

  // -- rendering --------------------------------------------------------------------------------------

  _render() {
    const t = this._t;
    this.shadowRoot.innerHTML = `<style>${STYLE}</style><div class="shell">
      <header class="top">
        <button class="menu" data-act="menu" aria-label="Menu" ${this._narrow ? "" : "hidden"}>${MENU_ICON}</button>
        <h1 class="mark">Maestro</h1>
        <select class="field" id="rhythmSel" aria-label="${esc(t("Rhythm", "Rhythmus"))}">${this._rhythms
          .map((r, i) => `<option value="${i}"${i === this._i ? " selected" : ""}>${esc(r.title)}</option>`)
          .join("")}<option value="new">${esc(t("New rhythm …", "Neuer Rhythmus …"))}</option></select>
        <div class="tabs" role="tablist">
          <button role="tab" data-act="tab" data-v="setup" aria-selected="${this._view === "setup"}">${esc(t("Setup", "Einrichtung"))}</button>
          <button role="tab" data-act="tab" data-v="calendar" aria-selected="${this._view === "calendar"}">${esc(t("Calendar", "Kalender"))}</button>
          <button role="tab" data-act="tab" data-v="diag" aria-selected="${this._view === "diag"}">${esc(t("Diagnostics", "Diagnose"))}</button>
        </div>
      </header>
      <div id="main"></div></div>
      <div class="livebar" id="livebar"></div><div class="toast" id="toast" hidden></div>`;
    this._renderMain();
    this._renderLive();
  }

  _renderMain() {
    const main = this.shadowRoot.getElementById("main");
    if (!main) return;
    const t = this._t;
    if (this._creating || !this._r) {
      main.innerHTML = `<div class="sheet">${this._createForm()}</div>`;
      return;
    }
    if (this._view === "calendar") return this._renderCalendar(main);
    if (this._view === "diag") return this._renderDiag(main);
    const sections = [
      ["sec-tods", t("Times of day", "Tageszeiten")],
      ["sec-models", t("Day models", "Tagesmodelle")],
      ["sec-week", t("Week plan", "Wochenplan")],
      ["sec-rules", t("Rules", "Regeln")],
      ["sec-general", t("General", "Allgemein")],
    ];
    main.innerHTML = `<div class="layout"><nav class="jump" id="jump" aria-label="${esc(t("Sections", "Abschnitte"))}">${sections
      .map(([id, label]) => `<a href="#${id}" data-act="jump" data-to="${id}">${esc(label)}</a>`)
      .join("")}</nav>
      <div class="sheet">
        <div class="notice" id="saveError" ${this._error ? "" : "hidden"}>${esc(this._error ? `${t("Not saved", "Nicht gespeichert")}: ${this._error}` : "")}</div>
        ${this._titleRow()}
        ${this._import ? this._importBox() : ""}
        ${this._todSection()}
        ${this._modelSection()}
        ${this._weekSection()}
        ${this._rulesSection()}
        ${this._generalSection()}
      </div></div>`;
    this._renderAxis();
    this._renderModelResults();
    this._mountPickers();
    this._markJump();
  }

  _renderUndo() {
    const btn = this.shadowRoot.getElementById("undoBtn");
    if (btn) btn.disabled = !this._undo.length;
  }

  _renderLive() {
    const bar = this.shadowRoot.getElementById("livebar");
    if (!bar) return;
    const t = this._t;
    const s = this._snap;
    const w = this._w;
    if (!s || !w || this._creating) {
      bar.innerHTML = "";
      return;
    }
    const tod = this._look(s.state.key);
    const next = s.state.next_key ? `${t("then", "dann")} ${this._look(s.state.next_key).name} ${t("at", "um")} ${fmtTime(this._hass, s.state.until)}` : "";
    bar.innerHTML = `<div class="in"><span class="now">${this._tile(tod, true)}<span><b>${esc(tod.name)}</b> <span class="meta">${esc(t("since", "seit"))} ${esc(fmtTime(this._hass, s.state.since))}${next ? ` · ${esc(next)}` : ""}${s.state.pinned ? ` · ${esc(t("pinned", "festgesetzt"))}` : ""}</span></span></span>
      <span class="grow"></span>
      ${this._view === "setup" ? `<label class="opt" style="color:var(--ink)">${esc(t("Preview for", "Vorschau für"))} <input class="field" type="date" id="previewDate" value="${esc(this._previewDate)}" style="min-height:32px"></label><button class="btn sm" data-act="preview-today">${esc(t("Today", "Heute"))}</button>` : ""}</div>`;
  }

  _markJump() {
    const jump = this.shadowRoot.getElementById("jump");
    if (!jump) return;
    const links = [...jump.querySelectorAll("a")];
    let best = links[0];
    for (const a of links) {
      const el = this.shadowRoot.getElementById(a.dataset.to);
      if (el && el.getBoundingClientRect().top <= 140) best = a;
    }
    links.forEach((a) => a.classList.toggle("on", a === best));
  }

  _createForm() {
    const t = this._t;
    return `<section class="sec"><h2>${esc(t("New rhythm", "Neuer Rhythmus"))}</h2>
      <p class="note">${esc(t("A rhythm is one daily schedule, for example for the flat, a terrarium or a child's room.", "Ein Rhythmus ist ein eigener Tagesplan, zum Beispiel für die Wohnung, ein Terrarium oder ein Kinderzimmer."))}</p>
      <div class="row"><input class="field" id="newName" placeholder="${esc(t("Name", "Name"))}" aria-label="${esc(t("Name", "Name"))}" style="width:220px">
        <select class="field" id="newTemplate"><option value="day">${esc(t("A typical day", "Ein typischer Tag"))}</option><option value="empty">${esc(t("One time of day", "Eine Tageszeit"))}</option></select>
        <select class="field" id="newPalette"><option value="ha">${esc(t("Home Assistant's colors", "Farben von Home Assistant"))}</option><option value="earth">${esc(t("Earth tones", "Erdtöne"))}</option></select>
        <button class="btn primary" data-act="create">${esc(t("Create", "Anlegen"))}</button>${this._r ? `<button class="btn" data-act="create-cancel">${esc(t("Cancel", "Abbrechen"))}</button>` : ""}</div></section>`;
  }

  _titleRow() {
    const t = this._t;
    const r = this._r;
    const confirming = this._confirm === "rhythm";
    return `<div class="row space"><input class="field title" id="title" value="${esc(r.title)}" aria-label="${esc(t("Name of the rhythm", "Name des Rhythmus"))}">
      <span class="row"><button class="btn" id="undoBtn" data-act="undo" ${this._undo.length ? "" : "disabled"}>${esc(t("Undo", "Rückgängig"))}</button>
        <button class="btn" data-act="export">${esc(t("Export", "Exportieren"))}</button>
        <button class="btn" data-act="import">${esc(t("Import", "Importieren"))}</button><input type="file" id="importFile" accept="application/json,.json" hidden>
        ${confirming ? `<span class="note">${esc(t("Delete this rhythm with everything in it?", "Diesen Rhythmus mit allem darin löschen?"))}</span><button class="btn danger" data-act="delete-rhythm">${esc(t("Delete", "Löschen"))}</button><button class="btn" data-act="confirm" data-v="">${esc(t("Keep", "Behalten"))}</button>` : `<button class="btn danger" data-act="confirm" data-v="rhythm">${esc(t("Delete rhythm", "Rhythmus löschen"))}</button>`}</span></div>`;
  }

  _importBox() {
    const t = this._t;
    const imp = this._import;
    return `<div class="notice calm"><div class="row space"><span>${esc(t("Import", "Importieren"))}: <b>${esc(imp.title)}</b> · ${imp.options.times_of_day?.length || 0} ${esc(t("times of day", "Tageszeiten"))}, ${imp.options.models?.length || 0} ${esc(t("day models", "Tagesmodelle"))}, ${imp.options.rules?.length || 0} ${esc(t("rules", "Regeln"))}</span>
      <span class="row"><button class="btn" data-act="import-new">${esc(t("As a new rhythm", "Als neuen Rhythmus"))}</button><button class="btn" data-act="import-replace">${esc(t("Replace this rhythm", "Diesen Rhythmus ersetzen"))}</button><button class="btn" data-act="import-cancel">${esc(t("Cancel", "Abbrechen"))}</button></span></div></div>`;
  }

  // -- times of day -----------------------------------------------------------------------------------

  _todRow(tod, base) {
    const t = this._t;
    const w = this._w;
    const id = `tod-${tod.key}`;
    const open = this._open.has(id);
    const confirming = this._confirm === id;
    const used = w.models.filter((m) => m.entries.some((e) => e.tod === tod.key)).map((m) => m.name);
    const ref = base ? "base" : String(w.times_of_day.indexOf(tod));
    const palette = PALETTES[paletteOf(w)];
    const colors = palette.includes(tod.color.toLowerCase()) ? palette : [...palette.slice(0, 11), tod.color];
    const picker = customElements.get("ha-icon-picker")
      ? `<ha-icon-picker data-tod="${ref}" data-field="icon" value="${esc(tod.icon)}" label="${esc(t("Icon", "Symbol"))}"></ha-icon-picker>`
      : `<input class="field" data-tod="${ref}" data-field="icon" value="${esc(tod.icon)}" aria-label="${esc(t("Icon", "Symbol"))}" style="width:220px">`;
    return `<div class="r${open ? " open" : ""}">
      ${this._tile(tod)}
      <div><div class="cell" style="flex-wrap:wrap"><input class="field quiet" data-tod="${ref}" data-field="name" value="${esc(tod.name)}" aria-label="${esc(t("Name", "Name"))}"><span class="key" title="${esc(t("Key for automations", "Schlüssel für Automationen"))}">${esc(tod.key)}</span>${base ? `<span class="pill soft">${esc(t("Base state", "Grundzustand"))}</span>` : ""}</div>
        ${base ? `<div class="meta">${esc(t("Applies between the end of one day and the start of the next.", "Gilt vom Ende eines Tages bis zum Beginn des nächsten."))}</div>` : ""}</div>
      <div class="tools">${this._more(id)}${base ? "" : confirming ? `<span class="note">${esc(used.length ? `${t("Used in", "Genutzt in")} ${used.join(", ")}.` : "")}</span><button class="btn sm danger" data-act="delete-tod" data-key="${esc(tod.key)}">${esc(t("Delete", "Löschen"))}</button><button class="btn sm" data-act="confirm" data-v="">${esc(t("Keep", "Behalten"))}</button>` : `<button class="x" data-act="confirm" data-v="${esc(id)}" aria-label="${esc(t("Delete", "Löschen"))}">×</button>`}</div>
      ${open ? `<div class="sub-r"><div class="detail-grid">${picker}
        <span class="pal" role="group" aria-label="${esc(t("Color", "Farbe"))}">${colors.map((c) => `<button data-act="color" data-tod="${ref}" data-c="${esc(c)}" style="background:${esc(c)}" aria-pressed="${c.toLowerCase() === tod.color.toLowerCase()}" aria-label="${esc(c)}"></button>`).join("")}<span class="own" title="${esc(t("Own color", "Eigene Farbe"))}"><input type="color" data-tod="${ref}" data-field="color" value="${esc(tod.color)}" aria-label="${esc(t("Own color", "Eigene Farbe"))}"></span></span>
        ${base ? "" : `<span class="opt">${esc(used.length ? `${t("In", "In")} ${used.join(", ")}` : t("In no day model yet", "Noch in keinem Tagesmodell"))}</span>`}</div></div>` : ""}
    </div>`;
  }

  _todSection() {
    const t = this._t;
    const w = this._w;
    const free = this._templates.filter((tpl) => !w.times_of_day.some((x) => x.name === tpl.name));
    return `<section class="sec" id="sec-tods"><div class="hrow"><h2>${esc(t("Times of day", "Tageszeiten"))}</h2>${this._info("tods")}</div>
      ${this._infoText("tods", t("Each time of day has a name, an icon and a color. Its key stays the same when you rename it, so automations keep working. A day model decides when it begins. A new time of day takes the rule values of the one before it.", "Jede Tageszeit hat Name, Symbol und Farbe. Ihr Schlüssel bleibt beim Umbenennen gleich, damit Automationen weiterlaufen. Ein Tagesmodell legt fest, wann sie beginnt. Eine neue Tageszeit übernimmt in den Regeln die Werte der vorherigen."))}
      <div class="rows">${this._todRow(w.base, true)}${w.times_of_day.map((x) => this._todRow(x, false)).join("")}</div>
      <div class="add"><input class="field" id="newTod" placeholder="${esc(t("New time of day", "Neue Tageszeit"))}" aria-label="${esc(t("Name of the new time of day", "Name der neuen Tageszeit"))}" style="width:200px"><button class="btn" data-act="add-tod">${esc(t("Add", "Hinzufügen"))}</button>
        ${free.length ? `<span class="tpl">${esc(t("or from a template:", "oder aus einer Vorlage:"))}</span><span class="chips">${free.map((tpl) => `<button class="chip" data-act="add-tpl" data-name="${esc(tpl.name)}">${icon(tpl.icon, 14)}${esc(tpl.name)}</button>`).join("")}</span>` : ""}</div>
    </section>`;
  }

  // -- day models -------------------------------------------------------------------------------------

  _modelSection() {
    const t = this._t;
    const w = this._w;
    const model = this._currentModel();
    const chips = w.models
      .map((m) => `<button class="mchip" data-act="model" data-key="${esc(m.key)}" aria-pressed="${m.key === this._model}"><span>${esc(m.name)}</span><span data-strip="${esc(m.key)}">${this._stripHTML(m.key)}</span></button>`)
      .join("");
    let body = "";
    if (model) {
      const usedIn = WEEKDAYS.filter((d) => w.week[d] === model.key).length + w.calendar_links.filter((l) => l.model === model.key).length;
      const confirming = this._confirm === `model:${model.key}`;
      const free = w.times_of_day.filter((x) => !model.entries.some((e) => e.tod === x.key));
      body = `<div class="row space"><span class="row"><input class="field" id="modelName" value="${esc(model.name)}" aria-label="${esc(t("Name of the day model", "Name des Tagesmodells"))}" style="width:200px"><span class="key">${esc(model.key)}</span></span>
          <span class="row"><button class="btn" data-act="copy-model">${esc(t("Copy", "Kopieren"))}</button>
          ${confirming ? `<button class="btn danger" data-act="delete-model">${esc(t("Delete", "Löschen"))}</button><button class="btn" data-act="confirm" data-v="">${esc(t("Keep", "Behalten"))}</button>` : `<button class="btn" data-act="confirm" data-v="model:${esc(model.key)}" ${usedIn ? `disabled title="${esc(t("Used in the week plan or a calendar link", "Wird im Wochenplan oder in einer Kalender-Verknüpfung genutzt"))}"` : ""}>${esc(t("Delete", "Löschen"))}</button>`}</span></div>
        <div class="axis" id="axis"></div>
        ${this._infoText("models", t("Drag the marks of fixed times. Dashed marks follow the sun. A time after midnight belongs to the same day and shows +1.", "Ziehe die Markierungen fester Zeiten. Gestrichelte folgen der Sonne. Eine Zeit nach Mitternacht gehört zum selben Tag und zeigt +1."))}
        <div class="notice calm" id="dropNote" hidden></div>
        <div class="wrapx"><table class="tbl" id="entries">${this._entryRows(model)}</table></div>
        <div class="add">${free.length ? `<select class="field" id="addEntry" aria-label="${esc(t("Time of day", "Tageszeit"))}">${free.map((x) => `<option value="${esc(x.key)}">${esc(x.name)}</option>`).join("")}</select><button class="link" data-act="add-entry">${esc(t("+ Add to this model", "+ In dieses Modell aufnehmen"))}</button>` : `<span class="tpl">${esc(t("All times of day are in this model.", "Alle Tageszeiten sind in diesem Modell."))}</span>`}</div>`;
    }
    return `<section class="sec" id="sec-models"><div class="hrow"><h2>${esc(t("Day models", "Tagesmodelle"))}</h2>${this._info("models")}</div>
      ${this._infoText("models", t("A day model lists which times of day happen with which start, and when the day ends. Changes apply at once, also to the running day. The strip shows the day for the preview date.", "Ein Tagesmodell legt fest, welche Tageszeiten mit welcher Startzeit stattfinden und wann der Tag endet. Änderungen gelten sofort, auch für den laufenden Tag. Der Streifen zeigt den Tag für das Vorschau-Datum."))}
      <div class="chips">${chips}<span class="row"><input class="field" id="newModel" placeholder="${esc(t("New day model", "Neues Tagesmodell"))}" aria-label="${esc(t("Name of the new day model", "Name des neuen Tagesmodells"))}" style="width:170px"><button class="btn" data-act="add-model">${esc(t("Add", "Hinzufügen"))}</button></span></div>
      ${body}</section>`;
  }

  _specEditor(spec, ref) {
    const t = this._t;
    const kind = `<select class="field" data-entry="${ref}" data-field="kind" aria-label="${esc(t("Kind", "Art"))}"><option value="fixed"${spec.kind === "fixed" ? " selected" : ""}>${esc(t("Fixed", "Fest"))}</option><option value="sun"${spec.kind === "sun" ? " selected" : ""}>${esc(t("Sun", "Sonne"))}</option></select>`;
    const plus = `<label class="opt"><input type="checkbox" data-entry="${ref}" data-field="next_day"${spec.next_day ? " checked" : ""}> +1</label>`;
    if (spec.kind === "fixed") {
      return `<span class="spec">${kind}<input class="field time" type="time" data-entry="${ref}" data-field="time" value="${esc(spec.time)}" aria-label="${esc(t("Time", "Uhrzeit"))}">${plus}</span>`;
    }
    const id = `bounds-${ref}`;
    const open = this._open.has(id);
    const events = Object.entries(EVENTS)
      .map(([k, names]) => `<option value="${k}"${spec.event === k ? " selected" : ""}>${esc(t(...names))}</option>`)
      .join("");
    const bounds = open
      ? `<label class="opt">${esc(t("earliest", "frühestens"))} <input class="field time" type="time" data-entry="${ref}" data-field="earliest" value="${esc(spec.earliest || "")}"></label>
         <label class="opt">${esc(t("latest", "spätestens"))} <input class="field time" type="time" data-entry="${ref}" data-field="latest" value="${esc(spec.latest || "")}"></label>${plus}`
      : `<span class="sum">· ${esc(spec.earliest || "—")} ${esc(t("to", "bis"))} ${esc(spec.latest || "—")}${spec.next_day ? " +1" : ""}</span>`;
    return `<span class="spec">${kind}<select class="field" data-entry="${ref}" data-field="event" aria-label="${esc(t("Sun event", "Sonnenstand"))}">${events}</select>
      <span class="opt"><input class="field num" type="number" min="-720" max="720" step="5" data-entry="${ref}" data-field="offset" value="${esc(spec.offset)}" aria-label="${esc(t("Offset in minutes", "Versatz in Minuten"))}"> min</span>${bounds}${this._more(id, t("Bounds", "Grenzen"))}</span>`;
  }

  _entryRows(model) {
    const t = this._t;
    const w = this._w;
    const year = this._previewDate.slice(0, 4);
    const heads = [fmtDate(this._hass, this._previewDate), fmtDate(this._hass, `${year}-06-21`, { day: "numeric", month: "short" }), fmtDate(this._hass, `${year}-12-21`, { day: "numeric", month: "short" })];
    const rows = model.entries
      .map((e, i) => {
        const tod = this._look(e.tod);
        return `<tr><td><span class="cell"><button class="x" data-act="move" data-i="${i}" data-d="-1" ${i ? "" : "disabled"} aria-label="${esc(t("Up", "Nach oben"))}">↑</button><button class="x" data-act="move" data-i="${i}" data-d="1" ${i < model.entries.length - 1 ? "" : "disabled"} aria-label="${esc(t("Down", "Nach unten"))}">↓</button>
          ${this._tile(tod, true)}<b>${esc(tod.name)}</b></span></td>
          <td>${this._specEditor(e.at, i)}</td>
          ${[0, 1, 2].map((n) => `<td class="res" data-res="${n}" data-key="${esc(e.tod)}"></td>`).join("")}
          <td><button class="x" data-act="remove-entry" data-i="${i}" aria-label="${esc(t("Remove", "Entfernen"))}">×</button></td></tr>`;
      })
      .join("");
    return `<thead><tr><th>${esc(t("Time of day", "Tageszeit"))}</th><th>${esc(t("Start", "Start"))}</th>${heads.map((h) => `<th>${esc(h)}</th>`).join("")}<th></th></tr></thead>
      <tbody>${rows}<tr class="base"><td><span class="cell">${this._tile(w.base, true)}<b>${esc(w.base.name)} ${esc(t("from", "ab"))}</b></span></td>
        <td>${this._specEditor(model.end, "end")}</td>${[0, 1, 2].map((n) => `<td class="res" data-res="${n}" data-key=""></td>`).join("")}<td></td></tr></tbody>`;
  }

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
    if (endMark) {
      const base = this._w.base;
      segs += `<div class="seg" style="left:${pos(endMark.m)}%;width:${pos(Math.min(AXIS_MAX, endMark.m + 90)) - pos(endMark.m)}%;background:${esc(base.color)};color:${inkOn(base.color)}"></div>`;
    }
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

  // -- week plan and calendars ------------------------------------------------------------------------

  _modelOptions(selected, allowNone = false) {
    const t = this._t;
    const none = allowNone ? `<option value=""${!selected ? " selected" : ""}>${esc(t("— only the base state", "— nur Grundzustand"))}</option>` : "";
    return this._w.models.map((m) => `<option value="${esc(m.key)}"${m.key === selected ? " selected" : ""}>${esc(m.name)}</option>`).join("") + none;
  }

  _weekSection() {
    const t = this._t;
    const w = this._w;
    const calendars = Object.keys(this._hass.states).filter((e) => e.startsWith("calendar."));
    const calOptions = (selected) =>
      calendars
        .concat(selected && !calendars.includes(selected) ? [selected] : [])
        .map((c) => `<option value="${esc(c)}"${c === selected ? " selected" : ""}>${esc(friendly(this._hass, c))}</option>`)
        .join("");
    const links = w.calendar_links
      .map(
        (l, i) => `<div class="r"><span class="cell"><button class="x" data-act="move-link" data-i="${i}" data-d="-1" ${i ? "" : "disabled"} aria-label="${esc(t("Up", "Nach oben"))}">↑</button><button class="x" data-act="move-link" data-i="${i}" data-d="1" ${i < w.calendar_links.length - 1 ? "" : "disabled"} aria-label="${esc(t("Down", "Nach unten"))}">↓</button></span>
          <div class="cell" style="flex-wrap:wrap"><select class="field" data-link="${i}" data-field="calendar">${calOptions(l.calendar)}</select><span class="meta">${esc(t("with", "mit"))}</span><input class="field" data-link="${i}" data-field="match" value="${esc(l.match)}" placeholder="${esc(t("every event", "jedem Termin"))}" style="width:160px" aria-label="${esc(t("Title contains", "Titel enthält"))}"><span class="meta">→</span><select class="field" data-link="${i}" data-field="model">${this._modelOptions(l.model)}</select></div>
          <div class="tools"><button class="x" data-act="remove-link" data-i="${i}" aria-label="${esc(t("Remove", "Entfernen"))}">×</button></div></div>`,
      )
      .join("");
    return `<section class="sec" id="sec-week"><div class="hrow"><h2>${esc(t("Week plan", "Wochenplan"))}</h2>${this._info("week")}</div>
      ${this._infoText("week", t("Every weekday gets a day model. A calendar from Home Assistant can override single dates: public holidays, shifts or holidays. All-day events count for each of their dates, events with a time for the date they start on. The upper link wins. The month view is under Calendar.", "Jeder Wochentag bekommt ein Tagesmodell. Ein Kalender aus Home Assistant kann einzelne Daten übersteuern: Feiertage, Schichten oder Urlaub. Ganztägige Termine gelten für jedes ihrer Daten, Termine mit Uhrzeit für das Datum, an dem sie beginnen. Die obere Verknüpfung gewinnt. Die Monatsansicht steht unter Kalender."))}
      <div class="week">${WEEKDAYS.map((d) => `<div class="d"><b>${esc(t(...DAY_NAMES[d]))}</b><span data-strip="${esc(w.week[d] || "")}">${this._stripHTML(w.week[d])}</span><select class="field" data-week="${d}" aria-label="${esc(t(...DAY_NAMES[d]))}">${this._modelOptions(w.week[d], true)}</select></div>`).join("")}</div>
      <div class="hrow"><span class="sub">${esc(t("Calendars", "Kalender"))}</span></div>
      ${links ? `<div class="rows">${links}</div>` : ""}
      <div class="add">${calendars.length ? `<button class="link" data-act="add-link">${esc(t("+ Link a calendar", "+ Kalender verknüpfen"))}</button>` : `<span class="tpl">${esc(t("There is no calendar in Home Assistant yet. The integrations Holiday and Local calendar add one.", "In Home Assistant gibt es noch keinen Kalender. Die Integrationen Feiertage (Holiday) und Lokaler Kalender legen einen an."))}</span>`}
        ${w.calendar_links.length ? `<button class="link" data-act="refresh-cal">${esc(t("Read calendars now", "Kalender jetzt lesen"))}</button>` : ""}</div>
    </section>`;
  }

  // -- rules ------------------------------------------------------------------------------------------

  _lightInfo(entityId) {
    const t = this._t;
    const st = this._hass.states[entityId];
    if (!st) return { name: entityId, kind: t("not found", "nicht gefunden"), state: "", crescendo: false, color: false, kelvin: false, dimmable: false };
    const a = st.attributes;
    const modes = a.supported_color_modes || [];
    const crescendo = !!a.crescendo;
    const group = Array.isArray(a.entity_id) && a.entity_id.length > 0;
    const kelvin = modes.includes("color_temp");
    const color = modes.some((m) => ["hs", "rgb", "rgbw", "rgbww", "xy"].includes(m));
    const dimmable = crescendo || modes.some((m) => m !== "onoff");
    let kind = crescendo ? t("Crescendo object", "Crescendo-Objekt") : group ? `${t("Light group", "Lichtgruppe")} · ${a.entity_id.map((e) => friendly(this._hass, e)).join(", ")}` : t("Light", "Leuchte");
    if (!crescendo && !group) kind += ` · ${color && kelvin ? t("colors and white tones", "Farben und Weißtöne") : color ? t("colors", "Farben") : kelvin ? t("white tones", "Weißtöne") : dimmable ? t("dimming only", "nur Dimmen") : t("on/off only", "nur An/Aus")}`;
    const pct = st.state === "on" ? (crescendo ? Math.round(a.position ?? 0) : a.brightness != null ? Math.round((a.brightness * 100) / 255) : 100) : null;
    const state = st.state === "on" ? `${t("On", "An")}${dimmable ? `, ${pct} %` : ""}` : st.state === "off" ? t("Off", "Aus") : st.state;
    return { name: friendly(this._hass, entityId), kind, state, crescendo, color, kelvin, dimmable, buttons: crescendo ? a.buttons || [] : [] };
  }

  _ruleSummary(rule) {
    const t = this._t;
    const trig = [rule.motion.length ? t("motion", "Bewegung") : null, rule.buttons.length ? t("button", "Taster") : null, rule.manual ? t("by hand", "von Hand") : null].filter(Boolean).join(" · ") || t("without triggers", "ohne Auslöser");
    const names = [...rule.lights, ...rule.devices.map((d) => d.entity)].map((e) => friendly(this._hass, e));
    return `${names.join(", ") || t("no lights yet", "noch keine Leuchten")} · ${trig}`;
  }

  _rulesSection() {
    const t = this._t;
    const w = this._w;
    return `<section class="sec" id="sec-rules"><div class="hrow"><h2>${esc(t("Rules", "Regeln"))}</h2>${this._info("rules")}</div>
      ${this._infoText("rules", t("A rule says, for each time of day, what its lights do: when they come on, how bright and in which color, when they go off. It can also give devices a value when a time of day begins, such as a blind or the heating, or start a scene. When somebody changes a light by hand, Maestro remembers that for the memory time. The order counts when a light is in several rules.", "Eine Regel legt pro Tageszeit fest, was ihre Leuchten tun: wann sie angehen, wie hell und in welcher Farbe, wann sie ausgehen. Dazu kann sie Geräten beim Beginn einer Tageszeit einen Wert geben, etwa einem Rollo oder der Heizung, oder eine Szene starten. Ändert jemand eine Leuchte von Hand, merkt sich Maestro das für die Merkdauer. Die Reihenfolge zählt, wenn eine Leuchte in mehreren Regeln steht."))}
      <div style="display:grid;gap:10px">${w.rules.map((r, i) => this._ruleHTML(r, i)).join("")}</div>
      <div class="add"><input class="field" id="newRule" placeholder="${esc(t("New rule", "Neue Regel"))}" aria-label="${esc(t("Name of the new rule", "Name der neuen Regel"))}" style="width:200px"><button class="btn" data-act="add-rule">${esc(t("Add", "Hinzufügen"))}</button>
        ${w.rules.length ? `<span class="tpl">${esc(t("or like another rule:", "oder wie eine andere Regel:"))}</span><span class="chips">${w.rules.map((r) => `<button class="chip" data-act="copy-rule" data-id="${esc(r.id)}">${esc(r.name)}</button>`).join("")}</span>` : ""}</div>
    </section>`;
  }

  _ruleHTML(rule, index) {
    const t = this._t;
    const w = this._w;
    const open = this._open.has(`rule-${rule.id}`);
    const live = this._snap?.rules?.find((r) => r.id === rule.id);
    const onCount = live?.on?.length || 0;
    const head = `<div class="head" data-act="rule" data-id="${esc(rule.id)}"><span class="tile sm" style="background:var(--accent-soft);color:var(--accent)">${icon(rule.motion.length ? "mdi:motion-sensor" : "mdi:lightbulb-auto-outline", 16)}</span>
      <span class="name">${esc(rule.name)}</span><span class="sum">${esc(this._ruleSummary(rule))}${onCount ? ` · ${onCount} ${esc(t("on", "an"))}` : ""}</span><span class="grow"></span>
      <span class="row" data-stop>${index ? `<button class="x" data-act="move-rule" data-id="${esc(rule.id)}" data-d="-1" aria-label="${esc(t("Up", "Nach oben"))}">↑</button>` : ""}${index < w.rules.length - 1 ? `<button class="x" data-act="move-rule" data-id="${esc(rule.id)}" data-d="1" aria-label="${esc(t("Down", "Nach unten"))}">↓</button>` : ""}
      <label class="switch"><input type="checkbox" data-rule="${esc(rule.id)}" data-f="active" ${rule.active ? "checked" : ""}> ${esc(t("Active", "Aktiv"))}</label></span></div>`;
    if (!open) return `<div class="rule">${head}</div>`;
    const confirming = this._confirm === `rule:${rule.id}`;
    const moreId = `rule-${rule.id}-more`;
    const lights = rule.lights
      .map((e) => {
        const li = this._lightInfo(e);
        const also = w.rules.filter((r) => r !== rule && r.lights.includes(e)).map((r) => r.name);
        return `<div class="light"><b>${esc(li.name)}</b><span class="kind">${esc(li.kind)}</span>${also.length ? `<span class="pill soft">${esc(t("also in", "auch in"))} ${esc(also.join(", "))}</span>` : ""}<span class="state">${esc(li.state)}</span><button class="x" data-act="rm-light" data-rule="${esc(rule.id)}" data-e="${esc(e)}" aria-label="${esc(t("Remove", "Entfernen"))}">×</button></div>`;
      })
      .join("");
    const picker = (kind) => (this._pick?.rule === rule.id && this._pick.kind === kind ? this._pickerHTML(rule, kind) : "");
    const devs = rule.devices;
    const body = `<div class="body">
      <div class="row space"><input class="field" data-rule="${esc(rule.id)}" data-f="name" value="${esc(rule.name)}" aria-label="${esc(t("Name of the rule", "Name der Regel"))}" style="width:220px;font-weight:600">
        <span class="row"><button class="btn" data-act="copy-rule" data-id="${esc(rule.id)}">${esc(t("Copy rule", "Regel kopieren"))}</button>
        ${confirming ? `<button class="btn danger" data-act="delete-rule" data-id="${esc(rule.id)}">${esc(t("Delete", "Löschen"))}</button><button class="btn" data-act="confirm" data-v="">${esc(t("Keep", "Behalten"))}</button>` : `<button class="btn danger" data-act="confirm" data-v="rule:${esc(rule.id)}">${esc(t("Delete rule", "Regel löschen"))}</button>`}</span></div>
      <div><div class="hrow"><span class="sub">${esc(t("Lights", "Leuchten"))}</span>${this._info(`lights-${rule.id}`)}</div>
        ${this._infoText(`lights-${rule.id}`, t("One or more lights, also light groups and Crescendo objects. A light may be in several rules; the newest command wins. A Crescendo object takes a position from 1 to 100, its colors come from its stops.", "Eine oder mehrere Leuchten, auch Lichtgruppen und Crescendo-Objekte. Eine Leuchte darf in mehreren Regeln stehen; der neueste Befehl gewinnt. Bei einem Crescendo-Objekt gilt die Position 1 bis 100, Farben kommen aus seinen Stufen."))}
        <div>${lights}<div class="add"><button class="link" data-act="pick" data-rule="${esc(rule.id)}" data-kind="light">${esc(t("+ Add a light", "+ Leuchte hinzufügen"))}</button></div>${picker("light")}</div></div>
      <div><div class="hrow"><span class="sub">${esc(t("Triggers", "Auslöser"))}</span>${this._info(`trig-${rule.id}`)}</div>
        ${this._infoText(`trig-${rule.id}`, t("Motion switches on and, after the time in the row, off again. A button toggles. “By hand” means: when a light goes on without Maestro, it gets the values of the time of day or its remembered values. A light sensor only limits switching on.", "Bewegung schaltet ein und nach der Zeit in der Zeile wieder aus. Ein Taster schaltet um. „Von Hand“ heißt: Geht eine Leuchte an, ohne dass Maestro sie eingeschaltet hat, bekommt sie die Werte der Tageszeit oder ihre gemerkten Werte. Ein Helligkeitssensor begrenzt nur das Einschalten."))}
        <div class="trig">
          <span class="lbl">${esc(t("Motion or presence", "Bewegung oder Präsenz"))}</span><span class="chips">${rule.motion.map((m) => `<span class="tag">${esc(friendly(this._hass, m))}<button class="x" data-act="rm-motion" data-rule="${esc(rule.id)}" data-e="${esc(m)}" aria-label="${esc(t("Remove", "Entfernen"))}">×</button></span>`).join("")}<button class="chip" data-act="pick" data-rule="${esc(rule.id)}" data-kind="motion">${esc(t("+ Sensor", "+ Melder"))}</button></span>
          ${picker("motion") ? `<span></span>${picker("motion")}` : ""}
          <span class="lbl">${esc(t("Buttons", "Taster"))}</span><span class="chips">${rule.buttons
            .map((b, bi) => {
              const types = this._hass.states[b.entity]?.attributes?.event_types || [];
              return `<span class="tag">${esc(friendly(this._hass, b.entity))}${types.length ? `<select class="field" data-rule="${esc(rule.id)}" data-button="${bi}" style="min-height:26px;padding:1px 4px;font-size:12.5px"><option value="">${esc(t("any press", "jeder Druck"))}</option>${types.map((x) => `<option value="${esc(x)}"${b.event === x ? " selected" : ""}>${esc(x)}</option>`).join("")}</select>` : ""}<button class="x" data-act="rm-button" data-rule="${esc(rule.id)}" data-i="${bi}" aria-label="${esc(t("Remove", "Entfernen"))}">×</button></span>`;
            })
            .join("")}<button class="chip" data-act="pick" data-rule="${esc(rule.id)}" data-kind="button">${esc(t("+ Button", "+ Taster"))}</button><span class="opt">${esc(t("or the action “Toggle a rule” from an automation", "oder die Aktion „Regel umschalten“ aus einer Automation"))}</span></span>
          ${picker("button") ? `<span></span>${picker("button")}` : ""}
          <span class="lbl">${esc(t("By hand", "Von Hand"))}</span><label class="opt" style="color:var(--ink)"><input type="checkbox" data-rule="${esc(rule.id)}" data-f="manual" ${rule.manual ? "checked" : ""}> ${esc(t("Also reacts when a light goes on by hand", "Reagiert auch, wenn eine Leuchte von Hand angeht"))}</label>
          <span class="lbl">${esc(t("Only when dark", "Nur wenn dunkel"))}</span><span class="row">${rule.lux ? `<span class="tag">${esc(friendly(this._hass, rule.lux.sensor))}<button class="x" data-act="rm-lux" data-rule="${esc(rule.id)}" aria-label="${esc(t("Remove", "Entfernen"))}">×</button></span><span class="opt">${esc(t("below", "unter"))}</span><input class="field num" type="number" min="0" data-rule="${esc(rule.id)}" data-f="lux_below" value="${esc(rule.lux.below)}"><span class="opt">lx</span>` : `<button class="chip" data-act="pick" data-rule="${esc(rule.id)}" data-kind="lux">${esc(t("+ Light sensor", "+ Helligkeitssensor"))}</button>`}</span>
          ${picker("lux") ? `<span></span>${picker("lux")}` : ""}
        </div></div>
      <div><div class="hrow"><span class="sub">${esc(t("In each time of day", "In jeder Tageszeit"))}</span>${this._info(`rows-${rule.id}`)}<span class="grow"></span>${this._more(moreId, t("More about the rule", "Mehr zur Regel"))}</div>
        ${this._infoText(`rows-${rule.id}`, t("Each time of day has its own row. “At the start” says what happens to lights that are on when this time of day begins. Empty fields take the defaults from General. “More” opens transition, memory and taking over another row. “Test” applies the row now.", "Jede Tageszeit hat ihre eigene Zeile. „Beim Beginn“ sagt, was mit eingeschalteten Leuchten passiert, wenn diese Tageszeit anfängt. Leere Felder nehmen die Standardwerte aus Allgemein. „Mehr“ öffnet Übergang, Gedächtnis und das Übernehmen einer anderen Zeile. „Testen“ wendet die Zeile jetzt an."))}
        ${this._open.has(moreId) ? this._ruleMore(rule) : ""}
        <div class="wrapx"><table class="tbl"><thead><tr><th>${esc(t("Time of day", "Tageszeit"))}</th><th>${esc(t("Reaction", "Reaktion"))}</th><th>${esc(rule.lights.some((e) => this._lightInfo(e).crescendo) ? t("Position", "Position") : t("Brightness", "Helligkeit"))}</th><th>${esc(t("Color", "Farbe"))}</th><th>${esc(t("Off after", "Aus nach"))}</th><th>${esc(t("At the start", "Beim Beginn"))}</th><th></th><th></th></tr></thead>
          <tbody>${this._allTods().map((tod) => this._ruleRow(rule, tod)).join("")}</tbody></table></div></div>
      <div><div class="hrow"><span class="sub">${esc(t("Devices and actions at the start", "Geräte und Aktionen beim Beginn"))}</span>${this._info(`dev-${rule.id}`)}</div>
        ${this._infoText(`dev-${rule.id}`, t("When a time of day begins, a device gets its value once: a blind its position, a thermostat its temperature, a speaker its volume, a switch on or off. A scene or script starts. Empty means: do nothing. After that you may change the device; Maestro steps in again at the next start.", "Beim Beginn einer Tageszeit bekommt ein Gerät seinen Wert, einmal: ein Rollo seine Position, ein Thermostat seine Temperatur, ein Lautsprecher seine Lautstärke, ein Schalter an oder aus. Eine Szene oder ein Skript startet. Leer heißt: nichts tun. Danach darfst du das Gerät verstellen; Maestro greift erst beim nächsten Beginn wieder ein."))}
        ${devs.length ? `<div class="wrapx"><table class="tbl"><thead><tr><th>${esc(t("Time of day", "Tageszeit"))}</th>${devs.map((d, di) => `<th>${esc(friendly(this._hass, d.entity))}<br><span style="font-weight:400">${esc(this._deviceKind(d.entity))}</span> <button class="x" data-act="rm-device" data-rule="${esc(rule.id)}" data-i="${di}" aria-label="${esc(t("Remove", "Entfernen"))}" style="width:20px;height:20px;font-size:14px">×</button></th>`).join("")}<th></th></tr></thead>
          <tbody>${this._allTods()
            .map(
              (tod) => `<tr class="${tod.key === w.base.key ? "base" : ""}"><td><span class="cell">${this._tile(tod, true)}<b>${esc(tod.name)}</b></span></td>${devs.map((d, di) => `<td>${this._deviceCell(rule, di, d, tod.key)}</td>`).join("")}
                <td><button class="btn sm" data-act="test" data-rule="${esc(rule.id)}" data-tod="${esc(tod.key)}">${esc(t("Test", "Testen"))}</button></td></tr>`,
            )
            .join("")}</tbody></table></div>` : ""}
        <div class="add"><button class="link" data-act="pick" data-rule="${esc(rule.id)}" data-kind="device">${esc(t("+ Add a device or action", "+ Gerät oder Aktion hinzufügen"))}</button></div>${picker("device")}</div>
    </div>`;
    return `<div class="rule">${head}${body}</div>`;
  }

  _ruleMore(rule) {
    const t = this._t;
    const d = this._w.defaults;
    const manualAfter = rule.manual_after === "same" ? "same" : rule.manual_after === "never" ? "never" : "minutes";
    return `<div class="detail-grid scrim">
      <label>${esc(t("Switched on by hand or by another rule", "Von Hand oder von einer anderen Regel eingeschaltet"))} <select class="field" data-rule="${esc(rule.id)}" data-f="manual_after_mode"><option value="same"${manualAfter === "same" ? " selected" : ""}>${esc(t("same time until off", "gleiche Nachlaufzeit"))}</option><option value="minutes"${manualAfter === "minutes" ? " selected" : ""}>${esc(t("own time", "eigene Nachlaufzeit"))}</option><option value="never"${manualAfter === "never" ? " selected" : ""}>${esc(t("never switch off", "nicht ausschalten"))}</option></select>${manualAfter === "minutes" ? `<input class="field num" type="number" min="1" data-rule="${esc(rule.id)}" data-f="manual_after_minutes" value="${esc(rule.manual_after)}"> min` : ""}</label>
      <label>${esc(t("Switched on from outside", "Einschalten von außen"))} <select class="field" data-rule="${esc(rule.id)}" data-f="external_on"><option value="apply"${rule.external_on === "apply" ? " selected" : ""}>${esc(t("apply the time of day", "Werte der Tageszeit anwenden"))}</option><option value="keep"${rule.external_on === "keep" ? " selected" : ""}>${esc(t("leave as it is", "so lassen"))}</option></select></label>
      <label><input type="checkbox" data-rule="${esc(rule.id)}" data-f="warn" ${(rule.warn ?? d.warn) ? "checked" : ""}> ${esc(t("Warn by dimming before switching off", "Vorwarnung vor dem Ausschalten"))}</label>
      <label>${esc(t("Lock after switching off by hand", "Sperrzeit nach Ausschalten von Hand"))} <input class="field num" type="number" min="0" data-rule="${esc(rule.id)}" data-f="lock" value="${rule.lock ?? ""}" placeholder="${esc(d.lock)}"> s</label>
    </div>`;
  }

  _ruleRow(rule, tod) {
    const t = this._t;
    const w = this._w;
    const d = w.defaults;
    const row = rule.rows[tod.key] || { react: "none", begin: "keep" };
    const id = `row-${rule.id}-${tod.key}`;
    const open = this._open.has(id),
      colorOpen = this._open.has(`${id}-c`);
    const infos = rule.lights.map((e) => this._lightInfo(e));
    const cres = infos.some((x) => x.crescendo);
    const anyKelvin = infos.some((x) => x.kelvin),
      anyColor = infos.some((x) => x.color);
    const hasMotion = rule.motion.length > 0,
      hasButton = rule.buttons.length > 0;
    const off = row.react !== "on";
    const attrs = `data-rule="${esc(rule.id)}" data-tod="${esc(tod.key)}"`;
    const reactions = [["on", t("Switch on", "Einschalten")], ["off_only", t("Only switch off", "Nur ausschalten")], ["none", t("Do nothing", "Nicht reagieren")]];
    const begins = [["follow_free", t("Follow, unless overridden", "Folgen, außer übersteuert")], ["follow", t("Follow", "Folgen")], ["keep", t("Keep", "Beibehalten")], ["off", t("Switch off", "Ausschalten")]];
    const sel = (f, pairs, value) => `<select class="field" ${attrs} data-f="${f}">${pairs.map(([k, v]) => `<option value="${k}"${k === value ? " selected" : ""}>${esc(v)}</option>`).join("")}</select>`;
    const presets = cres ? infos.find((x) => x.crescendo).buttons : [];
    const brightCell = off
      ? `<span class="opt">—</span>`
      : `<span class="cell"><input class="field num" type="number" min="1" max="100" ${attrs} data-f="brightness" value="${row.brightness ?? ""}" placeholder="100"><span class="opt">%</span>${presets.length ? `<span class="presets">${presets.map((b) => `<button data-act="preset" ${attrs} data-v="${esc(b.position)}" title="${esc(b.name)}: ${esc(b.position)}">${esc(b.name)}</button>`).join("")}</span>` : ""}</span>`;
    const colorLabel = row.color?.kelvin ? `${row.color.kelvin} K` : row.color?.rgb ? t("Color", "Farbe") : t("as is", "wie bisher");
    const colorBg = row.color?.kelvin ? kelvinColor(row.color.kelvin) : row.color?.rgb ? `rgb(${row.color.rgb.join(",")})` : "var(--well)";
    const colorCell = off ? "" : cres ? `<span class="opt">${esc(t("from the stops", "aus den Stufen"))}</span>` : anyKelvin || anyColor ? `<button class="swatchbtn" data-act="more" data-id="${esc(id)}-c" aria-expanded="${colorOpen}"><i style="background:${colorBg}"></i>${esc(colorLabel)}</button>` : `<span class="opt">—</span>`;
    const afterCell = `<span class="cell"><input class="field num" type="number" min="0" ${attrs} data-f="after" value="${row.after ?? ""}" placeholder="${hasMotion ? esc(d.after) : "—"}"><span class="opt">min</span></span>`;
    let detail = "";
    if (colorOpen && !off) {
      const mode = row.color?.rgb ? "rgb" : "kelvin";
      detail += `<tr class="detail"><td colspan="8"><div class="detail-grid">
        ${anyKelvin ? `<label><input type="radio" name="${esc(id)}-mode" ${attrs} data-f="color_mode" value="kelvin" ${mode === "kelvin" ? "checked" : ""}> ${esc(t("White tone", "Weißton"))}</label>` : ""}
        ${anyColor ? `<label><input type="radio" name="${esc(id)}-mode" ${attrs} data-f="color_mode" value="rgb" ${mode === "rgb" ? "checked" : ""}> ${esc(t("Color", "Farbe"))}</label>` : ""}
        ${mode === "kelvin" ? `<input class="bar-k" type="range" min="2000" max="6500" step="50" ${attrs} data-f="kelvin" value="${row.color?.kelvin || 3000}" aria-label="${esc(t("White tone", "Weißton"))}"><span class="opt">${row.color?.kelvin || 3000} K</span>` : `<input class="bar-h" type="range" min="0" max="359" ${attrs} data-f="hue" value="${row.color?.rgb ? rgbHue(row.color.rgb) : 30}" aria-label="${esc(t("Color", "Farbe"))}">`}
        <button class="link" data-act="color-none" ${attrs}>${esc(t("No color change", "Keine Farbänderung"))}</button></div></td></tr>`;
    }
    if (open) {
      detail += `<tr class="detail"><td colspan="8"><div class="detail-grid">
        <label>${esc(t("Transition", "Übergang"))} <input class="field num" type="number" min="0" ${attrs} data-f="transition" value="${row.transition ?? ""}" placeholder="${esc(d.transition)}"> s${cres ? ` <span class="opt">${esc(t("empty: the object's speed", "leer: Tempo des Objekts"))}</span>` : ""}</label>
        <label>${esc(t("Memory", "Merkdauer"))} <input class="field num" type="number" min="0" ${attrs} data-f="memory" value="${row.memory ?? ""}" placeholder="${esc(d.memory)}"> min</label>
        <label><input type="checkbox" ${attrs} data-f="forget" ${row.forget ? "checked" : ""}> ${esc(t("Forget at the start", "Beim Beginn vergessen"))}</label>
        ${rule.lux ? `<label>${esc(t("Only below", "Nur unter"))} <input class="field num" type="number" min="0" ${attrs} data-f="lux_below" value="${row.lux_below ?? ""}" placeholder="${esc(rule.lux.below)}"> lx</label>` : ""}
        <label>${esc(t("Row like", "Zeile wie"))} <select class="field" ${attrs} data-f="copy_row"><option value="">…</option>${this._allTods()
          .filter((x) => x.key !== tod.key)
          .map((x) => `<option value="${esc(x.key)}">${esc(x.name)}</option>`)
          .join("")}</select></label>
        <button class="link" data-act="row-all" ${attrs}>${esc(t("Use for all times of day", "Für alle Tageszeiten übernehmen"))}</button></div></td></tr>`;
    }
    return `<tr class="${tod.key === w.base.key ? "base" : ""}${open || colorOpen ? " open" : ""}">
      <td><span class="cell">${this._tile(tod, true)}<b>${esc(tod.name)}</b></span></td>
      <td>${sel("react", reactions, row.react)}</td>
      <td>${brightCell}</td><td>${colorCell}</td><td>${afterCell}</td>
      <td>${sel("begin", begins, row.begin)}</td>
      <td><button class="btn sm" data-act="test" data-rule="${esc(rule.id)}" data-tod="${esc(tod.key)}">${esc(t("Test", "Testen"))}</button></td>
      <td>${this._more(id)}</td></tr>${detail}`;
  }

  _deviceKind(entityId) {
    const t = this._t;
    const names = { cover: ["Blind", "Rollo"], climate: ["Thermostat", "Thermostat"], media_player: ["Speaker", "Lautsprecher"], fan: ["Fan", "Lüfter"], switch: ["Switch", "Schalter"], input_boolean: ["Switch", "Schalter"], number: ["Value", "Wert"], input_number: ["Value", "Wert"], scene: ["Scene", "Szene"], script: ["Script", "Skript"] };
    const pair = names[entityId.split(".")[0]];
    return pair ? t(...pair) : entityId.split(".")[0];
  }

  _deviceCell(rule, di, device, key) {
    const t = this._t;
    const domain = device.entity.split(".")[0];
    const value = device.values[key];
    const attrs = `data-rule="${esc(rule.id)}" data-device="${di}" data-tod="${esc(key)}"`;
    if (domain in DEVICE_UNITS) {
      const unit = domain === "climate" ? this._hass.config?.unit_system?.temperature || "°C" : DEVICE_UNITS[domain];
      return `<span class="cell"><input class="field num" type="number" step="${domain === "climate" ? 0.5 : 5}" ${attrs} value="${value ?? ""}" placeholder="—" aria-label="${esc(friendly(this._hass, device.entity))}"><span class="opt">${esc(unit)}</span></span>`;
    }
    const pairs = domain === "scene" || domain === "script" ? [["", "—"], ["on", t("start", "starten")]] : [["", "—"], ["on", t("on", "an")], ["off", t("off", "aus")]];
    const current = value === true || value === "on" ? "on" : value === false || value === "off" ? "off" : "";
    return `<select class="field" ${attrs} aria-label="${esc(friendly(this._hass, device.entity))}">${pairs.map(([k, v]) => `<option value="${k}"${k === current ? " selected" : ""}>${esc(v)}</option>`).join("")}</select>`;
  }

  // The entity search for lights, sensors, buttons and devices.
  _pickerHTML(rule, kind) {
    const t = this._t;
    const titles = { light: t("Add a light", "Leuchte hinzufügen"), motion: t("Add a motion or presence sensor", "Bewegungs- oder Präsenzmelder hinzufügen"), button: t("Add a button", "Taster hinzufügen"), lux: t("Choose a light sensor", "Helligkeitssensor wählen"), device: t("Add a device or action", "Gerät oder Aktion hinzufügen") };
    return `<div class="pick"><div class="row space"><span class="sub">${esc(titles[kind])}</span><button class="btn sm" data-act="pick-close">${esc(t("Done", "Fertig"))}</button></div>
      <input class="field" type="search" id="pickSearch" value="${esc(this._pickQuery)}" placeholder="${esc(t("Search by name or room", "Nach Name oder Raum suchen"))}" autocomplete="off">
      <div class="picklist" id="pickList">${this._pickListHTML(rule, kind)}</div></div>`;
  }

  _pickCandidates(rule, kind) {
    const hass = this._hass;
    const all = Object.keys(hass.states);
    const taken = new Set(kind === "light" ? rule.lights : kind === "motion" ? rule.motion : kind === "button" ? rule.buttons.map((b) => b.entity) : kind === "device" ? rule.devices.map((d) => d.entity) : []);
    const prefer = (id) => {
      const dc = hass.states[id].attributes.device_class;
      if (kind === "motion") return ["motion", "occupancy", "presence"].includes(dc) ? 0 : 1;
      if (kind === "lux") return dc === "illuminance" ? 0 : 1;
      if (kind === "light") return hass.states[id].attributes.crescendo ? 0 : 1;
      return 0;
    };
    const ok = (id) => {
      const domain = id.split(".")[0];
      if (taken.has(id)) return false;
      if (kind === "light") return domain === "light";
      if (kind === "motion") return domain === "binary_sensor";
      if (kind === "button") return domain === "event" || domain === "input_button" || domain === "button";
      if (kind === "lux") return domain === "sensor" && (hass.states[id].attributes.device_class === "illuminance" || /lx|lux/i.test(hass.states[id].attributes.unit_of_measurement || ""));
      return DEVICE_DOMAINS.includes(domain) && !hass.states[id].attributes.crescendo;
    };
    const q = this._pickQuery.trim().toLowerCase();
    return all
      .filter(ok)
      .filter((id) => !q || `${friendly(hass, id)} ${areaOf(hass, id)} ${id}`.toLowerCase().includes(q))
      .sort((a, b) => prefer(a) - prefer(b) || friendly(hass, a).localeCompare(friendly(hass, b)))
      .slice(0, 60);
  }

  _pickListHTML(rule, kind) {
    const t = this._t;
    const hass = this._hass;
    const items = this._pickCandidates(rule, kind);
    if (!items.length) return `<p class="note" style="padding:8px">${esc(t("Nothing found.", "Nichts gefunden."))}</p>`;
    return items
      .map((id) => {
        const st = hass.states[id];
        const meta = [areaOf(hass, id), kind === "light" ? this._lightInfo(id).kind : kind === "device" ? this._deviceKind(id) : st.attributes.device_class || ""].filter(Boolean).join(" · ");
        const state = kind === "light" ? this._lightInfo(id).state : st.state === "on" || st.state === "off" ? t(st.state === "on" ? "On" : "Off", st.state === "on" ? "An" : "Aus") : st.state.length < 12 ? st.state : "";
        return `<button data-act="pick-add" data-rule="${esc(rule.id)}" data-kind="${esc(kind)}" data-e="${esc(id)}"><span class="pname">${esc(friendly(hass, id))}</span><span class="pstate">${esc(state)}</span><span class="pmeta">${esc(meta || id)}</span></button>`;
      })
      .join("");
  }

  // -- general ----------------------------------------------------------------------------------------

  _generalSection() {
    const t = this._t;
    const w = this._w;
    const r = this._r;
    const loc = w.location;
    const d = w.defaults;
    const sensor = r.entities?.time_of_day || "sensor.…";
    const example = w.times_of_day[0]?.key || "aufstehen";
    return `<section class="sec" id="sec-general"><div class="hrow"><h2>${esc(t("General", "Allgemein"))}</h2></div>
      <div class="hrow"><span class="sub">${esc(t("Location for sun times", "Standort für Sonnenzeiten"))}</span></div>
      <div class="row"><label class="opt" style="color:var(--ink)"><input type="radio" name="loc" id="locHa" ${loc ? "" : "checked"}> ${esc(t("Location of Home Assistant", "Standort von Home Assistant"))}</label><label class="opt" style="color:var(--ink)"><input type="radio" name="loc" id="locOwn" ${loc ? "checked" : ""}> ${esc(t("Own location", "Eigener Standort"))}</label>
        ${loc ? `<input class="field num" id="lat" type="number" step="0.0001" min="-90" max="90" value="${esc(loc.latitude)}" aria-label="${esc(t("Latitude", "Breitengrad"))}" style="width:110px"><input class="field num" id="lon" type="number" step="0.0001" min="-180" max="180" value="${esc(loc.longitude)}" aria-label="${esc(t("Longitude", "Längengrad"))}" style="width:110px">` : ""}</div>
      <div class="hrow"><span class="sub">${esc(t("Defaults for the rules", "Standardwerte für Regeln"))}</span>${this._info("defaults")}</div>
      ${this._infoText("defaults", t("Empty fields in the rules take these values. Before switching off, the warning dims to half, at least 1 %. The lock keeps motion from switching a light back on right after somebody switched it off by hand.", "Leere Felder in den Regeln nehmen diese Werte. Die Vorwarnung dimmt vor dem Ausschalten auf die Hälfte, mindestens 1 %. Die Sperrzeit verhindert, dass eine von Hand ausgeschaltete Leuchte beim Hinausgehen gleich wieder angeht."))}
      <div class="detail-grid">
        <label>${esc(t("Transition", "Übergang"))} <input class="field num" type="number" min="0" data-default="transition" value="${esc(d.transition)}"> s</label>
        <label>${esc(t("Memory", "Merkdauer"))} <input class="field num" type="number" min="0" data-default="memory" value="${esc(d.memory)}"> min</label>
        <label>${esc(t("Off after", "Nachlaufzeit"))} <input class="field num" type="number" min="0" data-default="after" value="${esc(d.after)}"> min</label>
        <label><input type="checkbox" data-default="warn" ${d.warn ? "checked" : ""}> ${esc(t("Warning", "Vorwarnung"))}</label>
        <label><input class="field num" type="number" min="3" max="300" data-default="warn_seconds" value="${esc(d.warn_seconds)}"> s</label>
        <label>${esc(t("Lock", "Sperrzeit"))} <input class="field num" type="number" min="0" data-default="lock" value="${esc(d.lock)}"> s</label></div>
      <details><summary>${esc(t("In automations", "In Automationen"))}</summary>
        <p class="note" style="margin:8px 0">${esc(t("The rhythm is a device with triggers, conditions and actions. States use the keys, not the names. A trigger can fire before a planned time, for example 15 minutes before wake-up.", "Der Rhythmus ist ein Gerät mit Triggern, Bedingungen und Aktionen. Zustände nutzen die Schlüssel, nicht die Namen. Ein Trigger kann vor einer geplanten Zeit feuern, zum Beispiel 15 Minuten vor dem Aufstehen."))}</p>
        <pre>${esc(`triggers:
  - trigger: device
    domain: cloudless_maestro
    device_id: ${r.device_id || "…"}
    type: begins
    time_of_day: ${example}
    offset: -15

action: cloudless_maestro.toggle_rule
target:
  entity_id: ${sensor}
data:
  rule: ${w.rules[0]?.id || "bad"}`)}</pre></details>
      <div><div class="sub">${esc(t("Entry in the sidebar", "Eintrag in der Seitenleiste"))}</div><p class="note">${esc(t("Maestro has its own entry in the sidebar of Home Assistant. Without it, this page stays reachable through Configure on a rhythm under Devices & services.", "Maestro hat einen eigenen Eintrag in der Seitenleiste von Home Assistant. Ohne ihn bleibt diese Seite über „Konfigurieren“ beim Rhythmus unter Geräte & Dienste erreichbar."))}</p>
        <button class="link" data-act="sidebar">${esc(this._sidebar ? t("Remove this page from the sidebar", "Diese Einstellungsseite aus der Seitenleiste entfernen") : t("Show this page in the sidebar again", "Diese Einstellungsseite wieder in der Seitenleiste zeigen"))}</button></div>
    </section>`;
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
        this._month = { start: gridStart, days, plans: {} };
      } catch (err) {
        main.innerHTML = `<div class="sheet"><div class="notice">${esc(err?.message || String(err))}</div></div>`;
        return;
      }
    }
    const month = first.slice(0, 7);
    const name = (key) => this._r.options.models.find((m) => m.key === key)?.name || "—";
    const cells = this._month.days
      .map((d) => {
        const cls = `d${d.day.slice(0, 7) !== month ? " other" : ""}${d.day === today ? " today" : ""}${d.day === this._selDay ? " sel" : ""}`;
        const dot = d.adjustment ? `<span class="dot" style="background:var(--warn)" title="${esc(t("adjusted", "angepasst"))}"></span>` : d.source === "calendar" ? `<span class="dot" style="background:var(--accent)" title="${esc(t("from a calendar", "aus einem Kalender"))}"></span>` : "";
        return `<button class="${cls}" data-act="day" data-day="${d.day}"><span class="n">${Number(d.day.slice(8))}${dot}</span><span class="mn">${esc(name(d.model))}</span><span data-daystrip="${d.day}">${this._stripHTML(d.model, this._month.plans[d.day])}</span></button>`;
      })
      .join("");
    const heads = WEEKDAYS.map((d) => `<div class="wd">${esc(t(...DAY_NAMES[d]))}</div>`).join("");
    main.innerHTML = `<div class="sheet"><section class="sec">
      <div class="row space"><h2 style="font-size:22px;font-weight:700">${esc(fmtDate(this._hass, first, { month: "long", year: "numeric" }))}</h2>
        <span class="row"><button class="btn" data-act="month" data-d="-1" aria-label="${esc(t("Previous month", "Voriger Monat"))}">‹</button><button class="btn" data-act="month" data-d="0">${esc(t("Today", "Heute"))}</button><button class="btn" data-act="month" data-d="1" aria-label="${esc(t("Next month", "Nächster Monat"))}">›</button></span></div>
      <div class="legend"><span><span class="dot" style="background:var(--accent)"></span> ${esc(t("from a calendar", "aus einem Kalender"))}</span><span><span class="dot" style="background:var(--warn)"></span> ${esc(t("adjusted", "angepasst"))}</span><span>${esc(t("Strip: the day after its model", "Streifen: der Tag nach seinem Modell"))}</span></div>
      <div class="month">${heads}${cells}</div></section>
      <section class="sec" id="dayEditor"></section></div>`;
    this._renderDayEditor();
    this._fetchMonthStrips();
  }

  // Resolved days for the month, in batches per model, so each cell shows its strip.
  async _fetchMonthStrips() {
    const month = this._month;
    if (!month || month.loading) return;
    month.loading = true;
    const byModel = {};
    for (const d of month.days) if (d.model && !month.plans[d.day]) (byModel[d.model] ||= []).push(d.day);
    for (const [model, dates] of Object.entries(byModel)) {
      for (let i = 0; i < dates.length; i += 14) {
        try {
          const plans = await this._hass.callWS({ type: "cloudless_maestro/preview", entry_id: this._r.entry_id, options: this._r.options, model, dates: dates.slice(i, i + 14) });
          for (const p of plans) month.plans[p.day] = p;
        } catch {
          // Cells stay without a strip.
        }
      }
    }
    month.loading = false;
    if (this._month !== month) return;
    this.shadowRoot.querySelectorAll("[data-daystrip]").forEach((el) => {
      const day = el.dataset.daystrip;
      const info = month.days.find((d) => d.day === day);
      el.innerHTML = this._stripHTML(info?.model, month.plans[day]);
    });
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
    const src = info.source === "calendar" ? `${t("From the calendar", "Aus dem Kalender")}${info.detail ? `: ${info.detail}` : ""}` : info.source === "adjustment" ? t("Chosen for this date", "Für dieses Datum gewählt") : t("From the week plan", "Aus dem Wochenplan");
    const planned = Object.fromEntries((this._dayPlan?.entries || []).map((e) => [e.key, e.start]));
    const rows = (model?.entries || [])
      .map((e) => {
        const tod = this._look(e.tod);
        const own = adj.times?.[e.tod];
        const value = own?.kind === "fixed" ? own.time : planned[e.tod] ? localParts(this._hass, planned[e.tod]).time : "";
        return `<tr><td><span class="cell">${this._tile(tod, true)}${esc(tod.name)}</span></td>
          <td><input class="field time" type="time" data-daytime="${esc(e.tod)}" value="${esc(value)}"></td>
          <td>${own ? `<button class="btn sm" data-act="day-reset" data-key="${esc(e.tod)}">${esc(t("Back to the model", "Zurück zum Modell"))}</button>` : `<span class="note">${planned[e.tod] ? "" : esc(t("does not happen", "fällt aus"))}</span>`}</td></tr>`;
      })
      .join("");
    const endValue = adj.end?.kind === "fixed" ? adj.end.time : this._dayPlan?.end ? localParts(this._hass, this._dayPlan.end).time : "";
    box.innerHTML = `<h2 style="font-size:19px;font-weight:700">${esc(fmtDate(this._hass, info.day, { weekday: "long", day: "numeric", month: "long" }))}</h2>
      <div class="row"><label class="row">${esc(t("Day model", "Tagesmodell"))} <select class="field" id="dayModel"><option value="">${esc(t("As planned", "Wie geplant"))}</option>${opts.models.map((m) => `<option value="${esc(m.key)}"${adj.model === m.key ? " selected" : ""}>${esc(m.name)}</option>`).join("")}</select></label><span class="note">${esc(src)}</span></div>
      ${model ? `<div class="wrapx"><table class="tbl"><tbody>${rows}<tr class="base"><td><span class="cell">${this._tile(opts.base, true)}<b>${esc(opts.base.name)} ${esc(t("from", "ab"))}</b></span></td><td><input class="field time" type="time" data-dayend="1" value="${esc(endValue)}"></td><td>${adj.end ? `<button class="btn sm" data-act="day-reset-end">${esc(t("Back to the model", "Zurück zum Modell"))}</button>` : ""}</td></tr></tbody></table></div>` : ""}
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

  _logText(item) {
    const t = this._t;
    const name = (k) => (k ? this._look(k)?.name || k : "—");
    const light = (e) => friendly(this._hass, e);
    const reasons = { plan: t("plan", "Plan"), pin: t("pinned", "festgesetzt"), resume: t("back to the plan", "zurück zum Plan"), adjustment: t("day adjusted", "Tag angepasst"), calendar: t("calendar", "Kalender"), config: t("settings", "Einstellungen"), restart: t("restart", "Neustart") };
    const until = { next_change: t("until the next change", "bis zum nächsten Wechsel"), duration: t("for a duration", "für eine Dauer"), time: t("until a time", "bis Uhrzeit"), next_day: t("until the next day", "bis zum nächsten Tag"), reset: t("until reset", "bis zurückgesetzt") };
    if (item.kind === "change") return `${name(item.from)} → ${name(item.to)} · ${reasons[item.reason] || item.reason}`;
    if (item.kind === "pin") return `${t("Pinned", "Festgesetzt")}: ${name(item.to)}, ${until[item.mode] || item.mode}${item.until ? ` (${fmtTime(this._hass, item.until)})` : ""}`;
    if (item.kind === "resume") return t("Back to the plan", "Zurück zum Plan");
    if (item.kind === "pin_ended") return t("The pin ended", "Die Festsetzung ist abgelaufen");
    if (item.kind === "adjust") return `${item.adjustment ? t("Day adjusted", "Tag angepasst") : t("Day adjustment removed", "Tagesanpassung entfernt")}: ${fmtDate(this._hass, item.day)}`;
    if (item.kind === "calendar_error") return `${t("Calendar not readable", "Kalender nicht lesbar")}: ${item.calendar} · ${item.error}`;
    if (item.kind === "rule") {
      const who = item.name ? `${item.name}: ` : "";
      const lights = (item.lights || []).map(light).join(", ");
      const what = {
        motion_on: `${t("motion, switched on", "Bewegung, eingeschaltet")} (${lights}${item.row ? `, ${name(item.row)}` : ""})`,
        memory: `${t("remembered values used for", "gemerkte Werte für")} ${light(item.light || "")}`,
        prewarn: `${t("warning before switching off", "Vorwarnung vor dem Ausschalten")} (${lights})`,
        prewarn_cancelled: t("motion during the warning, back to the previous values", "Bewegung während der Vorwarnung, zurück zum vorigen Wert"),
        off: `${t("switched off", "ausgeschaltet")} (${lights})`,
        override: `${light(item.light || "")} ${t("changed by hand, remembered", "von Hand geändert, gemerkt")}`,
        manual_on: `${light(item.light || "")} ${item.memory ? t("switched on by hand, remembered values applied", "von Hand eingeschaltet, gemerkte Werte angewendet") : t("switched on by hand, time of day applied", "von Hand eingeschaltet, Tageszeit angewendet")}`,
        manual_off: `${light(item.light || "")} ${t("switched off by hand", "von Hand ausgeschaltet")}`,
        locked: t("motion ignored during the lock time", "Bewegung in der Sperrzeit ignoriert"),
        bright: t("bright enough, no light", "hell genug, kein Licht"),
        begin_off: `${name(item.to)} ${t("began, switched off", "begann, ausgeschaltet")} (${lights})`,
        follow: `${name(item.to)} ${t("began, lights follow", "begann, Leuchten folgen")} (${lights})`,
        device: `${light(item.entity || "")} → ${item.value}`,
        device_error: `${light(item.entity || "")}: ${item.error}`,
        toggle_on: `${t("switched on", "eingeschaltet")} (${item.by === "button" ? t("button", "Taster") : t("action", "Aktion")})`,
        toggle_off: `${t("switched off", "ausgeschaltet")} (${item.by === "button" ? t("button", "Taster") : t("action", "Aktion")})`,
        toggle_ignored: t("button pressed, but the row does not switch on", "Taster gedrückt, aber die Zeile schaltet nicht ein"),
        test: `${t("test of the row", "Test der Zeile")} ${name(item.row)}`,
        forget: t("memory cleared", "Gedächtnis gelöscht"),
        active: t("rule switched on", "Regel eingeschaltet"),
        paused: t("rule paused", "Regel pausiert"),
      }[item.what];
      return `${who}${what || item.what}`;
    }
    return item.kind;
  }

  async _renderDiag(main) {
    const t = this._t;
    main.innerHTML = `<div class="sheet"><p class="note">${esc(t("Loading …", "Wird geladen …"))}</p></div>`;
    try {
      this._diag = await this._hass.callWS({ type: "cloudless_maestro/diagnostics", entry_id: this._r.entry_id });
    } catch (err) {
      main.innerHTML = `<div class="sheet"><div class="notice">${esc(err?.message || String(err))}</div></div>`;
      return;
    }
    const d = this._diag;
    const st = d.state;
    const tod = this._look(st.key);
    const next = st.next_key ? this._look(st.next_key) : null;
    const day = d.days?.[0];
    const modelName = this._r.options.models.find((m) => m.key === day?.model)?.name || "—";
    const sources = { week: t("from the week plan", "aus dem Wochenplan"), calendar: t("from a calendar", "aus einem Kalender"), adjustment: t("chosen for this date", "für dieses Datum gewählt") };
    const facts = `<div class="facts">
      <div class="fact"><h3>${esc(t("Time of day now", "Tageszeit jetzt"))}</h3><b>${this._tile(tod, true)} ${esc(tod.name)}</b><span class="meta">${esc(t("since", "seit"))} ${esc(fmtTime(this._hass, st.since))}${st.pinned ? ` · ${esc(t("pinned", "festgesetzt"))}` : ""}</span></div>
      <div class="fact"><h3>${esc(t("Next change", "Nächster Wechsel"))}</h3><b>${next ? `${this._tile(next, true)} ${esc(next.name)}` : "—"}</b><span class="meta">${st.until ? esc(fmtTime(this._hass, st.until)) : ""}</span></div>
      <div class="fact"><h3>${esc(t("Day model", "Tagesmodell"))}</h3><b>${esc(modelName)}</b><span class="meta">${esc(sources[day?.source] || "")}${day?.adjusted ? ` · ${esc(t("adjusted", "angepasst"))}` : ""}</span></div>
      <div class="fact"><h3>${esc(t("Rules", "Regeln"))}</h3><b>${d.rules.length}</b><span class="meta">${esc(d.rules.filter((r) => r.active).length)} ${esc(t("active", "aktiv"))}${d.rules.some((r) => r.on.length) ? ` · ${d.rules.reduce((n, r) => n + r.on.length, 0)} ${esc(t("lights on", "Leuchten an"))}` : ""}</span></div></div>`;
    const rules = d.rules
      .map((r) => {
        const pending = Object.entries(r.pending).map(([e, at]) => `${friendly(this._hass, e)} ${t("off at", "aus um")} ${fmtTime(this._hass, at)}`).join(", ");
        return `<div class="r"><span class="tile sm" style="background:var(--accent-soft);color:var(--accent)">${icon(r.motion !== null ? "mdi:motion-sensor" : "mdi:lightbulb-auto-outline", 15)}</span><div><div><b>${esc(r.name)}</b> ${r.active ? "" : `<span class="pill warn">${esc(t("paused", "pausiert"))}</span>`}${r.locked_until ? ` <span class="pill soft">${esc(t("lock until", "Sperre bis"))} ${esc(fmtTime(this._hass, r.locked_until))}</span>` : ""}</div><div class="meta">${esc(r.on.length ? `${r.on.map((e) => friendly(this._hass, e)).join(", ")} ${t("on", "an")}` : t("all off", "alles aus"))}${pending ? ` · ${esc(pending)}` : ""}${r.motion ? ` · ${esc(t("motion", "Bewegung"))}` : ""}</div></div><span></span></div>`;
      })
      .join("");
    const lights = d.lights
      .map((l) => `<div class="r"><span class="dot" style="background:${l.on ? "var(--accent)" : "var(--line)"}"></span><div><b>${esc(l.name)}</b><div class="meta">${l.memory?.values?.on ? `${Math.round(l.memory.values.brightness || 0)} %${l.memory.values.kelvin ? ` · ${l.memory.values.kelvin} K` : ""} · ${esc(fmtTime(this._hass, l.memory.at))}` : ""}</div></div><button class="btn sm" data-act="forget" data-e="${esc(l.entity_id)}">${esc(t("Forget", "Vergessen"))}</button></div>`)
      .join("");
    const rows = d.log.map((item) => `<tr><td>${esc(fmtDate(this._hass, item.at, { day: "numeric", month: "short" }))} ${esc(fmtTime(this._hass, item.at))}</td><td>${esc(this._logText(item))}</td></tr>`).join("");
    const cals = Object.entries(d.calendars)
      .map(([cal, s]) => `<div class="r"><span class="tile sm" style="background:${s.error ? "var(--warn-soft)" : "var(--good-soft)"};color:${s.error ? "var(--warn)" : "var(--good)"}">${icon("mdi:calendar", 15)}</span><div><b>${esc(friendly(this._hass, cal))}</b><div class="meta">${esc(s.fetched ? `${s.events} ${t("events", "Termine")} · ${fmtDate(this._hass, s.fetched, { day: "numeric", month: "short" })} ${fmtTime(this._hass, s.fetched)}` : "")}${s.error ? ` ${esc(s.error)}` : ""}</div></div>${s.error ? `<span class="pill warn">${esc(t("not readable", "nicht lesbar"))}</span>` : `<span class="pill ok">${esc(t("read", "gelesen"))}</span>`}</div>`)
      .join("");
    const lightIds = Object.keys(this._hass.states).filter((e) => e.startsWith("light.")).sort((a, b) => friendly(this._hass, a).localeCompare(friendly(this._hass, b)));
    const ruleLights = new Set(this._r.options.rules.flatMap((r) => r.lights));
    const ordered = [...lightIds.filter((e) => ruleLights.has(e)), ...lightIds.filter((e) => !ruleLights.has(e))];
    main.innerHTML = `<div class="sheet">
      ${facts}
      ${rules ? `<section class="sec"><div class="hrow"><h2>${esc(t("Rules", "Regeln"))}</h2></div><div class="rows">${rules}</div></section>` : ""}
      ${lights ? `<section class="sec"><div class="hrow"><h2>${esc(t("Set by hand", "Von Hand eingestellt"))}</h2></div><div class="rows">${lights}</div></section>` : ""}
      <section class="sec"><div class="hrow"><h2>${esc(t("What happened", "Was passiert ist"))}</h2>${this._info("log")}</div>
        ${this._infoText("log", t("The latest changes and decisions, newest first, to answer “Why did the light do that?”.", "Die letzten Wechsel und Entscheidungen, neueste zuerst, damit sich „Warum hat die Leuchte das getan?“ beantworten lässt."))}
        ${rows ? `<div class="wrapx"><table class="tbl log"><tbody>${rows}</tbody></table></div>` : `<p class="note">${esc(t("Nothing yet.", "Noch nichts."))}</p>`}</section>
      ${cals ? `<section class="sec"><div class="hrow"><h2>${esc(t("Calendars", "Kalender"))}</h2></div><div class="rows">${cals}</div></section>` : ""}
      <section class="sec"><div class="hrow"><h2>${esc(t("Light check", "Leuchten-Prüfung"))}</h2>${this._info("check")}</div>
        ${this._infoText("check", t("Maestro switches the light on to 30 %, fades it to 80 % in ten seconds and switches it off, and records every answer: how fast, how exact and how often it reports during a fade. That is how Maestro tells its own commands from changes by hand. The light goes back to how it was.", "Maestro schaltet die Leuchte auf 30 % ein, blendet in zehn Sekunden auf 80 % und schaltet aus, und protokolliert jede Rückmeldung: wie schnell, wie genau und wie oft sie während einer Überblendung meldet. So unterscheidet Maestro eigene Befehle von Änderungen von Hand. Danach ist die Leuchte wieder wie vorher."))}
        <div class="row"><select class="field" id="checkLight">${ordered.map((e) => `<option value="${esc(e)}">${esc(friendly(this._hass, e))}</option>`).join("")}</select><button class="btn primary" data-act="check" ${this._check?.running ? "disabled" : ""}>${esc(this._check?.running ? t("Running, about 25 seconds …", "Läuft, etwa 25 Sekunden …") : t("Start the check", "Prüfung starten"))}</button><span class="note">${esc(t("The light will be switched during the check.", "Die Leuchte wird dabei geschaltet."))}</span></div>
        <div id="checkOut">${this._checkHTML()}</div></section>
    </div>`;
  }

  _checkHTML() {
    const t = this._t;
    const c = this._check;
    if (!c || c.running) return "";
    if (c.error) return `<div class="notice">${esc(c.error)}</div>`;
    const s = c.result.summary;
    const rows = c.result.log
      .map((i) => {
        const v = i.values;
        const text = i.kind === "command" ? { on_30: t("Command: on to 30 %", "Befehl: an auf 30 %"), fade_80: t("Command: to 80 % in 10 s", "Befehl: auf 80 % in 10 s"), off: t("Command: off", "Befehl: aus") }[i.text] : t("Report", "Rückmeldung");
        const value = i.kind === "report" ? (v?.on ? `${t("on", "an")}, ${Math.round(v.brightness || 0)} %${v.kelvin ? `, ${v.kelvin} K` : ""}` : t("off", "aus")) : "";
        return `<tr><td>${i.t.toFixed(2)} s</td><td>${esc(text)}</td><td>${esc(value)}</td></tr>`;
      })
      .join("");
    const reading = [
      s.answered ? `${t("answers after", "antwortet nach")} ${s.delay} s` : t("no answer", "keine Antwort"),
      s.rounding !== null ? `${t("rounds by", "rundet um")} ${s.rounding} %` : null,
      c.result.dimmable ? `${s.intermediate} ${t("intermediate reports during the fade", "Zwischenstände während der Überblendung")}` : null,
      s.fade_done_after !== null ? `${t("fade done after", "Überblendung fertig nach")} ${s.fade_done_after} s` : null,
    ]
      .filter(Boolean)
      .join(" · ");
    return `<div class="wrapx"><table class="tbl log"><tbody>${rows}</tbody></table></div><p class="note" style="margin-top:8px"><b>${esc(friendly(this._hass, c.result.entity_id))}:</b> ${esc(reading)}.</p>`;
  }

  // -- pickers from Home Assistant --------------------------------------------------------------------

  _mountPickers() {
    if (!customElements.get("ha-icon-picker") && !this._waitingForPicker && this.shadowRoot.querySelector("[data-field='icon']")) {
      this._waitingForPicker = true;
      loadIconPicker().then((ready) => ready && this._renderMain());
    }
  }

  _onPicker(e) {
    const el = e.target;
    if (el.tagName !== "HA-ICON-PICKER" || el.dataset.tod === undefined) return;
    e.stopPropagation();
    const value = e.detail?.value ?? el.value;
    if (!value || !/^[a-z0-9-]+:[a-z0-9-]+$/.test(value)) return;
    this._edit((w) => (this._todRef(w, el.dataset.tod).icon = value), { preview: false, render: false });
    const tile = el.closest(".r")?.querySelector(".tile ha-icon");
    if (tile) tile.setAttribute("icon", value);
  }

  _todRef(w, ref) {
    return ref === "base" ? w.base : w.times_of_day[Number(ref)];
  }

  // -- events -----------------------------------------------------------------------------------------

  async _onClick(e) {
    const el = e.target.closest("[data-act]");
    if (!el || el.disabled) return;
    if (e.target.closest("[data-stop]") && el.dataset.act === "rule") return;
    const act = el.dataset.act;
    const t = this._t;
    const w = this._w;
    if (act === "menu") {
      this.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }));
    } else if (act === "tab") {
      this._view = el.dataset.v;
      this._month = null;
      this._pick = null;
      this._render();
      window.scrollTo(0, 0);
    } else if (act === "jump") {
      e.preventDefault();
      this.shadowRoot.getElementById(el.dataset.to)?.scrollIntoView({ behavior: "smooth", block: "start" });
    } else if (act === "info") {
      const id = el.dataset.id;
      this._infos.has(id) ? this._infos.delete(id) : this._infos.add(id);
      this._renderMain();
    } else if (act === "more") {
      const id = el.dataset.id;
      this._open.has(id) ? this._open.delete(id) : this._open.add(id);
      this._renderMain();
    } else if (act === "create") {
      const input = this.shadowRoot.getElementById("newName");
      const title = input.value.trim();
      if (!title) return input.focus();
      try {
        const res = await this._hass.callWS({ type: "cloudless_maestro/rhythm/create", title, template: this.shadowRoot.getElementById("newTemplate").value, palette: this.shadowRoot.getElementById("newPalette").value });
        this._creating = false;
        await this._load(res.entry_id);
      } catch (err) {
        this._toast(err?.message || String(err));
      }
    } else if (act === "create-cancel") {
      this._creating = false;
      this._render();
    } else if (act === "confirm") {
      this._confirm = el.dataset.v || null;
      this._renderMain();
    } else if (act === "delete-rhythm") {
      await this._hass.callWS({ type: "cloudless_maestro/rhythm/delete", entry_id: this._r.entry_id });
      this._i = 0;
      await this._load();
    } else if (act === "undo") {
      const last = this._undo.pop();
      if (!last) return;
      this._r.work = JSON.parse(last);
      this._changed();
    } else if (act === "export") {
      const data = { maestro: 1, title: this._r.title, options: w };
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `maestro-${makeKey(this._r.title)}.json`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    } else if (act === "import") {
      this.shadowRoot.getElementById("importFile")?.click();
    } else if (act === "import-cancel") {
      this._import = null;
      this._renderMain();
    } else if (act === "import-new") {
      const imp = this._import;
      try {
        const res = await this._hass.callWS({ type: "cloudless_maestro/rhythm/create", title: imp.title, options: imp.options });
        this._import = null;
        await this._load(res.entry_id);
      } catch (err) {
        this._toast(err?.message || String(err));
      }
    } else if (act === "import-replace") {
      const imp = this._import;
      this._import = null;
      this._edit((work) => Object.assign(work, clone(imp.options)));
    } else if (act === "add-tpl") {
      const tpl = this._templates.find((x) => x.name === el.dataset.name);
      if (!tpl) return;
      this._edit((work) => this._addTod(work, { ...tpl, key: makeKey(tpl.name, this._usedKeys()) }));
    } else if (act === "add-tod") {
      const input = this.shadowRoot.getElementById("newTod");
      const name = input.value.trim();
      if (!name) return input.focus();
      const colors = PALETTES[paletteOf(w)];
      const used = new Set(this._usedKeys().map((k) => this._look(k).color?.toLowerCase()));
      const color = colors.find((c) => !used.has(c)) || colors[w.times_of_day.length % colors.length];
      this._edit((work) => this._addTod(work, { key: makeKey(name, this._usedKeys()), name, icon: "mdi:clock-outline", color }));
    } else if (act === "delete-tod") {
      const key = el.dataset.key;
      this._confirm = null;
      this._edit((work) => {
        work.times_of_day = work.times_of_day.filter((x) => x.key !== key);
        for (const m of work.models) m.entries = m.entries.filter((x) => x.tod !== key);
        for (const r of work.rules) {
          delete r.rows[key];
          for (const d of r.devices) delete d.values[key];
        }
      });
    } else if (act === "color") {
      this._edit((work) => (this._todRef(work, el.dataset.tod).color = el.dataset.c), { preview: false });
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
      const src = this._currentModel();
      this._edit((work) => {
        work.models.push(src ? { ...clone(src), key, name } : { key, name, entries: work.times_of_day.slice(0, 1).map((x) => ({ tod: x.key, at: { kind: "fixed", time: "08:00", next_day: false } })), end: { kind: "fixed", time: "22:00", next_day: false } });
      });
      this._model = key;
      this._renderMain();
      this._fetchPreview();
    } else if (act === "copy-model") {
      const model = this._currentModel();
      const name = `${model.name} ${t("copy", "Kopie")}`;
      const key = makeKey(name, w.models.map((m) => m.key));
      this._edit((work) => work.models.push({ ...clone(model), key, name }));
      this._model = key;
      this._renderMain();
      this._fetchPreview();
    } else if (act === "delete-model") {
      this._confirm = null;
      this._edit((work) => (work.models = work.models.filter((m) => m.key !== this._model)));
      this._model = w.models[0]?.key || null;
      this._renderMain();
      this._fetchPreview();
    } else if (act === "add-entry") {
      const key = this.shadowRoot.getElementById("addEntry").value;
      this._edit((work) => {
        const model = work.models.find((m) => m.key === this._model);
        const last = model.entries.at(-1);
        const time = last?.at.kind === "fixed" ? clockOf(minutesOf(last.at.time) + 60) : "12:00";
        model.entries.push({ tod: key, at: { kind: "fixed", time, next_day: !!last?.at.next_day } });
      });
    } else if (act === "remove-entry") {
      this._edit((work) => work.models.find((m) => m.key === this._model).entries.splice(Number(el.dataset.i), 1));
    } else if (act === "move") {
      this._edit((work) => {
        const list = work.models.find((m) => m.key === this._model).entries;
        const i = Number(el.dataset.i),
          j = i + Number(el.dataset.d);
        [list[i], list[j]] = [list[j], list[i]];
      });
    } else if (act === "preview-today") {
      this._previewDate = localParts(this._hass, new Date().toISOString()).date;
      this._renderMain();
      this._renderLive();
      this._fetchPreview();
      this._fetchStrips();
    } else if (act === "add-link") {
      const cal = Object.keys(this._hass.states).find((x) => x.startsWith("calendar."));
      this._edit((work) => work.calendar_links.push({ calendar: cal, match: "", model: work.models.at(-1)?.key || work.models[0]?.key }), { preview: false });
    } else if (act === "remove-link") {
      this._edit((work) => work.calendar_links.splice(Number(el.dataset.i), 1), { preview: false });
    } else if (act === "move-link") {
      this._edit(
        (work) => {
          const list = work.calendar_links;
          const i = Number(el.dataset.i),
            j = i + Number(el.dataset.d);
          [list[i], list[j]] = [list[j], list[i]];
        },
        { preview: false },
      );
    } else if (act === "refresh-cal") {
      try {
        await this._hass.callWS({ type: "cloudless_maestro/refresh_calendars", entry_id: this._r.entry_id });
        this._toast(t("Calendars read", "Kalender gelesen"));
      } catch (err) {
        this._toast(err?.message || String(err));
      }
    } else if (act === "rule") {
      const id = `rule-${el.dataset.id}`;
      this._open.has(id) ? this._open.delete(id) : this._open.add(id);
      this._pick = null;
      this._renderMain();
    } else if (act === "move-rule") {
      this._edit(
        (work) => {
          const i = work.rules.findIndex((r) => r.id === el.dataset.id),
            j = i + Number(el.dataset.d);
          if (j < 0 || j >= work.rules.length) return;
          [work.rules[i], work.rules[j]] = [work.rules[j], work.rules[i]];
        },
        { preview: false },
      );
    } else if (act === "add-rule" || act === "copy-rule") {
      const src = act === "copy-rule" ? this._rule(el.dataset.id) : null;
      const input = this.shadowRoot.getElementById("newRule");
      const name = src ? `${src.name} ${t("copy", "Kopie")}` : input?.value.trim();
      if (!name) return input?.focus();
      const id = makeKey(name, w.rules.map((r) => r.id));
      this._edit(
        (work) => {
          const rule = src
            ? { ...clone(src), id, name, lights: [], motion: [], buttons: [], lux: null, devices: src.devices.map((d) => ({ entity: d.entity, values: clone(d.values) })) }
            : { id, name, active: true, lights: [], motion: [], buttons: [], manual: true, lux: null, manual_after: "same", external_on: "apply", warn: null, lock: null, rows: this._defaultRows(work), devices: [] };
          work.rules.push(rule);
          this._open.add(`rule-${id}`);
        },
        { preview: false },
      );
      setTimeout(() => this.shadowRoot.querySelector(`[data-act="rule"][data-id="${id}"]`)?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
    } else if (act === "delete-rule") {
      this._confirm = null;
      this._edit((work) => (work.rules = work.rules.filter((r) => r.id !== el.dataset.id)), { preview: false });
    } else if (act === "pick") {
      this._pick = { rule: el.dataset.rule, kind: el.dataset.kind };
      this._pickQuery = "";
      this._renderMain();
      this.shadowRoot.getElementById("pickSearch")?.focus();
    } else if (act === "pick-close") {
      this._pick = null;
      this._renderMain();
    } else if (act === "pick-add") {
      const id = el.dataset.e,
        kind = el.dataset.kind;
      this._edit(
        (work) => {
          const rule = work.rules.find((r) => r.id === el.dataset.rule);
          if (kind === "light") rule.lights.push(id);
          else if (kind === "motion") rule.motion.push(id);
          else if (kind === "button") rule.buttons.push({ entity: id, event: this._hass.states[id]?.attributes?.event_types?.[0] || null });
          else if (kind === "lux") rule.lux = { sensor: id, below: 20 };
          else if (kind === "device") rule.devices.push({ entity: id, values: {} });
        },
        { preview: false },
      );
      if (kind === "lux") this._pick = null;
      this._renderMain();
      const search = this.shadowRoot.getElementById("pickSearch");
      if (search) search.focus();
    } else if (act === "rm-light" || act === "rm-motion") {
      this._edit(
        (work) => {
          const rule = work.rules.find((r) => r.id === el.dataset.rule);
          if (act === "rm-light") rule.lights = rule.lights.filter((x) => x !== el.dataset.e);
          else rule.motion = rule.motion.filter((x) => x !== el.dataset.e);
        },
        { preview: false },
      );
    } else if (act === "rm-button") {
      this._edit((work) => work.rules.find((r) => r.id === el.dataset.rule).buttons.splice(Number(el.dataset.i), 1), { preview: false });
    } else if (act === "rm-lux") {
      this._edit((work) => (work.rules.find((r) => r.id === el.dataset.rule).lux = null), { preview: false });
    } else if (act === "rm-device") {
      this._edit((work) => work.rules.find((r) => r.id === el.dataset.rule).devices.splice(Number(el.dataset.i), 1), { preview: false });
    } else if (act === "preset") {
      this._edit((work) => (this._rowOf(work, el.dataset.rule, el.dataset.tod).brightness = Number(el.dataset.v)), { preview: false });
    } else if (act === "color-none") {
      this._edit((work) => (this._rowOf(work, el.dataset.rule, el.dataset.tod).color = null), { preview: false });
    } else if (act === "row-all") {
      this._edit(
        (work) => {
          const rule = work.rules.find((r) => r.id === el.dataset.rule);
          const src = clone(rule.rows[el.dataset.tod] || {});
          for (const tod of [...work.times_of_day, work.base]) rule.rows[tod.key] = clone(src);
        },
        { preview: false },
      );
      this._toast(t("Row used for all times of day", "Zeile für alle Tageszeiten übernommen"));
    } else if (act === "test") {
      try {
        await this._save();
        await this._hass.callWS({ type: "cloudless_maestro/rule/test", entry_id: this._r.entry_id, rule: el.dataset.rule, time_of_day: el.dataset.tod });
        this._toast(`${this._rule(el.dataset.rule)?.name}: ${this._look(el.dataset.tod).name} ${t("applied", "angewendet")}`);
      } catch (err) {
        this._toast(err?.message || String(err));
      }
    } else if (act === "forget") {
      try {
        await this._hass.callWS({ type: "cloudless_maestro/forget", entry_id: this._r.entry_id, lights: [el.dataset.e] });
        this._renderMain();
      } catch (err) {
        this._toast(err?.message || String(err));
      }
    } else if (act === "sidebar") {
      try {
        const res = await this._hass.callWS({ type: "cloudless_maestro/sidebar", show: !this._sidebar });
        this._sidebar = res.sidebar;
        this._toast(this._sidebar ? t("The page is back in the sidebar after a reload.", "Nach dem Neuladen steht die Seite wieder in der Seitenleiste.") : t("Removed. Reload the page to see the sidebar without it.", "Entfernt. Lade die Seite neu, dann fehlt der Eintrag."));
        this._renderMain();
      } catch (err) {
        this._toast(err?.message || String(err));
      }
    } else if (act === "check") {
      const entity = this.shadowRoot.getElementById("checkLight")?.value;
      if (!entity) return;
      this._check = { running: true };
      this._renderDiag(this.shadowRoot.getElementById("main"));
      try {
        const result = await this._hass.callWS({ type: "cloudless_maestro/light_check", entity_id: entity });
        this._check = { running: false, result };
      } catch (err) {
        this._check = { running: false, error: err?.message || String(err) };
      }
      if (this._view === "diag") this._renderDiag(this.shadowRoot.getElementById("main"));
    } else if (act === "month") {
      const d = Number(el.dataset.d);
      const today = localParts(this._hass, new Date().toISOString()).date;
      if (!d) this._monthStart = `${today.slice(0, 7)}-01`;
      else {
        const [y, m] = this._monthStart.split("-").map(Number);
        this._monthStart = new Date(Date.UTC(y, m - 1 + d, 1)).toISOString().slice(0, 10);
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

  _addTod(work, tod) {
    work.times_of_day.push(tod);
    // Rules: the new time of day starts like the one before it.
    const previous = work.times_of_day.at(-2)?.key;
    for (const r of work.rules) {
      r.rows[tod.key] = clone(r.rows[previous] || { react: "on", brightness: 100, begin: "follow_free" });
    }
  }

  _defaultRows(work) {
    const rows = {};
    for (const tod of work.times_of_day) rows[tod.key] = { react: "on", brightness: 100, color: null, after: null, begin: "follow_free", transition: null, memory: null, forget: false, lux_below: null };
    rows[work.base.key] = { react: "off_only", brightness: null, color: null, after: null, begin: "off", transition: null, memory: null, forget: false, lux_below: null };
    return rows;
  }

  _rowOf(work, ruleId, key) {
    const rule = work.rules.find((r) => r.id === ruleId);
    if (!rule.rows[key]) rule.rows[key] = { react: "on", brightness: 100, color: null, after: null, begin: "follow_free", transition: null, memory: null, forget: false, lux_below: null };
    return rule.rows[key];
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
    if (el.id === "rhythmSel") {
      if (el.value === "new") {
        this._creating = true;
        this._render();
        this.shadowRoot.getElementById("newName")?.focus();
        return;
      }
      this._i = Number(el.value);
      this._resetSelection();
      this._render();
      this._subscribe();
      return;
    }
    if (el.id === "importFile") {
      const file = el.files?.[0];
      if (!file) return;
      file.text().then((text) => {
        try {
          const data = JSON.parse(text);
          const options = data.options || data;
          if (!options.base || !options.models) throw new Error("not a Maestro file");
          this._import = { title: data.title || file.name.replace(/\.json$/i, ""), options };
          this._renderMain();
        } catch {
          this._toast(this._t("This is not a Maestro file.", "Das ist keine Maestro-Datei."));
        }
      });
      el.value = "";
      return;
    }
    if (!w) return;
    const num = (v) => (v === "" || v === null ? null : Number(v));
    if (el.id === "title") {
      const title = el.value.trim();
      if (!title) return;
      this._r.title = title;
      const opt = this.shadowRoot.querySelector(`#rhythmSel option[value="${this._i}"]`);
      if (opt) opt.textContent = title;
      this._changed({ render: false, preview: false });
    } else if (el.dataset.tod !== undefined && el.dataset.field) {
      const field = el.dataset.field;
      if (field === "name" && !el.value.trim()) return;
      if (field === "icon" && !/^[a-z0-9-]+:[a-z0-9-]+$/.test(el.value)) return;
      this._edit((work) => (this._todRef(work, el.dataset.tod)[field] = field === "name" ? el.value.trim() : el.value), { preview: false, render: field !== "name" });
    } else if (el.id === "locHa" || el.id === "locOwn") {
      this._edit((work) => (work.location = el.id === "locHa" ? null : { latitude: this._hass.config.latitude, longitude: this._hass.config.longitude }));
    } else if (el.id === "lat" || el.id === "lon") {
      this._edit((work) => (work.location = { latitude: Number(this.shadowRoot.getElementById("lat").value), longitude: Number(this.shadowRoot.getElementById("lon").value) }), { render: false });
    } else if (el.dataset.default) {
      const f = el.dataset.default;
      this._edit((work) => (work.defaults[f] = f === "warn" ? el.checked : Math.max(0, Math.round(Number(el.value) || 0))), { preview: false, render: false });
    } else if (el.id === "modelName") {
      if (!el.value.trim()) return;
      this._edit((work) => (work.models.find((m) => m.key === this._model).name = el.value.trim()), { preview: false });
    } else if (el.dataset.entry !== undefined) {
      const ref = el.dataset.entry;
      this._edit(
        (work) => {
          const model = work.models.find((m) => m.key === this._model);
          if (ref === "end") {
            model.end = this._setSpec(model.end, el.dataset.field, el);
            if (model.end.kind === "sun" && !model.end.latest) model.end.latest = "23:30";
          } else {
            const entry = model.entries[Number(ref)];
            entry.at = this._setSpec(entry.at, el.dataset.field, el);
          }
        },
        { render: el.dataset.field === "kind" },
      );
    } else if (el.id === "previewDate") {
      if (!el.value) return;
      this._previewDate = el.value;
      this._renderMain();
      this._fetchPreview();
      this._fetchStrips();
    } else if (el.dataset.week) {
      this._edit((work) => (work.week[el.dataset.week] = el.value || null), { render: false, preview: false });
      this.shadowRoot.querySelector(`[data-strip]`) && this._fetchStrips();
      this._renderMain();
    } else if (el.dataset.link !== undefined) {
      this._edit((work) => (work.calendar_links[Number(el.dataset.link)][el.dataset.field] = el.dataset.field === "match" ? el.value.trim() : el.value), { render: false, preview: false });
    } else if (el.dataset.rule && el.dataset.button !== undefined) {
      this._edit((work) => (work.rules.find((r) => r.id === el.dataset.rule).buttons[Number(el.dataset.button)].event = el.value || null), { render: false, preview: false });
    } else if (el.dataset.rule && el.dataset.device !== undefined) {
      this._edit(
        (work) => {
          const device = work.rules.find((r) => r.id === el.dataset.rule).devices[Number(el.dataset.device)];
          const v = el.value;
          if (v === "") delete device.values[el.dataset.tod];
          else device.values[el.dataset.tod] = el.type === "number" ? Number(v) : v;
        },
        { render: false, preview: false },
      );
    } else if (el.dataset.rule && el.dataset.tod) {
      const f = el.dataset.f;
      const render = ["react", "copy_row", "color_mode", "kelvin", "hue"].includes(f);
      this._edit(
        (work) => {
          const row = this._rowOf(work, el.dataset.rule, el.dataset.tod);
          if (f === "forget") row.forget = el.checked;
          else if (f === "copy_row") {
            if (!el.value) return;
            const rule = work.rules.find((r) => r.id === el.dataset.rule);
            Object.assign(row, clone(rule.rows[el.value] || {}));
          } else if (f === "color_mode") row.color = el.value === "rgb" ? { rgb: hueRgb(30) } : { kelvin: 3000 };
          else if (f === "kelvin") row.color = { kelvin: Number(el.value) };
          else if (f === "hue") row.color = { rgb: hueRgb(Number(el.value)) };
          else if (f === "react" || f === "begin") row[f] = el.value;
          else row[f] = num(el.value);
        },
        { preview: false, render },
      );
    } else if (el.dataset.rule) {
      const f = el.dataset.f;
      this._edit(
        (work) => {
          const rule = work.rules.find((r) => r.id === el.dataset.rule);
          if (f === "active" || f === "manual" || f === "warn") rule[f] = el.checked;
          else if (f === "name") {
            if (el.value.trim()) rule.name = el.value.trim();
          } else if (f === "lux_below") rule.lux.below = Number(el.value) || 0;
          else if (f === "manual_after_mode") rule.manual_after = el.value === "minutes" ? 10 : el.value;
          else if (f === "manual_after_minutes") rule.manual_after = Math.max(1, Math.round(Number(el.value) || 1));
          else if (f === "lock") rule.lock = num(el.value);
          else rule[f] = el.value;
        },
        { preview: false, render: f !== "name" && f !== "lux_below" && f !== "lock" && f !== "manual_after_minutes" },
      );
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
    if (el.id === "pickSearch") {
      this._pickQuery = el.value;
      const list = this.shadowRoot.getElementById("pickList");
      const rule = this._rule(this._pick?.rule);
      if (list && rule) list.innerHTML = this._pickListHTML(rule, this._pick.kind);
    } else if (el.dataset.f === "kelvin") {
      const label = el.nextElementSibling;
      if (label) label.textContent = `${el.value} K`;
    } else if (el.dataset.field === "icon" && el.tagName === "INPUT") {
      const tile = el.closest(".r")?.querySelector(".tile ha-icon");
      if (tile && /^[a-z0-9-]+:[a-z0-9-]+$/.test(el.value)) tile.setAttribute("icon", el.value);
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
    this._drag = { key: handle.dataset.handle, m: this._axisMinute(e.clientX), pointer: e.pointerId };
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
    const spec = { kind: "fixed", time: clockOf(m), next_day: m >= 1440 };
    this._edit((work) => {
      const model = work.models.find((x) => x.key === this._model);
      if (key) {
        const entry = model.entries.find((x) => x.tod === key);
        if (entry) entry.at = spec;
      } else model.end = spec;
    });
  }
}

if (!customElements.get("maestro-panel")) customElements.define("maestro-panel", MaestroPanel);
