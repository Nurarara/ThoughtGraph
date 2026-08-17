import { motion } from "framer-motion";

import { HeroContent } from "./HeroContent";
import { usePointerParallax, useTimeTheme } from "./TimeThemeManager";
import { TimeBasedWorldBackground } from "./TimeBasedWorldBackground";

export function LandingPage({ onCreateUniverse }: { onCreateUniverse: () => void }) {
  const theme = useTimeTheme();
  const parallax = usePointerParallax(theme.motion.parallaxStrength);

  return (
    <main className="relative min-h-screen overflow-hidden bg-black font-display text-white">
      <TimeBasedWorldBackground theme={theme} parallax={parallax} />

      <motion.div
        className="pointer-events-none absolute left-6 top-6 z-20 flex items-center gap-3 text-xs font-semibold uppercase tracking-[0.26em] text-white/70 sm:left-10 sm:top-8"
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease: "easeOut" }}
      >
        <span className="h-2 w-2 rounded-full" style={{ backgroundColor: theme.palette.accent }} />
        ThoughtGraph
      </motion.div>

      <HeroContent theme={theme} onCreateUniverse={onCreateUniverse} />
    </main>
  );
}
