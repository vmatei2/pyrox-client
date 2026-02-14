import { Capacitor, registerPlugin } from "@capacitor/core";

const HapticsPlugin = registerPlugin("Haptics");

export const triggerSelectionHaptic = async () => {
  try {
    if (Capacitor.isNativePlatform && Capacitor.isNativePlatform()) {
      await HapticsPlugin.selectionChanged();
      return;
    }
  } catch (error) {
    // Fall back silently.
  }

  if (typeof navigator !== "undefined" && typeof navigator.vibrate === "function") {
    navigator.vibrate(8);
  }
};
