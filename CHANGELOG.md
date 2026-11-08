# Changelog

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
