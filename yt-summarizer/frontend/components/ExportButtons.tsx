"use client";
import { SummaryResult, VideoMetadata } from "@/lib/api";

interface Props {
  result: SummaryResult;
  metadata: VideoMetadata | null;
}

export default function ExportButtons({ result, metadata }: Props) {
  const buildText = () => {
    return `# ${metadata?.title || "Video Summary"}
Channel: ${metadata?.channel || ""}

## Summary
${result.summary}

## Key Insights
${result.key_insights.map((i) => `• ${i}`).join("\n")}

## Notes
${result.bullet_notes.map((n) => `• ${n}`).join("\n")}

## Timestamps
${result.timestamps.map((t) => `[${t.time}] ${t.topic}`).join("\n")}
`;
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(buildText());
  };

  const handleExport = () => {
    const blob = new Blob([buildText()], { type: "text/plain" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "summary.txt";
    a.click();
  };

  return (
    <div className="flex gap-3 mt-6">
      <button
        onClick={handleCopy}
        className="flex-1 py-2 rounded-lg border border-zinc-700 text-sm text-zinc-300 hover:border-zinc-500 hover:text-white transition-all"
      >
        Copy
      </button>
      <button
        onClick={handleExport}
        className="flex-1 py-2 rounded-lg bg-white text-black text-sm font-medium hover:bg-zinc-200 transition-all"
      >
        Export .txt
      </button>
    </div>
  );
}