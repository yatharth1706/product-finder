import Image from "next/image";
import { ATTRIBUTE_NAMES, FAILURE_MESSAGES, PLATFORM_NAMES } from "@/lib/labels";
import type { MarketplaceResult as Result, ResultStatus } from "@/lib/types";

const BADGES: Record<ResultStatus, { label: string; className: string }> = {
  in_stock: { label: "In stock", className: "bg-green-100 text-green-800" },
  out_of_stock: { label: "Out of stock", className: "bg-orange-100 text-orange-800" },
  not_listed: { label: "Not listed", className: "bg-gray-100 text-gray-700" },
  failed: { label: "Could not check", className: "bg-red-50 text-red-700" },
};

export function MarketplaceResult({ result }: { result: Result }) {
  const badge =
    result.failure_reason === "availability_unknown"
      ? { label: "Stock unknown", className: "bg-yellow-50 text-yellow-800" }
      : BADGES[result.status];

  return (
    <article className="flex flex-col gap-3 rounded-xl border border-gray-200 bg-white p-4">
      <header className="flex items-center justify-between gap-2">
        <h3 className="font-semibold">{PLATFORM_NAMES[result.platform]}</h3>
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${badge.className}`}>
          {badge.label}
        </span>
      </header>

      {result.url && result.title && (
        <div className="flex gap-3">
          {result.image_url && (
            <Image
              src={result.image_url}
              alt=""
              width={64}
              height={64}
              className="h-16 w-16 shrink-0 object-contain"
            />
          )}
          <div className="min-w-0">
            <a
              href={result.url}
              target="_blank"
              rel="noreferrer"
              className="text-sm font-medium underline-offset-2 hover:underline"
            >
              {result.title}
            </a>
            {result.match && (
              <p className="mt-1 text-xs text-gray-500">
                Match score {result.match.score} ·{" "}
                {Object.entries(result.match.checks)
                  .filter(([, ok]) => ok)
                  .map(([name]) => ATTRIBUTE_NAMES[name] ?? name)
                  .join(", ")}{" "}
                matched
              </p>
            )}
          </div>
        </div>
      )}

      {result.status === "not_listed" && (
        <p className="text-sm text-gray-600">
          Checked {result.candidates_checked} listings; none was exactly this product.
        </p>
      )}
      {result.failure_reason && (
        <p className="text-sm text-gray-600">{FAILURE_MESSAGES[result.failure_reason]}</p>
      )}

      {result.search_url && !result.url && (
        <a
          href={result.search_url}
          target="_blank"
          rel="noreferrer"
          className="text-sm font-medium text-gray-900 underline underline-offset-2"
        >
          {result.status === "failed"
            ? `Search on ${PLATFORM_NAMES[result.platform]} yourself`
            : `See the search on ${PLATFORM_NAMES[result.platform]}`}
        </a>
      )}
    </article>
  );
}
