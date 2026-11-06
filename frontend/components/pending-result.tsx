import { PLATFORM_NAMES } from "@/lib/labels";
import type { Platform } from "@/lib/types";

export function PendingResult({ platform }: { platform: Platform }) {
  return (
    <article
      className="flex flex-col gap-3 rounded-xl border border-dashed border-gray-300 bg-white p-4"
      aria-busy="true"
    >
      <header className="flex items-center justify-between gap-2">
        <h3 className="font-semibold">{PLATFORM_NAMES[platform]}</h3>
        <span className="animate-pulse rounded-full bg-gray-100 px-2.5 py-0.5 text-xs text-gray-500">
          Searching…
        </span>
      </header>
      <div className="h-16 animate-pulse rounded-lg bg-gray-100" />
    </article>
  );
}
