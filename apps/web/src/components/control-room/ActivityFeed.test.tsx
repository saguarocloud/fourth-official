import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DEMO_MATCHDAY } from "@/fixtures/matchday";

import { ActivityFeed } from "./ActivityFeed";

describe("ActivityFeed", () => {
  it("announces new entries politely", () => {
    render(<ActivityFeed entries={DEMO_MATCHDAY.activity} partners={DEMO_MATCHDAY.partners} />);

    expect(screen.getByRole("log", { name: "Live activity" })).toHaveAttribute(
      "aria-live",
      "polite",
    );
  });

  it("shows each entry's state, partner and match minute", () => {
    const entry = DEMO_MATCHDAY.activity[0]!;
    render(<ActivityFeed entries={[entry]} partners={DEMO_MATCHDAY.partners} />);
    const item = screen.getByRole("listitem");

    expect(within(item).getByText(entry.text)).toBeInTheDocument();
    // A football minute is not a valid <time> value, so it is plain text.
    expect(item.querySelector("time")).toBeNull();
    expect(within(item).getByText(/^\d+(\+\d+)?'$/)).toBeInTheDocument();
  });

  it("explains what will appear before anything has happened", () => {
    render(<ActivityFeed entries={[]} partners={DEMO_MATCHDAY.partners} />);

    expect(
      screen.getByText(/Published items, approvals and corrections appear here/),
    ).toBeInTheDocument();
  });
});

describe("ActivityFeed labels", () => {
  it("names each entry's state in words, not just icon and colour", () => {
    const entry = { ...DEMO_MATCHDAY.activity[0]!, state: "retracted" as const };
    render(<ActivityFeed entries={[entry]} partners={DEMO_MATCHDAY.partners} />);

    expect(screen.getByText("Retracted")).not.toHaveClass("sr-only");
  });

  it("labels model-generated entries as AI", () => {
    const entry = { ...DEMO_MATCHDAY.activity[0]!, aiGenerated: true };
    render(<ActivityFeed entries={[entry]} partners={DEMO_MATCHDAY.partners} />);

    expect(screen.getByText("AI")).toHaveAttribute(
      "title",
      "AI-generated, verified before publishing",
    );
  });

  it("does not label template output as AI", () => {
    const entry = { ...DEMO_MATCHDAY.activity[0]!, aiGenerated: false };
    render(<ActivityFeed entries={[entry]} partners={DEMO_MATCHDAY.partners} />);

    expect(screen.queryByText("AI")).toBeNull();
  });
});

describe("ActivityFeed order", () => {
  it("lists the newest entry first whatever order it arrives in", () => {
    const [newest, older] = DEMO_MATCHDAY.activity;
    render(<ActivityFeed entries={[older!, newest!]} partners={DEMO_MATCHDAY.partners} />);

    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent(newest!.text);
  });

  it("falls back to the partner id when the partner is unknown", () => {
    const entry = { ...DEMO_MATCHDAY.activity[0]!, partnerId: "northlight" as const };
    render(<ActivityFeed entries={[entry]} partners={[]} />);

    expect(screen.getByText("northlight")).toBeInTheDocument();
  });
});
