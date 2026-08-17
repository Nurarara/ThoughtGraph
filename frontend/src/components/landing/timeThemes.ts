export type TimeState = "morning" | "day" | "evening" | "night";

export interface TimeTheme {
  id: TimeState;
  label: string;
  timeRange: {
    startHour: number;
    endHour: number;
  };
  greeting: string;
  moodDescription: string;
  animeStyleDescription: string;
  imageAssetPath: string;
  overlay: {
    gradient: string;
    vignette: string;
    textShadow: string;
  };
  motion: {
    cloudDurationSeconds: number;
    treeSway: number;
    parallaxStrength: number;
    skyPulseSeconds: number;
  };
  particles: {
    count: number;
    color: string;
    glow: string;
    behavior: "mist" | "dust" | "embers" | "fireflies";
  };
  palette: {
    skyTop: string;
    skyMid: string;
    horizon: string;
    ground: string;
    accent: string;
    text: string;
  };
  gptImagePrompt: string;
}

const BASE_PROMPT_RULES =
  "No characters, no humans, no people, no faces, no silhouettes, no animals, no creatures. " +
  "Only environmental anime world design: trees, sky, clouds, distant horizon, atmospheric depth, and clear empty composition space for centered text. " +
  "Premium cinematic anime film background, calm futuristic introspection product identity, high detail, painterly lighting, no glitter, no sparkles, no particle dots, no logos, no text, no UI.";

