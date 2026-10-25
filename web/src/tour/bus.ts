// A tiny event bus between the app and the guided demo.
// The app emits facts ("fleet:registered", "claim:done"); the tour waits for them and sends commands ("cmd:explore:play").
type Handler = (payload?: any) => void;
const handlers = new Map<string, Set<Handler>>();
const seen = new Map<string, any>();

export const bus = {
  emit(event: string, payload?: any) {
    seen.set(event, payload);
    handlers.get(event)?.forEach((h) => h(payload));
  },
  on(event: string, h: Handler) {
    if (!handlers.has(event)) handlers.set(event, new Set());
    handlers.get(event)!.add(h);
    return () => { handlers.get(event)?.delete(h); };
  },
  /** Resolve on the next emission (or immediately if it already happened since the last clear). */
  wait(event: string, timeoutMs = 0): Promise<any> {
    if (seen.has(event)) return Promise.resolve(seen.get(event));
    return new Promise((resolve, reject) => {
      const off = bus.on(event, (p) => { off(); if (t) clearTimeout(t); resolve(p); });
      const t = timeoutMs ? setTimeout(() => { off(); reject(new Error(`timed out waiting for ${event}`)); }, timeoutMs) : 0;
    });
  },
  clear(...events: string[]) { events.forEach((e) => seen.delete(e)); },
};

const visible = (el: Element | null): el is HTMLElement => {
  if (!el) return false;
  const r = (el as HTMLElement).getBoundingClientRect();
  return r.width > 0 && r.height > 0;
};

/** Wait until a matching element is in the DOM and visible. Uses DOM mutations, not fixed delays. */
export function waitForElement(selector: string, timeoutMs = 20000): Promise<HTMLElement | null> {
  return new Promise((resolve) => {
    const found = document.querySelector(selector);
    if (visible(found)) return resolve(found);
    const obs = new MutationObserver(() => {
      const el = document.querySelector(selector);
      if (visible(el)) { obs.disconnect(); clearTimeout(t); requestAnimationFrame(() => resolve(el)); }
    });
    obs.observe(document.body, { childList: true, subtree: true, attributes: true });
    const t = setTimeout(() => { obs.disconnect(); resolve(null); }, timeoutMs);
  });
}

/** Two animation frames: lets React commit and the browser lay out before the spotlight measures. */
export const settle = () => new Promise<void>((r) => requestAnimationFrame(() => requestAnimationFrame(() => r())));
