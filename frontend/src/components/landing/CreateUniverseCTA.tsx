import { motion } from "framer-motion";

import type { TimeTheme } from "./timeThemes";

export function CreateUniverseCTA({
  theme,
  onClick,
}: {
  theme: TimeTheme;
  onClick: () => void;
}) {
  return (
    <motion.button
      type="button"
      onClick={onClick}
      className="group relative mt-8 inline-flex min-h-14 items-center justify-center overflow-hidden rounded-full border border-white/30 px-7 py-4 font-display text-sm font-semibold text-white shadow-universe outline-none transition-[border-color,transform] duration-300 hover:-translate-y-0.5 hover:border-white/55 focus-visible:ring-2 focus-visible:ring-white/70 sm:px-8"
      style={{
        background: `linear-gradient(135deg, color-mix(in srgb, ${theme.palette.accent} 34%, transparent), rgba(255,255,255,0.11))`,
        boxShadow: `0 22px 80px color-mix(in srgb, ${theme.palette.accent} 22%, transparent)`,
      }}
      whileHover={{ scale: 1.025 }}
      whileTap={{ scale: 0.985 }}
    >
      <span className="absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100" style={{ background: "linear-gradient(120deg, transparent, rgba(255,255,255,0.22), transparent)" }} />
      <span className="relative">Create your universe</span>
    </motion.button>
  );
}
