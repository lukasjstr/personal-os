import { useEffect, useCallback } from "react";

export function useAutoRefresh(callback: () => void, intervalMs: number = 30000) {
  const stableCallback = useCallback(callback, [callback]);

  useEffect(() => {
    const id = setInterval(stableCallback, intervalMs);
    return () => clearInterval(id);
  }, [stableCallback, intervalMs]);
}
