/*
 * THESIS: the item annotated, on paper: its words large, the seal above, each claim's evidence in
 * the margin and its life beneath; refuses a key-value dump of a JSON record.
 * OWN-WORLD: the board's paper twin: the same hairlines, square keys and signal lamps, printed in
 * ink on stone for anyone outside the gallery.
 * STORY: someone holding a graphic asks whether it is real; the seal answers first, then what it
 * said, what it rests on, who wrote and checked it, and what became of it.
 * FORM: annotated item, candidate 6 of 7; seed 310d9828.
 */
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { Verify } from "@/components/provenance/Verify";
import { isItemId } from "@/lib/itemId";

export const metadata: Metadata = {
  title: "Verify a graphic · Fourth Official",
  description:
    "Check that a broadcast graphic is what the studio published, and what became of it.",
  robots: { index: false },
};

async function Checked({ params }: { readonly params: Promise<{ itemId: string }> }) {
  const { itemId } = await params;
  if (!isItemId(itemId)) notFound();
  return <Verify itemId={itemId} />;
}

export default function VerifyPage({ params }: PageProps<"/verify/[itemId]">) {
  return (
    <Suspense fallback={<div data-theme="paper" className="paper" />}>
      <Checked params={params} />
    </Suspense>
  );
}
