import { PLATFORM_NAMES } from "@/lib/labels";
import type { Platform } from "@/lib/types";

/** A marketplace that has not answered yet, or never did if the search stopped. */
export function PendingResult({ platform, stopped }: { platform: Platform; stopped: boolean }) {
  return (
    <article
      className="flex flex-col gap-3 rounded-xl border border-dashed border-gray-300 bg-white p-4"
      aria-busy={!stopped}
    >
      <header className="flex items-center justify-between gap-2">
        <h3 className="font-semibold">{PLATFORM_NAMES[platform]}</h3>
        <span
          className={`rounded-full bg-gray-100 px-2.5 py-0.5 text-xs text-gray-500 ${stopped ? "" : "animate-pulse"}`}
        >
          {stopped ? "No answer" : "Searching…"}
        </span>
      </header>
      {stopped ? (
        <p className="text-sm text-gray-600">The search stopped before this store answered.</p>
      ) : (
        <div className="h-16 animate-pulse rounded-lg bg-gray-100" />
      )}
    </article>
  );
}
