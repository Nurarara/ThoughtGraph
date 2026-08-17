import { useEffect, useRef } from "react";

type OrbitBody = {
  x: number;
  y: number;
  mass: number;
  phase: number;
  speed: number;
  color: "cyan" | "amber";
  label?: string;
  evidence?: string;
};

const BODIES: OrbitBody[] = [
  { x: 0.63, y: 0.52, mass: 1.7, phase: 0.2, speed: 0.24, color: "amber", label: "CORE IDEA", evidence: "gravity strong" },
  { x: 0.49, y: 0.27, mass: 1.05, phase: 1.3, speed: 0.18, color: "cyan", label: "ARCHITECTURE", evidence: "evidence 6/10" },
  { x: 0.82, y: 0.34, mass: 1.12, phase: 2.1, speed: 0.21, color: "cyan", label: "WORKFLOW", evidence: "evidence 5/10" },
  { x: 0.78, y: 0.72, mass: 0.92, phase: 3.2, speed: 0.16, color: "cyan", label: "GREEN LIVING", evidence: "evidence 7/10" },
  { x: 0.47, y: 0.78, mass: 0.84, phase: 4.1, speed: 0.19, color: "cyan", label: "MONEY", evidence: "evidence 4/10" },
  { x: 0.66, y: 0.83, mass: 0.68, phase: 5.2, speed: 0.23, color: "cyan", label: "HERE / CONSCIOUS", evidence: "evidence 8/10" },
  { x: 0.56, y: 0.45, mass: 0.48, phase: 0.8, speed: 0.31, color: "amber" },
  { x: 0.69, y: 0.45, mass: 0.42, phase: 2.6, speed: 0.29, color: "amber" },
  { x: 0.71, y: 0.57, mass: 0.36, phase: 4.4, speed: 0.34, color: "amber" },
  { x: 0.57, y: 0.61, mass: 0.34, phase: 5.7, speed: 0.27, color: "amber" },
  { x: 0.38, y: 0.38, mass: 0.26, phase: 1.8, speed: 0.22, color: "cyan" },
  { x: 0.91, y: 0.54, mass: 0.3, phase: 3.8, speed: 0.2, color: "amber" },
];

const LINKS: Array<[number, number]> = [
  [0, 1], [0, 2], [0, 3], [0, 4], [0, 5], [0, 6], [0, 7], [0, 8], [0, 9],
  [1, 10], [2, 11], [3, 8], [4, 9],
];

const CYAN = "63, 198, 220";
const AMBER = "244, 174, 66";

export type LandingFieldMode = "capture" | "connect" | "reflect";

