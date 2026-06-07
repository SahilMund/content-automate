import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
  Easing,
} from "remotion";
import { z } from "zod";

export const schema = z.object({
  topic: z.string(),
  stat: z.string(),
  statLabel: z.string(),
  points: z.array(z.string()).max(4),
  handle: z.string(),
  accentColor: z.string(),
  bgColor: z.string(),
});

type Props = z.infer<typeof schema>;

const ease = Easing.bezier(0.16, 1, 0.3, 1);

// ── Scene 1: Brand intro (0–40f) ─────────────────────────────
const Intro: React.FC<Pick<Props, "accentColor" | "bgColor">> = ({
  accentColor,
  bgColor,
}) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 20, 30, 40], [0, 1, 1, 0], {
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill
      style={{
        backgroundColor: bgColor,
        justifyContent: "center",
        alignItems: "center",
        opacity,
      }}
    >
      <div
        style={{
          fontSize: 64,
          fontWeight: 900,
          color: accentColor,
          fontFamily: "sans-serif",
          letterSpacing: -2,
        }}
      >
        DraftPilot
      </div>
      <div
        style={{
          fontSize: 20,
          color: "#888",
          marginTop: 12,
          fontFamily: "sans-serif",
        }}
      >
        AI Content Intelligence
      </div>
    </AbsoluteFill>
  );
};

// ── Scene 2: Topic (40–110f) ─────────────────────────────────
const TopicScene: React.FC<
  Pick<Props, "topic" | "accentColor" | "bgColor">
> = ({ topic, accentColor, bgColor }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const localFrame = Math.max(0, frame - 40);
  const slideUp = spring({
    frame: localFrame,
    fps,
    config: { damping: 14 },
    durationInFrames: 40,
  });
  const opacity = interpolate(localFrame, [0, 20, 90, 110], [0, 1, 1, 0], {
    extrapolateRight: "clamp",
  });
  const y = interpolate(slideUp, [0, 1], [60, 0]);

  return (
    <AbsoluteFill
      style={{
        backgroundColor: bgColor,
        justifyContent: "center",
        alignItems: "center",
        opacity,
      }}
    >
      <div
        style={{
          transform: `translateY(${y}px)`,
          padding: "0 80px",
          textAlign: "center",
        }}
      >
        <div
          style={{
            fontSize: 18,
            color: accentColor,
            fontFamily: "sans-serif",
            letterSpacing: 4,
            textTransform: "uppercase",
            marginBottom: 24,
          }}
        >
          Today's Topic
        </div>
        <div
          style={{
            fontSize: 52,
            fontWeight: 800,
            color: "#fff",
            fontFamily: "sans-serif",
            lineHeight: 1.15,
          }}
        >
          {topic}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ── Scene 3: Stat callout (110–200f) ─────────────────────────
const StatScene: React.FC<
  Pick<Props, "stat" | "statLabel" | "accentColor" | "bgColor">
> = ({ stat, statLabel, accentColor, bgColor }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const localFrame = Math.max(0, frame - 110);
  const pop = spring({
    frame: localFrame,
    fps,
    config: { mass: 0.6, damping: 12 },
  });
  const opacity = interpolate(localFrame, [0, 15, 80, 100], [0, 1, 1, 0], {
    extrapolateRight: "clamp",
  });
  const scale = interpolate(pop, [0, 1], [0.5, 1]);

  return (
    <AbsoluteFill
      style={{
        backgroundColor: bgColor,
        justifyContent: "center",
        alignItems: "center",
        opacity,
      }}
    >
      <div
        style={{
          transform: `scale(${scale})`,
          textAlign: "center",
          padding: "0 60px",
        }}
      >
        <div
          style={{
            fontSize: 100,
            fontWeight: 900,
            color: accentColor,
            fontFamily: "sans-serif",
            lineHeight: 1,
          }}
        >
          {stat}
        </div>
        <div
          style={{
            fontSize: 26,
            color: "#ccc",
            marginTop: 20,
            fontFamily: "sans-serif",
          }}
        >
          {statLabel}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ── Scene 4: Bullet points (200–310f) ────────────────────────
const PointsScene: React.FC<
  Pick<Props, "points" | "accentColor" | "bgColor">
> = ({ points, accentColor, bgColor }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const localFrame = Math.max(0, frame - 200);
  const opacity = interpolate(localFrame, [0, 15, 95, 110], [0, 1, 1, 0], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: bgColor,
        justifyContent: "center",
        opacity,
        padding: "0 80px",
      }}
    >
      <div
        style={{
          fontSize: 22,
          color: accentColor,
          fontFamily: "sans-serif",
          letterSpacing: 3,
          textTransform: "uppercase",
          marginBottom: 40,
        }}
      >
        Key Insights
      </div>
      {points.map((point, i) => {
        const delay = i * 18;
        const localF = Math.max(0, localFrame - delay);
        const slide = spring({
          frame: localF,
          fps,
          config: { damping: 16 },
          durationInFrames: 30,
        });
        const x = interpolate(slide, [0, 1], [-80, 0]);
        const pOpacity = interpolate(localF, [0, 20], [0, 1], {
          extrapolateRight: "clamp",
        });
        return (
          <div
            key={i}
            style={{
              display: "flex",
              alignItems: "flex-start",
              marginBottom: 32,
              transform: `translateX(${x}px)`,
              opacity: pOpacity,
            }}
          >
            <div
              style={{
                width: 8,
                height: 8,
                borderRadius: 4,
                backgroundColor: accentColor,
                marginTop: 10,
                marginRight: 20,
                flexShrink: 0,
              }}
            />
            <div
              style={{
                fontSize: 36,
                fontWeight: 600,
                color: "#fff",
                fontFamily: "sans-serif",
                lineHeight: 1.3,
              }}
            >
              {point}
            </div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

// ── Scene 5: Outro (310–360f) ────────────────────────────────
const Outro: React.FC<Pick<Props, "handle" | "accentColor" | "bgColor">> = ({
  handle,
  accentColor,
  bgColor,
}) => {
  const frame = useCurrentFrame();
  const localFrame = Math.max(0, frame - 310);
  const opacity = interpolate(localFrame, [0, 20], [0, 1], {
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill
      style={{
        backgroundColor: bgColor,
        justifyContent: "center",
        alignItems: "center",
        opacity,
      }}
    >
      <div
        style={{
          fontSize: 32,
          color: "#888",
          fontFamily: "sans-serif",
          marginBottom: 16,
        }}
      >
        Follow for more
      </div>
      <div
        style={{
          fontSize: 52,
          fontWeight: 800,
          color: accentColor,
          fontFamily: "sans-serif",
        }}
      >
        {handle}
      </div>
    </AbsoluteFill>
  );
};

// ── Main composition ──────────────────────────────────────────
export const DraftPilotVideo: React.FC<Props> = (props) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ backgroundColor: props.bgColor }}>
      {frame < 45 && <Intro {...props} />}
      {frame >= 35 && frame < 115 && <TopicScene {...props} />}
      {frame >= 105 && frame < 205 && <StatScene {...props} />}
      {frame >= 195 && frame < 315 && <PointsScene {...props} />}
      {frame >= 305 && <Outro {...props} />}
    </AbsoluteFill>
  );
};
