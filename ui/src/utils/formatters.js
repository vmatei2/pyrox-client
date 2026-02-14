import { toNumber } from "./parsers.js";

export const formatTimeWindowLabel = (value) => {
  const minutes = Number(value);
  if (!Number.isFinite(minutes) || minutes <= 0) {
    return "the selected +/- time window";
  }
  return `+/- ${minutes} min`;
};

export const formatMinutes = (value) => {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const minutesValue = Number(value);
  if (!Number.isFinite(minutesValue)) {
    return "-";
  }
  const totalSeconds = Math.max(0, Math.round(minutesValue * 60));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
};

export const formatDurationMinutes = (value) => {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const minutesValue = Number(value);
  if (!Number.isFinite(minutesValue)) {
    return "-";
  }
  const totalSeconds = Math.round(Math.abs(minutesValue) * 60);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
};

export const formatDeltaMinutes = (value) => {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const minutesValue = Number(value);
  if (!Number.isFinite(minutesValue)) {
    return "-";
  }
  const formatted = formatDurationMinutes(minutesValue);
  if (formatted === "-") {
    return "-";
  }
  if (minutesValue === 0) {
    return formatted;
  }
  return `${minutesValue > 0 ? "+" : "-"}${formatted}`;
};

export const formatPercent = (value) => {
  const percentValue = Number(value);
  if (!Number.isFinite(percentValue)) {
    return "-";
  }
  return `${(percentValue * 100).toFixed(1)}%`;
};

export const formatLabel = (value) => {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return String(value);
};

export const sumTimes = (...values) => {
  const numbers = values.map(toNumber);
  if (numbers.some((number) => number === null)) {
    return null;
  }
  return numbers.reduce((total, number) => total + number, 0);
};
