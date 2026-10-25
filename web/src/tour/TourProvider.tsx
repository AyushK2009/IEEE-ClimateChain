import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { STATUS, useJoyride } from "react-joyride";
import type { Scenario } from "../api";
import { useStore } from "../store";
import { bus } from "./bus";
import { buildSteps, CHAPTERS } from "./steps";
import { tourStatus } from "./state";
import { TourLoader, TourTooltip, type StepData } from "./TourTooltip";

type Tour = { active: boolean; scenario: Scenario | null; index: number; size: number; chapter: string; start: () => void; exit: () => void };
const Ctx = createContext<Tour>({ active: false, scenario: null, index: 0, size: 0, chapter: "", start: () => {}, exit: () => {} });
export const useTour = () => useContext(Ctx);

export function TourProvider({ children }: { children: ReactNode }) {
  const store = useStore();
  const [run, setRun] = useState(false);
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const scRef = useRef(scenario); scRef.current = scenario;
  const mRef = useRef(store.market); mRef.current = store.market;
  const refreshRef = useRef(store.refresh); refreshRef.current = store.refresh;
  const flags = useRef({ advanced: false, fraudNet: null as number | null });
  const waited = useRef(new Set<string>());

  const steps = useMemo(() => buildSteps({
    scenario: () => scRef.current, setScenario, market: () => mRef.current, refresh: () => refreshRef.current(), flags,
  }), []);

  const { Tour, controls, state } = useJoyride({
    continuous: true, run, steps, tooltipComponent: TourTooltip, loaderComponent: TourLoader,
    options: {
      zIndex: 1000, overlayColor: "rgba(16, 42, 58, 0.52)", spotlightRadius: 10, overlayClickAction: false, dismissKeyAction: false,
      beforeTimeout: 0, targetWaitTimeout: 6000, scrollOffset: 90, buttons: ["back", "primary", "skip"], loaderDelay: 250,
    },
    onEvent: (data, ctl) => {
      if (data.type === "tooltip") {
        // Steps that wait for a real interaction advance themselves when the app reports it happened.
        const d = (data.step?.data ?? {}) as StepData;
        const key = `${data.index}:${d.wait}`;
        if (d.wait && !waited.current.has(key)) {
          waited.current.add(key);
          const idx = data.index;
          bus.wait(d.wait).then(() => { if (ctl.info().index === idx) ctl.next(); });
        }
      }
      if (data.status === STATUS.FINISHED || data.status === STATUS.SKIPPED) {
        setRun(false);
        if (data.status === STATUS.FINISHED) window.location.hash = "/explore";
      }
    },
  });

  const start = useCallback(() => {
    waited.current.clear();
    flags.current = { advanced: false, fraudNet: null };
    setRun(true);
    requestAnimationFrame(() => controls.reset(true));
  }, [controls]);
  const exit = useCallback(() => controls.skip(), [controls]);
  useEffect(() => { tourStatus.exit = exit; tourStatus.restart = start; }, [exit, start]);

  const d = (state.status === STATUS.RUNNING ? (steps[state.index]?.data as StepData) : undefined);
  const value: Tour = { active: run, scenario, index: state.index, size: steps.length, chapter: d ? CHAPTERS[d.chapter] : "", start, exit };
  return <Ctx.Provider value={value}>{children}{Tour}</Ctx.Provider>;
}
