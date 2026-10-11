import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DataTable, type Column } from "./DataTable";

interface Row {
  readonly id: string;
  readonly partner: string;
  readonly items: number;
}

const columns: readonly Column<Row>[] = [
  { key: "partner", header: "Partner", cell: (r) => r.partner },
  { key: "items", header: "Items", cell: (r) => r.items, numeric: true },
];

describe("DataTable", () => {
  it("renders a captioned table with column headers and rows", () => {
    render(
      <DataTable
        caption="Items per partner"
        columns={columns}
        rows={[{ id: "1", partner: "Northlight Sport", items: 12 }]}
        rowKey={(r) => r.id}
      />,
    );

    const table = screen.getByRole("table", { name: "Items per partner" });
    expect(within(table).getByRole("columnheader", { name: "Partner" })).toHaveAttribute(
      "scope",
      "col",
    );
    expect(within(table).getByRole("cell", { name: "12" })).toHaveAttribute("data-numeric");
  });

  it("teaches what will appear when there are no rows", () => {
    render(
      <DataTable
        caption="Items per partner"
        columns={columns}
        rows={[]}
        rowKey={(r) => r.id}
        empty="Items appear here as partners publish."
      />,
    );

    expect(screen.getByText("Items appear here as partners publish.")).toBeInTheDocument();
  });
});
