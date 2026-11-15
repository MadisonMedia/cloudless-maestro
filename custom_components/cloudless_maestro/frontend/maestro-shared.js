// Shared by the Maestro card and the Maestro page: language, times, colors and the day timeline.

export const esc = (s) =>
  String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
export const clamp = (v, a, b) => Math.min(b, Math.max(a, v));

export const langOf = (hass) => (hass?.locale?.language || hass?.language || "en").split("-")[0];
export const tr = (hass) => {
  const de = langOf(hass) === "de";
  return (en, german) => (de ? german : en);
};

// Maestro's times are wall-clock times of the Home Assistant server.
export const tzOf = (hass) => hass?.config?.time_zone || Intl.DateTimeFormat().resolvedOptions().timeZone;

const formatters = new Map();
function formatter(lang, tz, opts) {
  const key = `${lang}|${tz}|${JSON.stringify(opts)}`;
  if (!formatters.has(key)) formatters.set(key, new Intl.DateTimeFormat(lang, { timeZone: tz, ...opts }));
  return formatters.get(key);
}
export const fmtTime = (hass, iso) =>
  iso ? formatter(langOf(hass), tzOf(hass), { hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(new Date(iso)) : "";
export const fmtDate = (hass, iso, opts = { weekday: "short", day: "numeric", month: "short" }) =>
  formatter(langOf(hass), tzOf(hass), opts).format(new Date(iso.length === 10 ? `${iso}T12:00:00Z` : iso));
export const fmtDuration = (hass, minutes) => {
  const t = tr(hass);
  const h = Math.floor(minutes / 60),
    m = Math.round(minutes % 60);
  if (!h) return `${m} min`;
  return m ? `${h} ${t("h", "Std.")} ${m} min` : `${h} ${t(h === 1 ? "hour" : "hours", h === 1 ? "Stunde" : "Stunden")}`;
};

// The local date (YYYY-MM-DD) and clock time (HH:MM) of a moment in the server's time zone.
export function localParts(hass, iso) {
  const parts = formatter("en-CA", tzOf(hass), {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(iso));
  const get = (type) => parts.find((p) => p.type === type)?.value;
  return { date: `${get("year")}-${get("month")}-${get("day")}`, time: `${get("hour")}:${get("minute")}` };
}
export const addDays = (isoDate, n) => {
  const d = new Date(`${isoDate}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
};
export const minutesOf = (clock) => {
  const [h, m] = clock.split(":").map(Number);
  return h * 60 + m;
};
export const clockOf = (minutes) => {
  const m = ((Math.round(minutes) % 1440) + 1440) % 1440;
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
};

// The same rule as model.make_key: a stable key from a name.
export function makeKey(name, taken = []) {
  const german = { ä: "ae", ö: "oe", ü: "ue", ß: "ss", Ä: "ae", Ö: "oe", Ü: "ue" };
  let base = String(name)
    .replace(/[äöüßÄÖÜ]/g, (c) => german[c])
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 36);
  if (!base) base = "item";
  if (!/^[a-z0-9]/.test(base)) base = `x${base}`;
  const used = new Set(taken);
  let key = base,
    n = 2;
  while (used.has(key)) key = `${base}_${n++}`;
  return key;
}

// -- colors -------------------------------------------------------------------------------------------

export const hexRgb = (h) => [1, 3, 5].map((i) => parseInt(String(h).slice(i, i + 2), 16) || 0);
const lin = (c) => {
  c /= 255;
  return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
};
export const luminance = (hex) => {
  const [r, g, b] = hexRgb(hex);
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
};
// Text on a colored segment: dark on light colors, white on dark ones.
export const inkOn = (hex) => (luminance(hex) > 0.36 ? "#14181f" : "#ffffff");

// Uses the color actually behind the element, because a theme can be dark without being the dark mode.
export function isDark(el, hass) {
  const bg = el ? getComputedStyle(el).backgroundColor : "";
  if (/^rgba?\(/.test(bg)) {
    const parts = bg.match(/[\d.]+/g).map(Number);
    if (parts[3] === undefined || parts[3] >= 0.5) return (0.299 * parts[0] + 0.587 * parts[1] + 0.114 * parts[2]) / 255 < 0.45;
  }
  return !!hass?.themes?.darkMode;
}

export const icon = (name, size = 20) =>
  name ? `<ha-icon icon="${esc(name)}" style="--mdc-icon-size:${size}px" aria-hidden="true"></ha-icon>` : "";

// -- the timeline -------------------------------------------------------------------------------------

export const TIMELINE_STYLE = `
.tl { position: relative; padding-bottom: 22px; user-select: none; -webkit-user-select: none; }
.tl-bar { position: relative; height: 38px; border-radius: 10px; overflow: hidden; background: var(--mae-well); }
.tl-seg { position: absolute; top: 0; bottom: 0; display: flex; align-items: center; gap: 4px; padding: 0 7px; overflow: hidden; white-space: nowrap; font-size: 12.5px; font-weight: 600; border-right: 2px solid var(--mae-surface); box-sizing: border-box; }
.tl-seg.base { font-weight: 500; }
.tl-seg span { overflow: hidden; text-overflow: ellipsis; }
.tl-seg.past { filter: saturate(.55); opacity: .7; }
.tl-now { position: absolute; top: -4px; height: 46px; width: 2px; margin-left: -1px; background: var(--mae-ink); border-radius: 2px; pointer-events: none; }
.tl-now::before { content: ""; position: absolute; top: -4px; left: -4px; width: 10px; height: 10px; border-radius: 50%; background: var(--mae-ink); }
.tl-tick { position: absolute; bottom: 0; transform: translateX(-50%); font-size: 11.5px; color: var(--mae-muted); font-variant-numeric: tabular-nums; white-space: nowrap; border: 0; background: transparent; padding: 1px 3px; border-radius: 5px; line-height: 1.3; }
button.tl-tick { color: var(--mae-ink); cursor: pointer; border-bottom: 1px solid var(--mae-line); border-radius: 0; padding-bottom: 0; }
button.tl-tick:hover, button.tl-tick.sel { background: var(--mae-accent-soft); }
.tl-tick.adj { color: var(--mae-accent); font-weight: 650; }
.tl-day { position: absolute; top: 0; bottom: 0; border-left: 1px dashed var(--mae-muted); opacity: .6; pointer-events: none; }
`;

// segments: [{key, start, end, day}], look(key) -> {name, icon, color}.
// boundary(seg) -> {clickable, adjusted, id} for the start of a segment, or null.
export function timelineHTML({ hass, segments, start, end, now, look, boundary = () => null, selected = null, base }) {
  const t0 = new Date(start).getTime(),
    t1 = new Date(end).getTime(),
    span = Math.max(1, t1 - t0);
  const pos = (iso) => clamp(((new Date(iso).getTime() - t0) / span) * 100, 0, 100);
  const nowMs = now ? new Date(now).getTime() : null;
  let bars = "",
    ticks = "",
    lastTickPos = -100;
  for (const seg of segments) {
    const a = pos(seg.start),
      b = pos(seg.end);
    if (b <= a) continue;
    const item = look(seg.key) || { name: seg.key, color: "#7a8599" };
    const color = item.color || "#7a8599";
    const past = nowMs !== null && new Date(seg.end).getTime() <= nowMs;
    const wide = b - a > 9;
    bars += `<div class="tl-seg${seg.key === base ? " base" : ""}${past ? " past" : ""}" style="left:${a}%;width:${b - a}%;background:${esc(color)};color:${inkOn(color)}" title="${esc(item.name)} · ${esc(fmtTime(hass, seg.start))}–${esc(fmtTime(hass, seg.end))}">${wide ? `${icon(item.icon, 15)}<span>${esc(item.name)}</span>` : ""}</div>`;
    if (a > 0.5 && a - lastTickPos > 7) {
      const info = boundary(seg);
      const label = esc(fmtTime(hass, seg.start));
      const cls = `tl-tick${info?.adjusted ? " adj" : ""}${info && selected === info.id ? " sel" : ""}`;
      ticks += info?.clickable
        ? `<button class="${cls}" style="left:${a}%" data-act="tick" data-id="${esc(info.id)}" title="${esc(item.name)}">${label}</button>`
        : `<span class="${cls}" style="left:${a}%">${label}</span>`;
      lastTickPos = a;
    }
  }
  const nowMark = nowMs !== null && nowMs >= t0 && nowMs <= t1 ? `<div class="tl-now" style="left:${pos(now)}%"></div>` : "";
  return `<div class="tl"><div class="tl-bar">${bars}</div>${nowMark}${ticks}</div>`;
}

// -- names and pickers --------------------------------------------------------------------------------

export const friendly = (hass, entityId) => hass?.states?.[entityId]?.attributes?.friendly_name || entityId;

// The room of an entity, through its own area or its device's.
export function areaOf(hass, entityId) {
  const entry = hass?.entities?.[entityId];
  const areaId = entry?.area_id || (entry?.device_id ? hass?.devices?.[entry.device_id]?.area_id : null);
  return areaId ? hass?.areas?.[areaId]?.name || "" : "";
}

// Home Assistant loads its icon picker on demand. Asking a card editor for it brings it in.
export async function loadIconPicker() {
  if (customElements.get("ha-icon-picker")) return true;
  try {
    const helpers = await window.loadCardHelpers?.();
    const card = helpers?.createCardElement({ type: "button", entity: "light.none" });
    await card?.constructor?.getConfigElement?.();
  } catch {
    // Without the helpers the picker arrives whenever Home Assistant loads it for something else.
  }
  await customElements.whenDefined("ha-icon-picker");
  return true;
}

// The two palettes of the templates: Home Assistant's own colors and deep earth tones.
export const PALETTES = {
  ha: ["#ff9800", "#ffc107", "#03a9f4", "#009688", "#e91e63", "#673ab7", "#37474f", "#4caf50", "#00bcd4", "#f44336", "#9c27b0", "#607d8b"],
  earth: ["#c2410c", "#b45309", "#0f766e", "#4d7c0f", "#86198f", "#3730a3", "#1f2937", "#9a3412", "#0e7490", "#b91c1c", "#6d28d9", "#374151"],
};
export const paletteOf = (options) => (PALETTES.earth.includes(String(options?.base?.color || "").toLowerCase()) ? "earth" : "ha");

// A hue on the color wheel as rgb, fully saturated, for the color row of a rule.
export function hueRgb(h) {
  const f = (n) => {
    const k = (n + h / 60) % 6;
    return Math.round(255 * (1 - Math.max(0, Math.min(k, 4 - k, 1))));
  };
  return [f(5), f(3), f(1)];
}
export function rgbHue([r, g, b]) {
  const max = Math.max(r, g, b),
    min = Math.min(r, g, b),
    d = max - min;
  if (!d) return 0;
  let h = max === r ? (g - b) / d + (g < b ? 6 : 0) : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return Math.round(h * 60) % 360;
}
export const kelvinColor = (k) => {
  const x = Math.max(0, Math.min(1, (k - 2000) / 4500));
  return `color-mix(in srgb, #ff9d3c ${Math.round((1 - x) * 100)}%, #bcd8ff)`;
};
