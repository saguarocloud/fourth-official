import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { foldBroadcast, instant, PARTNERS, type Program, rundown } from "@/domain/broadcast";

import { formatMatchMinute } from "@/lib/format";

import { CorrectionStrap, LowerThird, ScoreBug } from "./Graphics";
import { PartnerKeys } from "./PartnerKeys";
import { ProgramMonitor } from "./ProgramMonitor";
import { Rundown } from "./Rundown";
import { FEED, itemOf } from "./testing";

const NORTHLIGHT = PARTNERS[0]!;
const NOTHING: Program = { lowerThird: null, strap: null, score: null };

describe("LowerThird", () => {
  it("shows the partner's words and its label exactly as the policy writes it", () => {
    render(<LowerThird item={itemOf("tribuna-austral", "lower_third")} />);

    expect(screen.getByText("Generado con IA")).toBeInTheDocument();
    expect(screen.getByText(/^Gol de /)).toHaveAttribute("lang", "es-MX");
  });

  it("shows no label when the policy shows none", () => {
    const item = itemOf("northlight-sport", "lower_third");
    const reviewed = { ...item, overlay: { ...item.overlay, disclosure: null } };
    render(<LowerThird item={reviewed} />);

    expect(screen.queryByText("AI-generated")).not.toBeInTheDocument();
  });
});

describe("CorrectionStrap", () => {
  it("sets the lead apart from what changed", () => {
    render(<CorrectionStrap item={itemOf("rheinblick-sport", "correction_strap")} />);

    expect(screen.getByText("KORREKTUR").tagName).toBe("STRONG");
  });

  it("shows a strap without a lead as it is", () => {
    const item = itemOf("northlight-sport", "correction_strap");
    const plain = {
      ...item,
      overlay: {
        ...item.overlay,
        content: { template: "correction_strap", text: "Score updated" },
      },
    } as typeof item;
    render(<CorrectionStrap item={plain} />);

    expect(screen.getByText("Score updated")).toBeInTheDocument();
  });
});

describe("ScoreBug", () => {
  it("writes the score the partner's market's way", () => {
    render(<ScoreBug item={itemOf("rheinblick-sport", "score_bug", 1)} />);

    expect(screen.getByText("1:0")).toBeInTheDocument();
    expect(screen.getByText("12:26")).toBeInTheDocument();
  });

  it("runs with the match clock when given one", () => {
    render(<ScoreBug item={itemOf("rheinblick-sport", "score_bug", 1)} clock="25:08" />);

    expect(screen.getByText("25:08")).toBeInTheDocument();
    expect(screen.queryByText("12:26")).not.toBeInTheDocument();
  });
});

describe("ProgramMonitor", () => {
  const third = itemOf("northlight-sport", "lower_third");
  const strap = itemOf("northlight-sport", "correction_strap");

  it("lights the tally when a graphic is on air", () => {
    render(
      <ProgramMonitor
        partner={NORTHLIGHT}
        program={{ ...NOTHING, lowerThird: third }}
        mode="program"
        clock={null}
        guides={false}
      />,
    );

    expect(screen.getByRole("heading", { name: "Program: Northlight Sport" })).toBeInTheDocument();
    expect(document.querySelector(".monitor__tally[data-lit]")).not.toBeNull();
    expect(screen.getByLabelText("Match clock 00:00")).toBeInTheDocument();
  });

  it("lets a correction strap preempt the lower third", () => {
    render(
      <ProgramMonitor
        partner={NORTHLIGHT}
        program={{ ...NOTHING, lowerThird: third, strap }}
        mode="program"
        clock={null}
        guides={false}
      />,
    );

    expect(document.querySelector(".gfx-strap")).not.toBeNull();
    expect(document.querySelector(".gfx-third")).toBeNull();
  });

  it("marks a held graphic in preview, and shows the safe areas when asked", () => {
    const held = itemOf("tribuna-austral", "lower_third");
    render(
      <ProgramMonitor
        partner={PARTNERS[1]!}
        program={{ ...NOTHING, lowerThird: held }}
        mode="preview"
        clock={null}
        guides
      />,
    );

    expect(screen.getByText("Pending approval · held off air")).toBeInTheDocument();
    expect(document.querySelectorAll(".monitor__guide")).toHaveLength(2);
    expect(document.querySelector(".monitor__tally[data-lit]")).toBeNull();
  });
});