export const TIME_THEMES: Record<TimeState, TimeTheme> = {
  morning: {
    id: "morning",
    label: "Morning",
    timeRange: { startHour: 5, endHour: 11 },
    greeting: "Good morning, explorer.",
    moodDescription: "Fresh, hopeful, luminous, and quietly awakening.",
    animeStyleDescription:
      "Soft airy anime atmosphere with delicate mist, pastel warmth, gentle bloom, and translucent clouds.",
    imageAssetPath: "/gpt-worlds/thoughtgraph-morning.webp",
    overlay: {
      gradient:
        "linear-gradient(180deg, rgba(255,244,218,0.18) 0%, rgba(116,177,215,0.18) 42%, rgba(21,33,39,0.50) 100%)",
      vignette: "radial-gradient(circle at 50% 42%, rgba(255,255,255,0.05), rgba(2,8,13,0.50) 76%)",
      textShadow: "0 16px 48px rgba(63, 73, 91, 0.36)",
    },
    motion: {
      cloudDurationSeconds: 30,
      treeSway: 0.8,
      parallaxStrength: 14,
      skyPulseSeconds: 12,
    },
    particles: {
      count: 0,
      color: "rgba(255, 246, 218, 0.75)",
      glow: "rgba(255, 244, 196, 0.32)",
      behavior: "mist",
    },
    palette: {
      skyTop: "#ffe7c7",
      skyMid: "#a9d5ed",
      horizon: "#f9dba6",
      ground: "#183829",
      accent: "#ffe1a6",
      text: "#fffaf0",
    },
    gptImagePrompt: `${BASE_PROMPT_RULES} Morning state: soft luminous sunrise, delicate valley mist, fresh leaves, pale gold light through quiet trees, hopeful pastel sky, gentle atmospheric haze, cohesive ThoughtGraph universe.`,
  },
  day: {
    id: "day",
    label: "Day",
    timeRange: { startHour: 11, endHour: 17 },
    greeting: "Welcome back, creator.",
    moodDescription: "Open, crisp, peaceful, vivid, and energizing.",
    animeStyleDescription:
      "Clean bright anime scenery with crisp sunlight, open sky, vivid green layers, and clear depth.",
    imageAssetPath: "/gpt-worlds/thoughtgraph-day.webp",
    overlay: {
      gradient:
        "linear-gradient(180deg, rgba(109,191,245,0.12) 0%, rgba(88,172,197,0.10) 46%, rgba(7,18,20,0.48) 100%)",
      vignette: "radial-gradient(circle at 54% 38%, rgba(255,255,255,0.04), rgba(0,7,12,0.45) 78%)",
      textShadow: "0 18px 54px rgba(0, 32, 46, 0.38)",
    },
    motion: {
      cloudDurationSeconds: 24,
      treeSway: 1,
      parallaxStrength: 18,
      skyPulseSeconds: 10,
    },
    particles: {
      count: 0,
      color: "rgba(235, 252, 255, 0.64)",
      glow: "rgba(127, 224, 255, 0.20)",
      behavior: "dust",
    },
    palette: {
      skyTop: "#69bff6",
      skyMid: "#b7edff",
      horizon: "#e8f7cf",
      ground: "#123f31",
      accent: "#86f7df",
      text: "#f6fdff",
    },
    gptImagePrompt: `${BASE_PROMPT_RULES} Day state: bright clean open anime sky, crisp lighting, peaceful tree line, distant luminous horizon, vivid but premium color, calm energy, wide empty negative space for hero copy.`,
  },
  evening: {
    id: "evening",
    label: "Evening",
    timeRange: { startHour: 17, endHour: 21 },
    greeting: "Good evening, dreamer.",
    moodDescription: "Cinematic, nostalgic, dramatic, warm, and emotionally deep.",
    animeStyleDescription:
      "Dramatic anime sunset background with rich orange, pink, violet atmosphere and a glowing horizon.",
    imageAssetPath: "/gpt-worlds/thoughtgraph-evening.webp",
    overlay: {
      gradient:
        "linear-gradient(180deg, rgba(255,143,93,0.22) 0%, rgba(169,82,167,0.18) 46%, rgba(21,8,30,0.62) 100%)",
      vignette: "radial-gradient(circle at 50% 46%, rgba(255,160,110,0.08), rgba(9,3,18,0.58) 78%)",
      textShadow: "0 20px 58px rgba(37, 12, 44, 0.54)",
    },
    motion: {
      cloudDurationSeconds: 34,
      treeSway: 0.65,
      parallaxStrength: 16,
      skyPulseSeconds: 13,
    },
    particles: {
      count: 0,
      color: "rgba(255, 190, 130, 0.72)",
      glow: "rgba(255, 126, 92, 0.28)",
      behavior: "embers",
    },
    palette: {
      skyTop: "#7d4eb7",
      skyMid: "#ff8a68",
      horizon: "#ffd07b",
      ground: "#1a182a",
      accent: "#ffbf7a",
      text: "#fff4eb",
    },
    gptImagePrompt: `${BASE_PROMPT_RULES} Evening sunset state: cinematic emotional anime background, glowing orange-pink horizon, violet high clouds, nostalgic dreamy atmosphere, dark tree silhouettes with subtle detail, premium film lighting.`,
  },
  night: {
    id: "night",
    label: "Night",
    timeRange: { startHour: 21, endHour: 5 },
    greeting: "The universe is quiet tonight.",
    moodDescription: "Deep, magical, serene, private, cosmic, and introspective.",
    animeStyleDescription:
      "Moonlit ethereal anime world with quiet trees, soft cloud bands, and a subtle cosmic atmosphere.",
    imageAssetPath: "/gpt-worlds/thoughtgraph-night.webp",
    overlay: {
      gradient:
        "linear-gradient(180deg, rgba(23,32,78,0.22) 0%, rgba(25,23,65,0.20) 46%, rgba(2,4,14,0.70) 100%)",
      vignette: "radial-gradient(circle at 50% 40%, rgba(142,184,255,0.08), rgba(0,0,8,0.70) 78%)",
      textShadow: "0 24px 72px rgba(7, 10, 32, 0.70)",
    },
    motion: {
      cloudDurationSeconds: 40,
      treeSway: 0.42,
      parallaxStrength: 12,
      skyPulseSeconds: 16,
    },
    particles: {
      count: 0,
      color: "rgba(175, 221, 255, 0.86)",
      glow: "rgba(128, 219, 255, 0.42)",
      behavior: "mist",
    },
    palette: {
      skyTop: "#07132f",
      skyMid: "#18255f",
      horizon: "#5d6fc0",
      ground: "#07130f",
      accent: "#9ee8ff",
      text: "#edf6ff",
    },
    gptImagePrompt: `${BASE_PROMPT_RULES} Night state: serene magical moonlit anime world, deep blue sky, soft cloud bands, quiet tree layers, faint cosmic glow near horizon, private introspective universe, no star-field glitter, no fireflies.`,
  },
};

export function getTimeState(date = new Date()): TimeState {
  const hour = date.getHours();
  if (hour >= 5 && hour < 11) return "morning";
  if (hour >= 11 && hour < 17) return "day";
  if (hour >= 17 && hour < 21) return "evening";
  return "night";
}

export function getTimeTheme(date = new Date()): TimeTheme {
  return TIME_THEMES[getTimeState(date)];
}

export const GPT_IMAGE_PIPELINE_NOTES = {
  provider: "GPT Images 2.0",
  outputDirectory: "frontend/public/gpt-worlds",
  requiredAssets: Object.values(TIME_THEMES).map((theme) => theme.imageAssetPath),
  consistencyRules: [
    "Use the same imagined landscape layout across all four states.",
    "Keep empty composition space for the headline.",
    "No characters, no humans, no faces, no animals, no creatures.",
    "No glitter, sparkles, particle dots, fireflies, or decorative confetti.",
    "Export wide 16:9 or 21:9 images, at least 2400px wide.",
  ],
};
