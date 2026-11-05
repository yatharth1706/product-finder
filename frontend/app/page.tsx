import { BackendStatus } from "@/components/backend-status";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-16">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-3xl font-semibold tracking-tight">Product Finder</h1>
        <BackendStatus />
      </div>
      <p className="text-muted-foreground">
        Find the same product across marketplaces. Paste an Amazon link and we check Flipkart,
        Croma and Myntra for the exact same item.
      </p>
      {/* Search form and results are added in Milestone 8. */}
    </main>
  );
}
