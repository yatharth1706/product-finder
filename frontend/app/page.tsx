"use client";

import { MarketplaceResult } from "@/components/marketplace-result";
import { PendingResult } from "@/components/pending-result";
import { SearchForm, type Example } from "@/components/search-form";
import { SourceProduct } from "@/components/source-product";
import { useProductSearch } from "@/hooks/use-product-search";

const CATEGORIES = [
  ["Smartphones", "Flipkart, Croma"],
  ["Televisions", "Flipkart, Croma"],
  ["Sneakers", "Flipkart, Myntra"],
  ["T-shirts, polos, jerseys", "Flipkart, Myntra"],
];

const EXAMPLES: Example[] = [
  { label: "Phone", url: "https://www.amazon.in/dp/B0GWLJL55D" },
  { label: "TV", url: "https://www.amazon.in/dp/B0GTZ9TSDJ" },
  { label: "Sold-out phone", url: "https://www.amazon.in/dp/B0BT9FDZ8N" },
  { label: "Sneakers", url: "https://www.amazon.in/dp/B0FQN7T937" },
  { label: "Polo", url: "https://www.amazon.in/dp/B0G4B2W8FH" },
];

export default function Home() {
  const { product, platforms, results, error, running, start } = useProductSearch();
  const idle = !running && !product && !error;

  return (
    <main className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 py-12">
      <header>
        <h1 className="text-3xl font-semibold tracking-tight">Product Finder</h1>
        <p className="mt-2 text-gray-600">
          Paste an Amazon link. We look for the exact same product on other stores and tell you
          if you can buy it there.
        </p>
      </header>

      <SearchForm onSearch={start} disabled={running} examples={EXAMPLES} />

      {error && (
        <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">
          {error}
        </p>
      )}

      {running && !product && (
        <p className="animate-pulse text-sm text-gray-500" aria-live="polite">
          Reading the Amazon page…
        </p>
      )}

      {product && <SourceProduct product={product} />}

      {platforms.length > 0 && (
        <section className="grid gap-3 sm:grid-cols-2" aria-label="Results" aria-live="polite">
          {platforms.map((platform) => {
            const result = results[platform];
            return result ? (
              <MarketplaceResult key={platform} result={result} />
            ) : (
              <PendingResult key={platform} platform={platform} stopped={!running} />
            );
          })}
        </section>
      )}

      {idle && (
        <section className="text-sm text-gray-600">
          <h2 className="mb-2 font-medium text-gray-900">What we support</h2>
          <ul className="grid gap-1">
            {CATEGORIES.map(([category, stores]) => (
              <li key={category}>
                {category} <span className="text-gray-400">→ {stores}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
