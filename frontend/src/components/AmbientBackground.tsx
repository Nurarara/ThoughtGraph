import { motion } from "framer-motion";

import type { Mood } from "../types";

interface AmbientBackgroundProps {
  mood: Mood;
}

export function AmbientBackground({ mood }: AmbientBackgroundProps) {
  return (
    <div className={`ambient ambient-${mood}`} aria-hidden="true">
      <motion.div className="ambient-orb orb-a" animate={{ x: [0, 20, -10], y: [0, -30, 10], scale: [1, 1.1, 0.95] }} transition={{ duration: 22, repeat: Infinity, repeatType: "reverse", ease: "easeInOut" }} />
      <motion.div className="ambient-orb orb-b" animate={{ x: [0, -25, 5], y: [0, 15, -25], scale: [1, 0.95, 1.08] }} transition={{ duration: 24, repeat: Infinity, repeatType: "reverse", ease: "easeInOut" }} />
      <motion.div className="ambient-orb orb-c" animate={{ x: [0, 18, -12], y: [0, 22, -14], scale: [1, 1.06, 0.92] }} transition={{ duration: 20, repeat: Infinity, repeatType: "reverse", ease: "easeInOut" }} />
      <div className="ambient-stars" />
    </div>
  );
}

