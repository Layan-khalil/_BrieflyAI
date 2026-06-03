"use client";
import { SummaryResult, VideoMetadata } from "@/lib/api";
import ExportButtons from "./ExportButtons";

interface Props {
  result: SummaryResult;
  metadata: VideoMetadata | null;
}

export default function ResultCard({ result, metadata }: Props) {
  return (
    <div className="w-full max-w-2xl mx-auto flex flex-col gap-6 pb-16">
      {metadata && (
        <div className="flex gap-4 items-start">
          {metadata.thumbnail && (
            <img
              src={metadata.thumbnail}
              alt="thumbnail"
              className="w-24 h-16 object-cover rounded-lg"
            />
          )}
          <div>
            <p dir="auto" className="text-white font-medium text-sm leading-snug">{metadata.title}</p>
            <p className="text-zinc-500 text-xs mt-1">{metadata.channel}</p>
            <span className="text-xs text-zinc-600 mt-1 inline-block">
              via {metadata.transcript_source === "whisper" ? "Whisper AI" : "Subtitles"}
            </span>
          </div>
        </div>
      )}

      <section>
        <h3 className="text-xs text-zinc-500 uppercase tracking-widest mb-2">Summary</h3>
        <p dir="auto" className="text-zinc-200 text-sm leading-relaxed">{result.summary}</p>
      </section>

      <section>
        <h3 className="text-xs text-zinc-500 uppercase tracking-widest mb-3">Key Insights</h3>
        <ul className="flex flex-col gap-2">
          {result.key_insights.map((insight, i) => (
            <li key={i} dir="auto" className="flex gap-3 text-sm text-zinc-300">
              <span className="text-zinc-600 mt-0.5 shrink-0">→</span>
              <span>{insight}</span>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h3 className="text-xs text-zinc-500 uppercase tracking-widest mb-3">Notes</h3>
        <ul className="flex flex-col gap-2">
          {result.bullet_notes.map((note, i) => (
            <li key={i} dir="auto" className="flex gap-3 text-sm text-zinc-300">
              <span className="text-zinc-600 shrink-0">•</span>
              <span>{note}</span>
            </li>
          ))}
        </ul>
      </section>

      {result.timestamps?.length > 0 && (
        <section>
          <h3 className="text-xs text-zinc-500 uppercase tracking-widest mb-3">Timestamps</h3>
          <div className="flex flex-col gap-2">
            {result.timestamps.map((t, i) => (
              <div key={i} className="flex gap-3 text-sm">
                <span className="text-zinc-500 font-mono text-xs w-12 shrink-0 pt-0.5">{t.time}</span>
                <span dir="auto" className="text-zinc-300">{t.topic}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      <ExportButtons result={result} metadata={metadata} />
    </div>
  );
}