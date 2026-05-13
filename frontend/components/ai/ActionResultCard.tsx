"use client";

interface ActionResultCardProps {
  action: string;
  success: boolean;
  data?: Record<string, unknown>;
}

export function ActionResultCard({ action, success, data }: ActionResultCardProps) {
  return (
    <div
      className={`mt-2 rounded border px-3 py-2 text-xs ${
        success ? "border-green-200 bg-green-50 text-green-800" : "border-red-200 bg-red-50 text-red-800"
      }`}
    >
      <span className="font-semibold">{success ? "✓" : "✗"} {action.replace(/_/g, " ")}</span>
      {data && (
        <ul className="mt-1 space-y-0.5 text-gray-600">
          {Object.entries(data).map(([k, v]) => (
            <li key={k}>
              <span className="font-medium">{k}:</span>{" "}
              {v !== null && typeof v === "object" && !Array.isArray(v)
                ? Object.entries(v as Record<string, unknown>)
                    .map(([sk, sv]) => `${sk}: ${sv}`)
                    .join(" · ")
                : String(v ?? "")}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