describe("Rundown", () => {
  const rows = rundown(foldBroadcast(FEED));

  it("explains itself when there is nothing yet", () => {
    render(<Rundown rows={[]} partner="northlight-sport" selected={null} onSelect={() => {}} />);

    expect(screen.getByText(/No graphics yet/)).toBeInTheDocument();
  });

  it("lists each moment with every partner's version and state", () => {
    render(<Rundown rows={rows} partner="tribuna-austral" selected={null} onSelect={() => {}} />);

    expect(screen.getAllByRole("row")).toHaveLength(rows.length + 1);
    const headers = screen.getAllByRole("columnheader").map((h) => h.textContent);
    expect(headers).toEqual([
      "Time",
      "Moment",
      "NLSNorthlight Sport",
      "TRATribuna Austral",
      "RHBRheinblick Sport",
    ]);
    expect(screen.getAllByText("Pending approval").length).toBeGreaterThan(0);
    expect(document.querySelector('[lang="de-DE"]')).not.toBeNull();
  });

  it("previews the row chosen", () => {
    const onSelect = vi.fn();
    render(
      <Rundown
        rows={rows}
        partner="northlight-sport"
        selected={rows[0]!.key}
        onSelect={onSelect}
      />,
    );
    const buttons = screen.getAllByRole("rowheader").map((h) => within(h).getByRole("button"));

    expect(buttons[0]).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(buttons[1]!);
    expect(onSelect).toHaveBeenCalledWith(rows[1]!.key);
  });

  it("says a graphic whose time has passed was published", () => {
    const row = rows.find((r) => r.byPartner["northlight-sport"]?.state === "on_air")!;
    const out = row.byPartner["northlight-sport"]!.overlay.outAt;
    render(
      <Rundown
        rows={[row]}
        partner="northlight-sport"
        selected={null}
        onSelect={() => {}}
        now={instant(out) + 1}
      />,
    );

    expect(screen.getAllByText("Published").length).toBeGreaterThan(0);
    expect(screen.queryByText("On air")).not.toBeInTheDocument();
  });

  it("says a graphic not yet in is queued, and no moment repeats its partner's words", () => {
    const row = rows.find((r) => r.kind === "insight")!;
    const inAt = row.byPartner["northlight-sport"]!.overlay.inAt;
    render(
      <Rundown
        rows={[row]}
        partner="northlight-sport"
        selected={null}
        onSelect={() => {}}
        now={instant(inAt) - 1}
      />,
    );

    expect(screen.getAllByText("Queued")).toHaveLength(2);
    expect(screen.getByRole("rowheader").querySelector(".rundown__label")?.textContent).toBe(
      row.label,
    );
    expect(screen.getByRole("rowheader").querySelector("svg")).not.toBeNull();
  });

  it("previews a partner's version from its own cell", () => {
    const onSelect = vi.fn();
    const onPartner = vi.fn();
    const [row] = rows;
    render(
      <Rundown
        rows={[row!]}
        partner="northlight-sport"
        selected={null}
        onSelect={onSelect}
        onPartner={onPartner}
      />,
    );

    fireEvent.click(
      screen.getByRole("button", { name: /^Preview Rheinblick Sport, On air: KORREKTUR/ }),
    );
    expect(onSelect).toHaveBeenCalledWith(row!.key);
    expect(onPartner).toHaveBeenCalledWith("rheinblick-sport");
  });

  it("names each moment by its kind, time and words, and each version by its state", () => {
    const row = rows.find((r) => r.kind === "insight" && r.label === "Goal")!;
    render(<Rundown rows={[row]} partner="northlight-sport" selected={null} onSelect={() => {}} />);

    expect(
      screen.getByRole("button", {
        name: `Goal, ${formatMatchMinute(row.at.minute, row.at.period)}: ${row.title}`,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: /^Preview Tribuna Austral, Pending approval, AI-labelled: /,
      }),
    ).toBeInTheDocument();
  });

  it("says when a partner was sent nothing", () => {
    const [row] = rows;
    const partial = {
      ...row!,
      byPartner: { "northlight-sport": row!.byPartner["northlight-sport"] },
    };
    render(
      <Rundown rows={[partial]} partner="northlight-sport" selected={null} onSelect={() => {}} />,
    );

    expect(screen.getAllByText("Not sent")).toHaveLength(2);
  });
});

describe("PartnerKeys", () => {
  it("presses the partner on the monitor and lights the ones on air", () => {
    const onChoose = vi.fn();
    render(
      <PartnerKeys
        current="rheinblick-sport"
        onAir={new Set(["northlight-sport"] as const)}
        onChoose={onChoose}
      />,
    );

    expect(screen.getByRole("button", { name: /Rheinblick Sport/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: /Northlight Sport.*on air/ })).toHaveAttribute(
      "aria-keyshortcuts",
      "1",
    );
    expect(screen.getByRole("button", { name: /Tribuna Austral/ })).toHaveTextContent("TRA");
    fireEvent.click(screen.getByRole("button", { name: /Tribuna Austral/ }));
    expect(onChoose).toHaveBeenCalledWith("tribuna-austral");
  });
});
