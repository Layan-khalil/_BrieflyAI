"use client";
import { useState } from "react";

interface Props {
  onSubmit: (url: string) => void;
  loading: boolean;
}

export default function UrlInput({ onSubmit, loading }: Props) {
  const [value, setValue] = useState("");

  const handleSubmit = () => {
    if (value.trim()) onSubmit(value.trim());
  };

  return (
    <div className="w-full max-w-2xl mx-auto">
      <div className="flex gap-2 items-center bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-3 focus-within:border-zinc-600 transition-all">
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
          placeholder="Paste a YouTube URL..."
          className="flex-1 bg-transparent text-white text-sm outline-none placeholder:text-zinc-600"
          disabled={loading}
        />
        <button
          onClick={handleSubmit}
          disabled={loading || !value.trim()}
          className="text-xs bg-white text-black font-medium px-4 py-1.5 rounded-lg hover:bg-zinc-200 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
        >
          {loading ? "..." : "Summarize"}
        </button>
      </div>
    </div>
  );
}