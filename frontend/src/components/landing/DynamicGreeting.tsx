import { motion } from "framer-motion";

import type { TimeTheme } from "./timeThemes";

export function DynamicGreeting({ theme }: { theme: TimeTheme }) {
  return (
    <motion.p
      key={theme.id}
      className="font-display text-[0.72rem] font-semibold uppercase tracking-[0.28em] text-white/78 sm:text-[0.78rem]"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.7, ease: "easeOut" }}
    >
      {theme.greeting}
    </motion.p>
  );
}
