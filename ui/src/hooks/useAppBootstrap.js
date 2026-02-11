import { useCallback, useEffect, useRef, useState } from "react";

const MIN_BOOT_MS = 420;
const NETWORK_TIMEOUT_MS = 6500;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const readStoredSession = () => {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const value = window.localStorage.getItem("pyrox.auth.session");
    if (!value) {
      return null;
    }
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch (error) {
    return null;
  }
};

const checkHealth = async (apiBase) => {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), NETWORK_TIMEOUT_MS);
  try {
    const response = await fetch(`${apiBase}/api/health`, {
      method: "GET",
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new Error(`Service returned ${response.status}.`);
    }
    await response.json();
  } finally {
    clearTimeout(timeoutId);
  }
};

export const useAppBootstrap = (apiBase) => {
  const isMountedRef = useRef(true);
  const [state, setState] = useState({
    isBootstrapping: true,
    isReady: false,
    progress: 0,
    status: "Starting app...",
    warning: "",
  });

  const runBootstrap = useCallback(async () => {
    const startedAt = Date.now();
    setState({
      isBootstrapping: true,
      isReady: false,
      progress: 0,
      status: "Checking session...",
      warning: "",
    });

    const steps = [
      {
        label: "Checking session...",
        run: async () => {
          readStoredSession();
        },
      },
      {
        label: "Connecting to race service...",
        run: async () => {
          await checkHealth(apiBase);
        },
      },
      {
        label: "Preparing dashboards...",
        run: async () => {
          if (typeof window !== "undefined") {
            window.localStorage.getItem("pyrox.ui.last-mode");
          }
        },
      },
    ];

    let warning = "";
    for (let index = 0; index < steps.length; index += 1) {
      const step = steps[index];
      const progress = index / steps.length;
      if (isMountedRef.current) {
        setState((prev) => ({
          ...prev,
          status: step.label,
          progress,
        }));
      }
      try {
        await step.run();
      } catch (error) {
        warning =
          error?.name === "AbortError"
            ? "Connection timed out. You can still browse the app."
            : error?.message || "Unable to verify service connection.";
      }
    }

    const elapsed = Date.now() - startedAt;
    if (elapsed < MIN_BOOT_MS) {
      await sleep(MIN_BOOT_MS - elapsed);
    }

    if (isMountedRef.current) {
      setState({
        isBootstrapping: false,
        isReady: true,
        progress: 1,
        status: "Ready",
        warning,
      });
    }
  }, [apiBase]);

  useEffect(() => {
    isMountedRef.current = true;
    runBootstrap();
    return () => {
      isMountedRef.current = false;
    };
  }, [runBootstrap]);

  return {
    ...state,
    retryBootstrap: runBootstrap,
  };
};
