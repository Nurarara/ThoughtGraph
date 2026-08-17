import { motion } from "framer-motion";

interface ParallaxSceneLayerProps {
  className?: string;
  depth: number;
  offset: { x: number; y: number };
  children: React.ReactNode;
}

export function ParallaxSceneLayer({ className = "", depth, offset, children }: ParallaxSceneLayerProps) {
  return (
    <motion.div
      className={className}
      animate={{
        x: offset.x * depth,
        y: offset.y * depth,
      }}
      transition={{ type: "spring", stiffness: 34, damping: 22, mass: 1.2 }}
    >
      {children}
    </motion.div>
  );
}
