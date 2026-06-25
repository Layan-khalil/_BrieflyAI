export type SummaryResult = {
  summary: string;
  key_insights: string[];
  bullet_notes: string[];
  timestamps: { time: string; topic: string }[];
};

export type VideoMetadata = {
  title: string;
  channel: string;
  duration: number;
  thumbnail: string;
  transcript_source: "subtitles" | "whisper";
};

export async function streamSummary(
  url: string,
  onMetadata: (m: VideoMetadata) => void,
  onChunk: (text: string) => void,
  onDone: (result: SummaryResult) => void,
  onError: (e: string) => void
) {
  try {
    const isLocal = typeof window !== "undefined" && window.location.hostname === "localhost";
    const baseUrl = isLocal ? "http://localhost:8000" : "https://layan123-brieflyai-space.hf.space";
    const res = await fetch(`${baseUrl}/api/summarize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });

    if (!res.ok) throw new Error(`Server error: ${res.status}`);

    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let fullText = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.trim()) continue;

        if (line.startsWith("data: ")) {
          const data = line.slice(6).trim();
          if (data === "complete") continue;

          try {
            const obj = JSON.parse(data);
            if (obj.title !== undefined) {
              onMetadata(obj as VideoMetadata);
              continue;
            }
          } catch {}

          fullText += data;
          onChunk(data);
        }

        if (line.startsWith("event: done")) {
          try {
            const clean = fullText.replace(/```json|```/g, "").trim();
            const parsed = JSON.parse(clean);
            onDone(parsed);
          } catch {
            onError("Failed to parse AI response");
          }
        }
      }
    }
  } catch (err: any) {
    onError(err.message || "Something went wrong");
  }
}