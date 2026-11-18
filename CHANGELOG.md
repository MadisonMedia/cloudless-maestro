# Changelog

## 0.1.0b4

Restart Home Assistant after updating, then reload the browser or app once.

### Added

- **Missed actions follow.** An action with an offset runs once for each begin or end of its time of day; a pinned time of day is the same occasion when it overlaps or touches the planned one, and one of its own otherwise. When its moment is missed, because Home Assistant was not running or because the time was moved into the past, it runs as soon as possible while the time of day that begins at its edge is still running. The log shows it as caught up, with the planned time. Moving the time later after an action has run does not run it again. New actions and rules switched on again start with the moments still to come.

### Changed

- Switching on by motion, button, by hand or with **Test** is quick. The default transition applies to lights that are on and follow a new time of day; a transition set in a row still applies to both.

### Fixed

- An open settings page saved its old copy of the settings and so undid changes made elsewhere, for example a rule paused with its switch. The page now takes over such changes, and a save that would overwrite them is refused with a message.
- The same goes for the rhythm's name: an open page no longer overwrites a name changed elsewhere.

## 0.1.0b3

Restart Home Assistant after updating, then reload the browser or app once so the page loads anew. Devices set up in 0.1.0b2 become actions at the start of their time of day and keep working.

### Added

- **Wake-up light: fade to the end.** A row can run its lights from one brightness to another over the whole time of day, by default to the next time of day's brightness, white tones included. Lights and Crescendo objects fade by themselves; long fades go in parts, lights without their own fade in small steps. A change by hand stops the fade, **Resume** in the card or the action `cloudless_maestro.resume_fade` continues it. Pinning the running time of day holds it, a moved end is followed, and a restart goes on where the fade is.
- **Actions at a chosen moment:** at, before or after the start or the end of a time of day, with an offset in minutes, for example the heating 60 minutes before wake-up or the blind at the end of the evening.
- **A search with kinds and rooms** for lights, triggers and devices, as in Crescendo. Crescendo objects come first and are chosen by default. Contacts and other binary sensors can be triggers.
- The diagnostics list running fades and the coming actions.

### Changed

- The rules' defaults stand in rows, each with what it means.
- “+1” is now “after midnight”, and the timeline names midnight.
- Explanations use the full width of the page.
- The column “Off after” is called “Time until off” and explains when it counts: from the moment no sensor sees anybody, or from switching on with a button.
- A Crescendo object's buttons are suggestions in the position field; a rule with only Crescendo objects shows no color column.

### Fixed

- Icons chosen with Home Assistant's icon picker were not saved. The picker reports its choice only on itself; each picker now has its own listener.
- Maestro's own sensors were offered as triggers.

## 0.1.0b2

Restart Home Assistant after updating, then reload the browser or app once so the page loads anew. Settings from 0.1.0b1 keep working; the transition per time of day became a default of the rules.

### Added

- **Rules.** A rule has lights, triggers and one row of values per time of day. Motion or presence sensors switch on and, after the time in the row, off again, with a short dimming as a warning first. Buttons toggle. A light switched on by hand gets the values of the time of day. A light sensor can limit switching on to when it is dark. At the start of a time of day, lights that are on follow the new row, stay as they are, or go off, as the row says.
- **Memory.** When somebody changes a light by hand, Maestro remembers that: within the memory time the light comes back with those values, afterwards with the row again. The card and the diagnostics list such lights, with a way to forget.
- **Devices and actions at the start of a time of day.** A blind gets its position, a thermostat its temperature, a speaker its volume, a switch on or off; a scene or script starts.
- **Crescendo objects** are controlled through Crescendo's own actions, with Maestro as the source, with the object's buttons as presets for the position, and with the switch-on position kept up to date.
- A switch per rule to pause it, and the actions `cloudless_maestro.toggle_rule` and `cloudless_maestro.forget`.
- **Triggers with an offset:** a time of day begins or ends, so many minutes before the planned time or after.
- **The light check** under Diagnostics: Maestro switches a light on, fades it and switches it off, and shows how fast, how exactly and how often the light answers.
- **Export and import** of a rhythm as a file, **Undo** on the settings page, and a choice of colors when creating a rhythm: Home Assistant's colors or earth tones.
- The entry in the sidebar can be removed and brought back under General.

### Changed

- **The settings page is rebuilt** after Crescendo's: the rhythm is chosen in the header, a jump bar on the left leads to the sections, explanations sit behind a small **i**, settings of a row open in place under **More**, and a bar at the bottom shows the time of day now and the preview date. Every day model, every weekday and every date in the month view shows the day as a small strip.
- Colors come from a palette instead of the browser's color picker. New rhythms use Home Assistant's colors; the earlier colors stay on existing rhythms.
- Diagnostics show the state now, the rules and the lights set by hand above the log.

## 0.1.0b1

First public beta with the first part of Maestro: the times of day. Light rules follow in the next versions.

### Added

- Rhythms: independent daily schedules, each a device in Home Assistant.
- Times of day with name, icon, color and a stable key, and a base state between days.
- Day models with fixed start times or times following the sun, with offset, earliest and latest, and times after midnight.
- A week plan, and calendar links that set the day model on the dates of calendar events, for example public holidays or shift plans.
- Pinning a time of day until the next change, for a duration, until a time, until the next day or until reset. A duration or a time ends when the next day begins at the latest.
- Day adjustments for single dates, also in advance. They store only what differs from the model.
- Sensors for the time of day, today's model, the next change and the progress, a select to pin, and a binary sensor for overrides.
- Device triggers and conditions, actions, and the event `cloudless_maestro_changed`.
- A card with a full and a compact variant, and a settings page with a preview for summer and winter, a month view and diagnostics.
- German and English.
