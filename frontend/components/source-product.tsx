import Image from "next/image";
import { ATTRIBUTE_NAMES } from "@/lib/labels";
import type { Product } from "@/lib/types";

export function SourceProduct({ product }: { product: Product }) {
  return (
    <section className="flex gap-4 rounded-xl border border-gray-200 bg-white p-4">
      {product.image_url && (
        <Image
          src={product.image_url}
          alt=""
          width={96}
          height={96}
          className="h-24 w-24 shrink-0 object-contain"
        />
      )}
      <div className="min-w-0">
        <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
          On Amazon · {product.category}
        </p>
        <h2 className="mt-1 font-semibold">
          {product.brand} {product.model}
        </h2>
        <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-gray-600">
          {Object.entries(product.attributes).map(([name, value]) => (
            <div key={name} className="flex gap-1">
              <dt>{ATTRIBUTE_NAMES[name] ?? name}:</dt>
              <dd className="font-medium text-gray-900">{value}</dd>
            </div>
          ))}
        </dl>
        <a
          href={product.url}
          target="_blank"
          rel="noreferrer"
          className="mt-2 inline-block text-sm text-gray-500 underline"
        >
          View on Amazon
        </a>
      </div>
    </section>
  );
}
