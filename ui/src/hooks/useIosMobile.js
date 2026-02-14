import { useEffect, useState } from "react";
import { IOS_MOBILE_MEDIA_QUERY, isIosBrowserDevice } from "../constants/segments.js";
import { Capacitor } from "@capacitor/core";

export function useIosMobile() {
  const platform = Capacitor.getPlatform ? Capacitor.getPlatform() : "web";
  const isIosPlatform = platform === "ios";
  const isIosEnvironment = isIosPlatform || isIosBrowserDevice();

  const [isIosMobile, setIsIosMobile] = useState(() => {
    if (!isIosEnvironment || typeof window === "undefined") {
      return false;
    }
    return window.matchMedia(IOS_MOBILE_MEDIA_QUERY).matches;
  });

  useEffect(() => {
    if (!isIosEnvironment || typeof window === "undefined") {
      setIsIosMobile(false);
      return;
    }
    const mediaQuery = window.matchMedia(IOS_MOBILE_MEDIA_QUERY);
    const updateIsIosMobile = () => {
      setIsIosMobile(mediaQuery.matches);
    };
    updateIsIosMobile();
    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener("change", updateIsIosMobile);
      return () => mediaQuery.removeEventListener("change", updateIsIosMobile);
    }
    mediaQuery.addListener(updateIsIosMobile);
    return () => mediaQuery.removeListener(updateIsIosMobile);
  }, [isIosEnvironment]);

  return isIosMobile;
}
