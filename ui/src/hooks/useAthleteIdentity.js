import { useState } from "react";

export const ATHLETE_IDENTITY_KEY = "pyrox.ui.athlete-identity";

function readStoredIdentity() {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(ATHLETE_IDENTITY_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return null;
    const athleteId =
      typeof parsed.athleteId === "string" ? parsed.athleteId.trim() : "";
    const name = typeof parsed.name === "string" ? parsed.name.trim() : "";
    if (!athleteId && !name) return null;
    const identity = {};
    if (athleteId) identity.athleteId = athleteId;
    if (name) identity.name = name;
    if (typeof parsed.setAt === "string") identity.setAt = parsed.setAt;
    return identity;
  } catch {
    return null;
  }
}

function persistIdentity(identity) {
  if (typeof window === "undefined") return;
  try {
    if (identity) {
      window.localStorage.setItem(ATHLETE_IDENTITY_KEY, JSON.stringify(identity));
    } else {
      window.localStorage.removeItem(ATHLETE_IDENTITY_KEY);
    }
  } catch {
    // Storage unavailable — silent fail
  }
}

export function useAthleteIdentity() {
  const [identity, setIdentityState] = useState(readStoredIdentity);

  const setIdentity = (next) => {
    persistIdentity(next);
    setIdentityState(next);
  };

  const clearIdentity = () => setIdentity(null);

  return { identity, setIdentity, clearIdentity };
}
