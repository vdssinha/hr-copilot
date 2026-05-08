"use client";

interface SQLResultTableProps {
  rows: Record<string, unknown>[];
  sql?: string;
  showSQL?: boolean;
}

export function SQLResultTable({ rows, sql, showSQL }: SQLResultTableProps) {
  if (!rows?.length) return null;
  const cols = Object.keys(rows[0]);
  return (
    <div className="mt-2">
      {showSQL && sql && (
        <details className="mb-2">
          <summary className="text-xs text-gray-400 cursor-pointer">Show SQL</summary>
          <pre className="text-xs bg-gray-900 text-green-400 p-2 rounded mt-1 overflow-x-auto">{sql}</pre>
        </details>
      )}
      <div className="overflow-x-auto rounded border border-gray-200">
        <table className="text-xs w-full">
          <thead className="bg-gray-50">
            <tr>
              {cols.map((c) => (
                <th key={c} className="px-3 py-1.5 text-left font-semibold text-gray-600 border-b border-gray-200">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-gray-50"}>
                {cols.map((c) => (
                  <td key={c} className="px-3 py-1.5 text-gray-700 border-b border-gray-100">
                    {String(row[c] ?? "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-gray-400 mt-1">{rows.length} row(s)</p>
    </div>
  );
}
