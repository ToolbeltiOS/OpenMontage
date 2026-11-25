/**
 * Where a timeline event sits, and what its card prints.
 *
 * ITS OWN FILE, AND FREE OF REACT, so the rule can be exercised
 * directly — `tests/composer/test_timeline_dates.py` bundles this with
 * the composer's own esbuild and runs it under node, the same way the
 * props gate runs the zod schemas. A Python restatement of a date
 * formatter would be a second source of truth for the thing under
 * test, which is the bug class this whole gate exists for.
 */
export interface TimelineDate {
  year: number;
  month?: number;
  day?: number;
  /** placed in sequence, with no year printed — see fmtDate */
  undated?: boolean;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/**
 * Where a date sits on the axis. A YEAR IS A WHOLE NUMBER and the fraction
 * is derived from the month and day, which is the whole of this change.
 *
 * Two films got this wrong in opposite directions and both were published.
 * king-tut c009 authored `year: 1922.84` to put "4 Nov 1922" five months
 * along a one-year span: correct placement, and `fmtYear` printed the
 * fraction, so the film reads "AD 1922.84". The atomic-bombings film
 * authored `year: "27 Jul"` — `Math.abs("27 Jul")` is NaN, `pos(NaN)` is
 * NaN, and six cards show "NaN" with every label stacked at the left edge
 * of the frame. Both were asking for a DATE, and there was nowhere to put
 * one.
 */
export const axisValue = (d: TimelineDate): number => {
  const year = Number(d?.year);
  if (!Number.isFinite(year)) return NaN;
  const month = Number.isFinite(Number(d?.month))
    ? Math.min(12, Math.max(1, Number(d.month)))
    : null;
  if (month === null) return year;
  const day = Number.isFinite(Number(d?.day))
    ? Math.min(31, Math.max(1, Number(d.day)))
    : 1;
  // Months are equal twelfths and days equal thirty-firsts of a month.
  // Exact enough to place a tick and not a claim about calendars.
  const sign = year < 0 ? -1 : 1;
  return year + sign * ((month - 1) + (day - 1) / 31) / 12;
};

/**
 * What the card prints. Never a fraction, never NaN: an unusable date
 * prints nothing at all, because a tick with no legible year is better
 * than one labelled "NaN".
 */
export const fmtDate = (d: TimelineDate): string => {
  // A marker the edit did not date prints nothing. It carries the date of
  // the event it follows so that it has somewhere to sit on the axis, and
  // printing that date would attribute a moment to it that nobody claimed.
  if (d?.undated) return "";
  const year = Number(d?.year);
  if (!Number.isFinite(year)) return "";
  const n = Math.round(Math.abs(year));
  const era = year < 0 ? `${n} BC` : `AD ${n}`;
  const month = Number(d?.month);
  if (!Number.isFinite(month) || month < 1 || month > 12) return era;
  const name = MONTHS[Math.round(month) - 1];
  const day = Number(d?.day);
  const stem = Number.isFinite(day) && day >= 1 && day <= 31
    ? `${Math.round(day)} ${name}`
    : name;
  return year < 0 ? `${stem} ${n} BC` : `${stem} ${n}`;
};
