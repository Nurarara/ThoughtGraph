import { motion } from "framer-motion";

import type { TimeTheme } from "./timeThemes";

export function FloatingParticles({ theme, cursor }: { theme: TimeTheme; cursor: { x: number; y: number } }) {
  const veils = [
    { id: 0, left: -10, top: 18, width: 54, height: 24, duration: 22, delay: 0 },
    { id: 1, left: 42, top: 12, width: 62, height: 28, duration: 26, delay: 2.8 },
    { id: 2, left: 8, top: 58, width: 46, height: 20, duration: 24, delay: 1.4 },
    { id: 3, left: 62, top: 64, width: 52, height: 22, duration: 28, delay: 4.2 },
  ];

  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      {veils.map((veil) => (
        <motion.div
          key={veil.id}
          className="absolute rounded-full blur-3xl"
          style={{
            left: `${veil.left}%`,
            top: `${veil.top}%`,
            width: `${veil.width}%`,
            height: `${veil.height}%`,
            background: `radial-gradient(ellipse at center, ${theme.particles.glow}, transparent 68%)`,
            opacity: 0.18,
          }}
          animate={{
            x: [cursor.x * 0.04, cursor.x * 0.1 + 14, cursor.x * 0.04],
            y: [0, -8, 0],
            opacity: [0.1, 0.2, 0.1],
            scale: [1, 1.04, 1],
          }}
          transition={{
            duration: veil.duration,
            delay: veil.delay,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />
      ))}
    </div>
  );
}
