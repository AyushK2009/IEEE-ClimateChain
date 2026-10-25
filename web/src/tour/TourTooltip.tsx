import type { LoaderRenderProps, TooltipRenderProps } from "react-joyride";
import { ArrowLeft, ArrowRight, MousePointerClick, RotateCcw } from "lucide-react";
import { CHAPTERS } from "./steps";
import { tourStatus } from "./state";

export type StepData = {
  chapter: number; wait?: string; doIt?: string; doLabel?: string; noBack?: boolean; wide?: boolean; media?: string; mediaCaption?: string;
  nextLabel?: string; finale?: boolean; loading?: string;
};

export function TourTooltip({ backProps, index, primaryProps, size, skipProps, step, tooltipProps, controls }: TooltipRenderProps) {
  const d = (step.data ?? {}) as StepData;
  const ch = CHAPTERS[d.chapter] ?? CHAPTERS[0];
  const pct = Math.round(((index + 1) / size) * 100);
  return (
    <div {...tooltipProps} className={`tour ${d.wide ? "wide" : ""}`} data-step={step.id}>
      {d.media && <img className="tour-media" src={d.media} alt="" />}
      <div className="tour-progress"><i style={{ width: `${pct}%` }} /></div>
      <div className="tour-body">
        <div className="tour-chapter"><span>{d.chapter > 0 ? `${d.chapter}. ` : ""}{ch}</span><span className="muted">{index + 1} / {size}</span></div>
        {step.title && <h3>{step.title}</h3>}
        <div className="tour-content">{step.content}</div>
        {d.mediaCaption && <div className="tiny muted" style={{ marginTop: 8 }}>{d.mediaCaption}</div>}
        {d.wait && (
          <div className="tour-wait"><MousePointerClick size={15} style={{ flex: "none" }} />
            <span className="grow">Click the highlighted control to continue.</span>
            {d.doIt && <button className="btn sm" onClick={() => {
              const t: any = step.target;
              const el = d.doIt === "@target" ? (typeof t === "function" ? t() : typeof t === "string" ? document.querySelector(t) : t) : document.querySelector(d.doIt!);
              (el as HTMLElement | null)?.click();
            }}>{d.doLabel ?? "Do it for me"}</button>}
          </div>
        )}
      </div>
      <div className="tour-foot">
        <button className="exit" {...skipProps}>{d.finale ? "Close" : "Exit demo"}</button>
        <span className="grow" />
        {d.finale && <button className="btn sm" onClick={() => tourStatus.restart?.()}><RotateCcw size={14} />Restart</button>}
        {index > 0 && !d.noBack && !d.finale && <button className="btn sm" {...backProps}><ArrowLeft size={14} />Back</button>}
        {!d.wait && <button className="btn sm primary" {...primaryProps}>{d.nextLabel ?? (index + 1 === size ? "Finish" : "Next")}{!d.finale && <ArrowRight size={14} />}</button>}
      </div>
    </div>
  );
}

export function TourLoader({ step }: LoaderRenderProps) {
  const d = (step?.data ?? {}) as StepData;
  return (
    <div className="tour-loading">
      <div><span className="spin" style={{ color: "var(--sea)" }} />
        <div>{tourStatus.message || d.loading || "Getting the next step ready…"}<small>{tourStatus.detail || "Waiting for the application, not a timer."}</small></div>
        <button className="btn sm" onClick={() => tourStatus.exit?.()}>Exit</button>
      </div>
    </div>
  );
}
