"use client";

import { MarketplaceResult } from "@/components/marketplace-result";
import { SearchForm } from "@/components/search-form";
import { SourceProduct } from "@/components/source-product";
import { useProductSearch } from "@/hooks/use-product-search";

const CATEGORIES = [
  ["Smartphones", "Flipkart, Croma"],
  ["Televisions", "Flipkart, Croma"],
  ["Sneakers", "Flipkart, Myntra"],
  ["T-shirts, polos, jerseys", "Flipkart, Myntra"],
];

export default function Home() {
  const { job, error, running, start } = useProductSearch();

  return (
    <main className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 py-12">
      <header>
        <h1 className="text-3xl font-semibold tracking-tight">Product Finder</h1>
        <p className="mt-2 text-gray-600">
          Paste an Amazon link. We look for the exact same product on other stores and tell you
          if you can buy it there.
        </p>
      </header>

      <SearchForm onSearch={start} disabled={running} />

      {error && (
        <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">
          {error}
        </p>
      )}

      {job?.status === "failed" && (
        <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">
          {job.error}
        </p>
      )}

      {job?.source_product && <SourceProduct product={job.source_product} />}

      {running && (
        <p className="animate-pulse text-sm text-gray-500" aria-live="polite">
          {job?.source_product ? "Searching other stores…" : "Reading the Amazon page…"}
        </p>
      )}

      {job?.results && (
        <section className="grid gap-3 sm:grid-cols-2" aria-label="Results">
          {job.results.map((result) => (
            <MarketplaceResult key={result.platform} result={result} />
          ))}
        </section>
      )}

      {!job && !running && (
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
