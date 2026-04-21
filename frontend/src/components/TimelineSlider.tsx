import { useMemo } from "react";

interface TimelineSliderProps {
  minTimestamp: string | null;
  maxTimestamp: string | null;
  value: number | null;
  onChange: (value: number) => void;
}

export function TimelineSlider({ minTimestamp, maxTimestamp, value, onChange }: TimelineSliderProps) {
  const range = useMemo(() => {
    if (!minTimestamp || !maxTimestamp) {
      return null;
    }
    return {
      min: new Date(minTimestamp).getTime(),
      max: new Date(maxTimestamp).getTime(),
    };
  }, [minTimestamp, maxTimestamp]);

  if (!range) {
    return (
      <div className="timeline-shell disabled">
        <div className="timeline-header">
          <span>Timeline</span>
          <span>Post thoughts to watch your graph evolve.</span>
        </div>
      </div>
    );
  }

  const currentValue = value ?? range.max;
  const leftLabel = new Date(range.min).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  const rightLabel = new Date(range.max).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  const currentLabel = new Date(currentValue).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  const progress = ((currentValue - range.min) / Math.max(range.max - range.min, 1)) * 100;

  return (
    <div className="timeline-shell">
      <div className="timeline-header">
        <span>Timeline</span>
        <span>{currentLabel}</span>
      </div>
      <input
        className="timeline-slider"
        type="range"
        min={range.min}
        max={range.max}
        value={currentValue}
        onChange={(event) => onChange(Number(event.currentTarget.value))}
        style={{ ["--progress" as string]: `${progress}%` }}
      />
      <div className="timeline-labels">
        <span>{leftLabel}</span>
        <span>30 day window</span>
        <span>{rightLabel}</span>
      </div>
    </div>
  );
}

