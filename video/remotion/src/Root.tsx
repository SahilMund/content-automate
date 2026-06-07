import { Composition } from "remotion";
import { DraftPilotVideo, schema } from "./DraftPilotVideo";

export const Root: React.FC = () => {
  return (
    <Composition
      id="DraftPilotVideo"
      component={DraftPilotVideo}
      durationInFrames={360} // 12 seconds at 30fps
      fps={30}
      width={1080}
      height={1080}
      schema={schema}
      defaultProps={{
        topic: "AI Agents in 2026",
        stat: "78% of enterprises deploying AI agents",
        statLabel: "Enterprise Adoption",
        points: [
          "Agents make decisions autonomously",
          "Multi-agent systems outperform single LLMs",
          "Cost drops 60% vs human workflows",
        ],
        handle: "@the.undefined.parts",
        accentColor: "#7C3AED",
        bgColor: "#0F0F1A",
      }}
    />
  );
};
