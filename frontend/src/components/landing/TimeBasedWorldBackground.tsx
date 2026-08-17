import { motion } from "framer-motion";

import { FloatingParticles } from "./FloatingParticles";
import { ParallaxSceneLayer } from "./ParallaxSceneLayer";
import type { TimeTheme } from "./timeThemes";

function forestCanopy(theme: TimeTheme, opacity: number) {
  const canopy = `color-mix(in srgb, ${theme.palette.ground} ${Math.round(opacity * 100)}%, transparent)`;
  return [
    `radial-gradient(ellipse at 6% 100%, ${canopy} 0 18%, transparent 19%)`,
    `radial-gradient(ellipse at 18% 96%, ${canopy} 0 25%, transparent 26%)`,
    `radial-gradient(ellipse at 34% 102%, ${canopy} 0 22%, transparent 23%)`,
    `radial-gradient(ellipse at 52% 98%, ${canopy} 0 26%, transparent 27%)`,
    `radial-gradient(ellipse at 70% 101%, ${canopy} 0 22%, transparent 23%)`,
    `radial-gradient(ellipse at 88% 96%, ${canopy} 0 25%, transparent 26%)`,
    `linear-gradient(180deg, transparent 0%, transparent 52%, ${canopy} 53%, ${theme.palette.ground} 100%)`,
  ].join(", ");
}

function groundHaze(theme: TimeTheme) {
  return [
    `radial-gradient(ellipse at 50% 18%, color-mix(in srgb, ${theme.palette.horizon} 42%, transparent), transparent 42%)`,
    "linear-gradient(180deg, transparent 0%, rgba(255,255,255,0.07) 48%, transparent 100%)",
  ].join(", ");
}

export function TimeBasedWorldBackground({
  theme,
  parallax,
}: {
  theme: TimeTheme;
  parallax: { x: number; y: number };
}) {
  return (
    <div className="absolute inset-0 overflow-hidden" aria-hidden="true">
      <motion.div
        key={`${theme.id}-sky`}
        className="absolute inset-0"
        style={{
          background:
            `linear-gradient(180deg, ${theme.palette.skyTop} 0%, ${theme.palette.skyMid} 42%, ${theme.palette.horizon} 68%, ${theme.palette.ground} 100%)`,
        }}
        initial={{ opacity: 0.82, scale: 1.02 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 1.3, ease: "easeOut" }}
      />

      <motion.div
        className="absolute inset-[-6%] bg-cover bg-center opacity-45 mix-blend-soft-light"
        style={{
          backgroundImage: `url(${theme.imageAssetPath})`,
        }}
        animate={{ scale: [1.02, 1.035, 1.02], opacity: [0.32, 0.46, 0.32] }}
        transition={{ duration: theme.motion.skyPulseSeconds, repeat: Infinity, ease: "easeInOut" }}
      />

      <ParallaxSceneLayer className="absolute inset-x-[-12%] top-[6%] h-[32%]" depth={0.34} offset={parallax}>
        <div
          className="h-full animate-cloud-drift opacity-55 blur-[1px]"
          style={{
            animationDuration: `${theme.motion.cloudDurationSeconds}s`,
            background:
              "radial-gradient(ellipse at 18% 42%, rgba(255,255,255,0.72), transparent 24%), radial-gradient(ellipse at 44% 24%, rgba(255,255,255,0.56), transparent 22%), radial-gradient(ellipse at 78% 34%, rgba(255,255,255,0.46), transparent 26%)",
          }}
        />
      </ParallaxSceneLayer>

      <ParallaxSceneLayer className="absolute inset-x-[-10%] top-[30%] h-[34%]" depth={0.5} offset={parallax}>
        <div
          className="h-full opacity-70 blur-[1px]"
          style={{
            background: groundHaze(theme),
          }}
        />
      </ParallaxSceneLayer>

      <ParallaxSceneLayer className="absolute inset-x-[-8%] bottom-[14%] h-[28%]" depth={0.68} offset={parallax}>
        <div
          className="h-full animate-tree-breathe"
          style={{
            animationDuration: `${15 / Math.max(theme.motion.treeSway, 0.35)}s`,
            background: forestCanopy(theme, 0.58),
            filter: "blur(1.2px)",
          }}
        />
      </ParallaxSceneLayer>

      <ParallaxSceneLayer className="absolute inset-x-[-6%] bottom-[-10%] h-[48%]" depth={1.02} offset={parallax}>
        <div
          className="h-full animate-tree-breathe"
          style={{
            animationDuration: `${12 / Math.max(theme.motion.treeSway, 0.35)}s`,
            background: forestCanopy(theme, 0.94),
          }}
        />
      </ParallaxSceneLayer>

      <FloatingParticles theme={theme} cursor={parallax} />

      <div className="absolute inset-0" style={{ background: theme.overlay.gradient }} />
      <div className="absolute inset-0" style={{ background: theme.overlay.vignette }} />
      <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-black/46 via-black/10 to-transparent" />
    </div>
  );
}
