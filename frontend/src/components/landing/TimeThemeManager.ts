import { useEffect, useMemo, useState } from "react";

import { getTimeTheme, type TimeTheme } from "./timeThemes";

export function useTimeTheme(): TimeTheme {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const intervalId = window.setInterval(() => setNow(new Date()), 60_000);
    return () => window.clearInterval(intervalId);
  }, []);

  return useMemo(() => getTimeTheme(now), [now]);
}

export function usePointerParallax(strength: number) {
  const [offset, setOffset] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const handlePointerMove = (event: PointerEvent) => {
      const x = (event.clientX / window.innerWidth - 0.5) * strength;
      const y = (event.clientY / window.innerHeight - 0.5) * strength;
      setOffset({ x, y });
    };

    window.addEventListener("pointermove", handlePointerMove, { passive: true });
    return () => window.removeEventListener("pointermove", handlePointerMove);
  }, [strength]);

  return offset;
}
