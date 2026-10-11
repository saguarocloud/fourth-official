import { render, screen, within } from "@testing-library/react";
import axe from "axe-core";
import { describe, expect, it } from "vitest";

import { ANSWERS, DEVELOPMENT, ON_AIR_ID, HELD_ID, RETRACTED_ID, AMENDED_ID } from "./testing";
import { ProvenanceRecord } from "./ProvenanceRecord";

describe("ProvenanceRecord", () => {
  it("leads with the seal: signed and unchanged, by which key", () => {
    render(<ProvenanceRecord answer={ANSWERS[ON_AIR_ID]!} />);

    const seal = screen.getByRole("region", { name: "Verification" });
    expect(seal).toHaveTextContent("Signed and unchanged");
    expect(seal).toHaveTextContent("The studio's key in Azure Key Vault (ES256)");
    expect(seal).toHaveTextContent("Issued by Meridian League Studios");
    expect(seal).toHaveAttribute("data-tone", "verified");
  });

  it("marks a record signed with a development key as such, never green", () => {
    render(<ProvenanceRecord answer={DEVELOPMENT[ON_AIR_ID]!} />);

    const seal = screen.getByRole("region", { name: "Verification" });
    expect(seal).toHaveTextContent("Unchanged, signed with a development key");
    expect(seal).toHaveAttribute("data-tone", "development");
  });

  it("sets the item's words in its own language, with the label it carried", () => {
    render(<ProvenanceRecord answer={ANSWERS[HELD_ID]!} />);

    const headline = screen.getByRole("heading", { level: 2, name: "Gol de Harbour City" });
    expect(headline).toHaveAttribute("lang", "es-MX");
    expect(screen.getByText("Generado con IA")).toBeInTheDocument();
    expect(screen.getByText("Tribuna Austral")).toBeInTheDocument();
    expect(screen.getByText("Pending approval")).toBeInTheDocument();
  });

  it("notes beside each claim the events it rests on", () => {
    render(<ProvenanceRecord answer={ANSWERS[ON_AIR_ID]!} />);

    const claims = within(screen.getByRole("list", { name: "Claims" })).getAllByRole("listitem");
    expect(claims).toHaveLength(2);
    expect(claims[0]).toHaveTextContent("Niklas Navarro-Gil scores for Harbour City at 12': 1–0.");
    expect(claims[0]).toHaveTextContent("Rests on events m42-e0286, m42-e0287");
  });

  it("tells the item's life in order", () => {
    render(<ProvenanceRecord answer={ANSWERS[RETRACTED_ID]!} />);

    const steps = within(screen.getByRole("list", { name: "Its life" })).getAllByRole("listitem");
    expect(steps.map((s) => s.querySelector("h4")?.textContent)).toEqual([
      "Written",
      "Checked",
      "Localised",
      "Pulled",
    ]);
    expect(steps.at(-1)).toHaveTextContent("Pulled by correction c-m42-01");
  });

  it("says which version a remade item replaced", () => {
    render(<ProvenanceRecord answer={ANSWERS[AMENDED_ID]!} />);

    expect(screen.getByText(/Version 2, replacing/)).toBeInTheDocument();
  });

  it("lists the record's facts, with the full hash and signature", () => {
    render(<ProvenanceRecord answer={ANSWERS[ON_AIR_ID]!} />);
    const signed = ANSWERS[ON_AIR_ID]!.provenance!;

    const facts = screen.getByRole("region", { name: "The record" });
    expect(facts).toHaveTextContent(signed.contentHash);
    expect(facts).toHaveTextContent(signed.signature);
    expect(facts).toHaveTextContent(ON_AIR_ID);
    expect(facts).toHaveTextContent("Feed entry 129");
  });

  it("warns plainly when a record does not verify, and keeps showing what it says", () => {
    const answer = {
      ...ANSWERS[ON_AIR_ID]!,
      verification: { valid: false, reason: "the signature does not match" },
    };
    render(<ProvenanceRecord answer={answer} />);

    const seal = screen.getByRole("region", { name: "Verification" });
    expect(seal).toHaveTextContent("Does not verify");
    expect(seal).toHaveTextContent("the signature does not match");
    expect(seal).toHaveAttribute("data-tone", "failed");
    expect(screen.getByRole("heading", { level: 2 })).toBeInTheDocument();
  });

  it("says so when the stored record no longer reads", () => {
    render(
      <ProvenanceRecord
        answer={{
          provenance: null,
          verification: { valid: false, reason: "the stored record no longer reads" },
        }}
      />,
    );

    expect(screen.getByRole("region", { name: "Verification" })).toHaveTextContent(
      "the stored record no longer reads",
    );
    expect(screen.queryByRole("heading", { level: 2 })).toBeNull();
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<ProvenanceRecord answer={ANSWERS[AMENDED_ID]!} />);

    const results = await axe.run(container);
    expect(results.violations).toEqual([]);
  });
});
