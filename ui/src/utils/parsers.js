export const toNumber = (value) => {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed) {
      return null;
    }
    if (trimmed.includes(":")) {
      const parts = trimmed.split(":").map((part) => part.trim());
      if (parts.some((part) => part === "")) {
        return null;
      }
      const numbers = parts.map((part) => Number(part));
      if (numbers.some((number) => !Number.isFinite(number))) {
        return null;
      }
      if (numbers.length === 2) {
        const [minutes, seconds] = numbers;
        return minutes + seconds / 60;
      }
      if (numbers.length === 3) {
        const [hours, minutes, seconds] = numbers;
        return hours * 60 + minutes + seconds / 60;
      }
      return null;
    }
    const numberValue = Number(trimmed);
    return Number.isFinite(numberValue) ? numberValue : null;
  }
  const numberValue = Number(value);
  return Number.isFinite(numberValue) ? numberValue : null;
};

export const normalizeSplitKey = (value) => {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value).trim().toLowerCase().replace(/[^a-z0-9]+/g, "");
};

export const buildSplitTimeMap = (splits) => {
  const map = new Map();
  if (!Array.isArray(splits)) {
    return map;
  }
  splits.forEach((split) => {
    const key = normalizeSplitKey(split.split_name);
    if (!key) {
      return;
    }
    map.set(key, {
      name: split.split_name,
      time: toNumber(split.split_time_min),
    });
  });
  return map;
};

export const pickSegmentValue = (segment, race, splitMap) => {
  if (splitMap?.has(segment.key)) {
    const splitValue = splitMap.get(segment.key)?.time;
    if (Number.isFinite(splitValue)) {
      return splitValue;
    }
  }
  return toNumber(race?.[segment.column]);
};

export const parseError = async (response) => {
  try {
    const data = await response.json();
    return data?.detail || response.statusText;
  } catch (error) {
    return response.statusText || "Request failed.";
  }
};
