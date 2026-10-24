import { useEffect, useEffectEvent, useState } from "react";

export interface Async<T> {
  data: T | undefined;
  error: Error | undefined;
  loading: boolean;
}

/**
 * Fetch with abort-on-change. While a new request is in flight the previous data is kept,
 * so charts hold their last render instead of flashing a skeleton. ``deps`` must be
 * JSON-serialisable (they form the request key).
 */
export function useAsync<T>(load: (signal: AbortSignal) => Promise<T>, deps: unknown[]): Async<T> {
  const key = JSON.stringify(deps);
  const [state, setState] = useState<{ key: string | null; data?: T; error?: Error }>({ key: null });
  const run = useEffectEvent((signal: AbortSignal) => load(signal));

  useEffect(() => {
    const ctrl = new AbortController();
    run(ctrl.signal).then(
      (data) => {
        if (!ctrl.signal.aborted) setState({ key, data });
      },
      (error: unknown) => {
        if (!ctrl.signal.aborted)
          setState((s) => ({ key, data: s.data, error: error instanceof Error ? error : new Error(String(error)) }));
      },
    );
    return () => ctrl.abort();
  }, [key]);

  return { data: state.data, error: state.key === key ? state.error : undefined, loading: state.key !== key };
}

/** Track an element's width so SVG charts can lay out for the space they actually have. */
export function useWidth<E extends HTMLElement>(fallback = 640): [(el: E | null) => void, number] {
  const [el, setEl] = useState<E | null>(null);
  const [width, setWidth] = useState(fallback);
  useEffect(() => {
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width;
      if (w) setWidth((prev) => (Math.abs(prev - w) > 1 ? Math.round(w) : prev));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [el]);
  return [setEl, width];
}
