import { formatTimeWindowLabel } from "./formatters.js";

export const buildReportFilename = (race) => {
  const parts = [
    race?.name,
    race?.event_name || race?.event_id,
    race?.location,
    race?.season,
    race?.year,
  ]
    .filter(Boolean)
    .join("-");
  const slug = parts.replace(/[^a-z0-9]+/gi, "-").replace(/(^-|-$)/g, "").toLowerCase();
  return `pyrox-report-${slug || "race"}.pdf`;
};

export const buildComparisonFilename = (baseRace, compareRace) => {
  const baseParts = [
    baseRace?.name,
    baseRace?.event_name || baseRace?.event_id,
    baseRace?.location,
    baseRace?.season,
    baseRace?.year,
  ]
    .filter(Boolean)
    .join("-");
  const compareParts = [
    compareRace?.name,
    compareRace?.event_name || compareRace?.event_id,
    compareRace?.location,
    compareRace?.season,
    compareRace?.year,
  ]
    .filter(Boolean)
    .join("-");
  const combined = [baseParts, compareParts].filter(Boolean).join("-vs-");
  const slug = combined
    .replace(/[^a-z0-9]+/gi, "-")
    .replace(/(^-|-$)/g, "")
    .toLowerCase();
  return `pyrox-compare-${slug || "races"}.pdf`;
};

export const buildReportHelpContent = (timeWindowValue) => {
  const timeWindowLabel = formatTimeWindowLabel(timeWindowValue);
  return {
    rankings: {
      title: "How rankings are calculated",
      summary: "Lower time is better. Rankings and percentiles are computed on total time.",
      bullets: [
        "Event cohort: same location + division + gender + age group.",
        "Season cohort: same season + division + gender + age group.",
        "Overall cohort: all seasons for the same division + gender + age group.",
      ],
      formula: "percentile = 1 - (rank - 1) / (cohort_size - 1)",
    },
    age_group_distributions: {
      title: "How age group distributions work",
      summary: "Histograms show total times for your demographic cohort with your race marked.",
      bullets: [
        "Bins are equal-width ranges across the observed min and max time.",
        "The marker line is your total time.",
        "n shows how many race results are in the cohort.",
      ],
    },
    split_percentile_lines: {
      title: "How split percentile lines work",
      summary: "Each point is your percentile for one split. Higher percentile means faster relative performance.",
      bullets: [
        "Cohort line uses the age-group cohort at the same location.",
        "Time-window line uses the same location + season and similar finish times.",
        "Missing split values are left blank and lines break across gaps.",
      ],
      formula: "percentile = 1 - (rank - 1) / (cohort_size - 1)",
    },
    splits_table: {
      title: "How split table values are calculated",
      summary: "Each row compares one split against the selected cohorts.",
      bullets: [
        "Rank is your position within the split cohort (lower split time ranks higher).",
        "Percentile is your standing vs the age-group split cohort.",
        `Window percentile uses ${timeWindowLabel} around your total time.`,
      ],
    },
    age_group_stats: {
      title: "How age group stats are calculated",
      summary: "Summary stats use total_time_min across your age-group cohort.",
      bullets: [
        "Best time is the minimum total time.",
        "Median is the middle value when times are sorted.",
        "90th percentile is the time at quantile 0.90.",
      ],
    },
    time_window_stats: {
      title: "How time window stats are calculated",
      summary: `Summary stats are computed on athletes within ${timeWindowLabel}.`,
      bullets: [
        "Scope: same location + season.",
        "Filter: total_time_min between athlete_time - window and athlete_time + window.",
        "Stats shown are count, median, best, and 90th percentile.",
      ],
    },
  };
};
