import type { ReactNode } from "react";

export interface Column<Row> {
  readonly key: string;
  readonly header: string;
  readonly cell: (row: Row) => ReactNode;
  /** Right-aligned, tabular figures. */
  readonly numeric?: boolean;
}

interface DataTableProps<Row> {
  readonly caption: string;
  readonly columns: readonly Column<Row>[];
  readonly rows: readonly Row[];
  readonly rowKey: (row: Row) => string;
  /** What will appear here, and when; shown instead of an empty body. */
  readonly empty?: ReactNode;
  /** Keep the caption for assistive technology only. */
  readonly hideCaption?: boolean;
  /** A closing row, by column key; the first column's cell heads the row. */
  readonly totals?: Readonly<Record<string, ReactNode>>;
}

export function DataTable<Row>({
  caption,
  columns,
  rows,
  rowKey,
  empty,
  hideCaption = false,
  totals,
}: DataTableProps<Row>) {
  return (
    <table className="data-table">
      <caption className={hideCaption ? "sr-only" : "data-table__caption"}>{caption}</caption>
      <thead>
        <tr>
          {columns.map((column) => (
            <th key={column.key} scope="col" data-numeric={column.numeric || undefined}>
              {column.header}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.length === 0 ? (
          <tr>
            <td colSpan={columns.length} className="data-table__empty">
              {empty ?? "Nothing to show yet."}
            </td>
          </tr>
        ) : (
          rows.map((row) => (
            <tr key={rowKey(row)}>
              {columns.map((column) => (
                <td key={column.key} data-numeric={column.numeric || undefined}>
                  {column.cell(row)}
                </td>
              ))}
            </tr>
          ))
        )}
      </tbody>
      {totals && (
        <tfoot>
          <tr>
            {columns.map((column, i) =>
              i === 0 ? (
                <th key={column.key} scope="row">
                  {totals[column.key]}
                </th>
              ) : (
                <td key={column.key} data-numeric={column.numeric || undefined}>
                  {totals[column.key]}
                </td>
              ),
            )}
          </tr>
        </tfoot>
      )}
    </table>
  );
}
