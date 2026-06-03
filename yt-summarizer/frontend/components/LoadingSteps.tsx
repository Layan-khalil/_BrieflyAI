"use client";
import { useEffect, useState } from "react";

const steps = [
  "Fetching video metadata...",
  "Extracting transcript...",
  "Analyzing with Gemini...",
  "Building insights...",
];

export default function LoadingSteps() {
  const [current, setCurrent] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrent((prev) => (prev < steps.length - 1 ? prev + 1 : prev));
    }, 2500);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex flex-col gap-3 py-8">
      {steps.map((step, i) => (
        <div
          key={i}
          className={`flex items-center gap-3 text-sm transition-all duration-500 ${
            i < current
              ? "text-green-400"
              : i === current
              ? "text-white"
              : "text-zinc-600"
          }`}
        >
          <span className="w-5 h-5 flex items-center justify-center">
            {i < current ? (
              "✓"
            ) : i === current ? (
              <span className="w-3 h-3 rounded-full bg-white animate-pulse block" />
            ) : (
              <span className="w-3 h-3 rounded-full bg-zinc-700 block" />
            )}
          </span>
          {step}
        </div>
      ))}
    </div>
  );
}