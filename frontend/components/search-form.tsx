"use client";

import { useState, type FormEvent } from "react";
import { amazonUrlError } from "@/lib/validation";

export interface Example {
  label: string;
  url: string;
}

export function SearchForm({
  onSearch,
  disabled,
  examples,
}: {
  onSearch: (url: string) => void;
  disabled: boolean;
  examples: Example[];
}) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);

  const tryExample = (example: Example) => {
    setUrl(example.url);
    setError(null);
    onSearch(example.url);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const problem = amazonUrlError(url);
    setError(problem);
    if (!problem) onSearch(url.trim());
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-2">
      <label htmlFor="amazon-url" className="text-sm font-medium text-gray-700">
        Amazon product link
      </label>
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          id="amazon-url"
          type="url"
          inputMode="url"
          placeholder="https://www.amazon.in/dp/..."
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          className="min-w-0 flex-1 rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-gray-900 focus:ring-2 focus:ring-gray-900/10"
          aria-invalid={error !== null}
          aria-describedby={error ? "amazon-url-error" : undefined}
        />
        <button
          type="submit"
          disabled={disabled}
          className="rounded-lg bg-gray-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {disabled ? "Searching…" : "Find it"}
        </button>
      </div>
      {error && (
        <p id="amazon-url-error" className="text-sm text-red-600">
          {error}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-gray-500">Try:</span>
        {examples.map((example) => (
          <button
            key={example.url}
            type="button"
            disabled={disabled}
            onClick={() => tryExample(example)}
            className="rounded-full border border-gray-300 bg-white px-3 py-1 text-gray-700 hover:border-gray-900 disabled:opacity-50"
          >
            {example.label}
          </button>
        ))}
      </div>
    </form>
  );
}
