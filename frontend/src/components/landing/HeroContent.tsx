import { motion } from "framer-motion";

import { CreateUniverseCTA } from "./CreateUniverseCTA";
import { DynamicGreeting } from "./DynamicGreeting";
import type { TimeTheme } from "./timeThemes";

export function HeroContent({
  theme,
  onCreateUniverse,
}: {
  theme: TimeTheme;
  onCreateUniverse: () => void;
}) {
  return (
    <section className="relative z-20 flex min-h-screen items-center px-6 py-24 sm:px-10 lg:px-20">
      <motion.div
        className="mx-auto w-full max-w-5xl text-center sm:text-left"
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.9, ease: "easeOut" }}
      >
        <DynamicGreeting theme={theme} />
        <motion.h1
          className="mt-5 max-w-4xl font-display text-5xl font-semibold leading-[1.02] tracking-[-0.06em] text-white sm:text-7xl lg:text-[6.75rem]"
          style={{ textShadow: theme.overlay.textShadow }}
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.9, delay: 0.08, ease: "easeOut" }}
        >
          Welcome to your universe
        </motion.h1>
        <motion.p
          className="mt-6 max-w-2xl text-base leading-8 text-white/78 sm:text-lg"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.85, delay: 0.18, ease: "easeOut" }}
        >
          A private place where thoughts become constellations, patterns become visible, and your inner world starts to feel explorable.
        </motion.p>
        <CreateUniverseCTA theme={theme} onClick={onCreateUniverse} />
      </motion.div>
    </section>
  );
}