export function LandingOrbitField({
  mode,
  entering = false,
}: {
  mode: LandingFieldMode;
  entering?: boolean;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const pointerRef = useRef({ x: 0.66, y: 0.5, active: false });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const context = canvas.getContext("2d");
    if (!context) return;

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let frameId = 0;
    let width = 0;
    let height = 0;
    let dpr = 1;

    const resize = () => {
      const bounds = canvas.getBoundingClientRect();
      width = bounds.width;
      height = bounds.height;
      dpr = window.devicePixelRatio || 1;
      canvas.width = Math.max(1, Math.floor(width * dpr));
      canvas.height = Math.max(1, Math.floor(height * dpr));
    };

    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    resize();

    const draw = (time: number) => {
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
      context.clearRect(0, 0, width, height);

      const seconds = reducedMotion ? 0 : time / 1000;
      const pointer = pointerRef.current;
      const fieldCenter = { x: width * 0.64, y: height * 0.52 };
      const fieldRadius = Math.min(width * 0.5, height * 0.62);

      context.lineWidth = 1;
      for (let ring = 1; ring <= 5; ring += 1) {
        context.beginPath();
        context.ellipse(fieldCenter.x, fieldCenter.y, fieldRadius * (ring / 5), fieldRadius * 0.74 * (ring / 5), -0.12, 0, Math.PI * 2);
        context.strokeStyle = `rgba(${ring % 2 ? CYAN : AMBER}, ${0.045 + ring * 0.006})`;
        context.stroke();
      }

      context.setLineDash([2, 8]);
      context.strokeStyle = `rgba(${CYAN}, 0.08)`;
      context.beginPath();
      context.moveTo(fieldCenter.x, height * 0.08);
      context.lineTo(fieldCenter.x, height * 0.92);
      context.moveTo(width * 0.36, fieldCenter.y);
      context.lineTo(width * 0.96, fieldCenter.y);
      context.stroke();
      context.setLineDash([]);

      const positions = BODIES.map((body) => {
        const orbitalX = Math.cos(seconds * body.speed + body.phase) * (3 + body.mass * 2.4);
        const orbitalY = Math.sin(seconds * body.speed + body.phase) * (2 + body.mass * 1.7);
        const pointerPull = pointer.active ? 0.022 / Math.max(0.65, body.mass) : 0;
        return {
          x: body.x * width + orbitalX + (pointer.x * width - body.x * width) * pointerPull,
          y: body.y * height + orbitalY + (pointer.y * height - body.y * height) * pointerPull,
        };
      });

      for (const [fromIndex, toIndex] of LINKS) {
        const from = positions[fromIndex];
        const to = positions[toIndex];
        const active = mode === "connect" || fromIndex === 0 || toIndex === 0;
        context.beginPath();
        context.moveTo(from.x, from.y);
        context.lineTo(to.x, to.y);
        const activeAlpha = mode === "connect" ? 0.3 : mode === "reflect" ? 0.2 : 0.14;
        context.strokeStyle = `rgba(${active ? AMBER : CYAN}, ${active ? activeAlpha : 0.08})`;
        context.lineWidth = active ? (mode === "connect" ? 1.35 : 1) : 0.7;
        context.stroke();
      }

      BODIES.forEach((body, index) => {
        const point = positions[index];
        const color = body.color === "amber" ? AMBER : CYAN;
        const radius = 4 + body.mass * 9;
        const halo = context.createRadialGradient(point.x, point.y, radius * 0.3, point.x, point.y, radius * 2.8);
        halo.addColorStop(0, `rgba(${color}, 0.34)`);
        halo.addColorStop(1, `rgba(${color}, 0)`);
        context.beginPath();
        context.arc(point.x, point.y, radius * 2.8, 0, Math.PI * 2);
        context.fillStyle = halo;
        context.fill();

        const bodyFill = context.createRadialGradient(point.x - radius * 0.3, point.y - radius * 0.35, radius * 0.1, point.x, point.y, radius);
        bodyFill.addColorStop(0, `rgba(${color}, 1)`);
        bodyFill.addColorStop(0.5, `rgba(${color}, 0.62)`);
        bodyFill.addColorStop(1, `rgba(${color}, 0.16)`);
        context.beginPath();
        context.arc(point.x, point.y, radius, 0, Math.PI * 2);
        context.fillStyle = bodyFill;
        context.fill();
        context.strokeStyle = `rgba(${color}, 0.72)`;
        context.stroke();

        if (body.label && width > 760 && (mode !== "capture" || index === 0)) {
          context.font = "500 11px 'IBM Plex Mono', monospace";
          context.fillStyle = `rgba(${color}, 0.92)`;
          context.textAlign = "left";
          context.fillText(body.label, point.x + radius + 13, point.y - 3);
          context.font = "400 10px 'IBM Plex Mono', monospace";
          context.fillStyle = "rgba(196, 218, 225, 0.52)";
          context.fillText(body.evidence ?? "", point.x + radius + 13, point.y + 13);
        }
      });

      const core = positions[0];
      const pulse = reducedMotion ? 0 : Math.sin(seconds * 1.4) * 4;
      context.strokeStyle = `rgba(${CYAN}, 0.78)`;
      context.lineWidth = 1.25;
      context.beginPath();
      context.arc(core.x, core.y, 68 + pulse, 0, Math.PI * 2);
      context.stroke();
      for (const angle of [0, Math.PI / 2, Math.PI, Math.PI * 1.5]) {
        const inner = 76 + pulse;
        const outer = 98 + pulse;
        context.beginPath();
        context.moveTo(core.x + Math.cos(angle) * inner, core.y + Math.sin(angle) * inner);
        context.lineTo(core.x + Math.cos(angle) * outer, core.y + Math.sin(angle) * outer);
        context.stroke();
      }

      if (mode === "reflect") {
        const evidenceNode = positions[5];
        context.setLineDash([4, 6]);
        context.strokeStyle = `rgba(${CYAN}, 0.62)`;
        context.beginPath();
        context.arc(evidenceNode.x, evidenceNode.y, 38 + pulse * 0.5, 0, Math.PI * 2);
        context.stroke();
        context.setLineDash([]);
      }

      if (!reducedMotion) frameId = window.requestAnimationFrame(draw);
    };

    frameId = window.requestAnimationFrame(draw);
    if (reducedMotion) draw(0);

    return () => {
      observer.disconnect();
      window.cancelAnimationFrame(frameId);
    };
  }, [mode]);

  return (
    <canvas
      ref={canvasRef}
      className={`landing-orbit-field ${entering ? "is-entering" : ""}`}
      aria-hidden="true"
      onPointerEnter={() => { pointerRef.current.active = true; }}
      onPointerLeave={() => { pointerRef.current.active = false; }}
      onPointerMove={(event) => {
        const bounds = event.currentTarget.getBoundingClientRect();
        pointerRef.current = {
          active: true,
          x: (event.clientX - bounds.left) / Math.max(1, bounds.width),
          y: (event.clientY - bounds.top) / Math.max(1, bounds.height),
        };
      }}
    />
  );
}
