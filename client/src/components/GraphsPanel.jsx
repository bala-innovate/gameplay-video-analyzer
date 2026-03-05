import React from "react";
import { MdDownload } from "react-icons/md";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  ResponsiveContainer,
} from "recharts";


const COLORS = [
  "#4da3ff",
  "#ff9800",
  "#9c27b0",
  "#4caf50",
  "#f44336",
  "#ffc107",
  "#00bcd4",
  "#e91e63",
];

function downloadJson(obj, filename = "data.json") {
  const blob = new Blob([JSON.stringify(obj, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// Turn { "0": [{move,p},...], ... } into [{ xKey, MOVE1, MOVE2, ... }, ...]
function buildLineData(obj, xKeyName) {
  if (!obj || typeof obj !== "object") return { data: [], moves: [] };

  const moveSet = new Set();

  const rawPoints = Object.entries(obj).map(([xStr, rows]) => {
    const xVal = Number(xStr);
    const arr = Array.isArray(rows) ? rows : [];

    const point = { [xKeyName]: xVal };

    arr.forEach((r) => {
      const move = String(r.move || r.tag || r.label || "UNKNOWN");
      const p = Number(r.p || r.prob || r.probability || 0);
      moveSet.add(move);
      point[move] = p;
    });

    return point;
  });

  const data = rawPoints.sort((a, b) => a[xKeyName] - b[xKeyName]);
  const moves = Array.from(moveSet);
  return { data, moves };
}

function ProbLineChart({
  dataObj,
  xKey,
  xLabel,
  title,
  labelPrefix,
  downloadName,
}) {
  if (!dataObj) return null;

  const { data, moves } = buildLineData(dataObj, xKey);

  if (!data.length || !moves.length) {
    return (
      <div className="gp__chartWrap">
        <h4 className="gp__chartTitle">{title}</h4>
        <div className="gp__empty">No data for this chart.</div>
      </div>
    );
  }

  return (
    <div className="gp__chartWrap">
      <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        marginBottom: 8,
      }}
    >
      <h4 className="gp__chartTitle">{title}</h4>

             <button
          type="button"
          className="gp__downloadBtn"
          onClick={() => downloadJson(dataObj, downloadName || "chart.json")}
          title="Download JSON"
        >
          <MdDownload size={16} />
        </button>
        </div>
      <div style={{ width: "100%", height: 280 }}>
        <ResponsiveContainer>
          <LineChart
            data={data}
            margin={{ top: 10, right: 20, left: 0, bottom: 30 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#2b3240" />
            <XAxis
              dataKey={xKey}
              tick={{ fill: "#a8b3c7", fontSize: 12 }}
              label={{
                value: xLabel,
                position: "insideBottom",
                offset: -20,
                fill: "#a8b3c7",
                fontSize: 12,
              }}
            />
            <YAxis
              tick={{ fill: "#a8b3c7", fontSize: 12 }}
              tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
              label={{
                value: "Probability",
                angle: -90,
                position: "insideLeft",
                offset: 10,
                fill: "#a8b3c7",
                fontSize: 12,
              }}
              domain={[0, 1]}
            />
            <Tooltip
              contentStyle={{
                background: "#1a1f29",
                border: "1px solid #2b3240",
                borderRadius: 8,
                color: "#eaeef7",
              }}
              formatter={(value, name) => [
                `${(value * 100).toFixed(1)}%`,
                name,
              ]}
              labelFormatter={(label) =>
                labelPrefix ? `${labelPrefix}: ${label}` : String(label)
              }
            />
            <Legend
              layout="vertical" verticalAlign="middle" align="right"
              wrapperStyle={{ paddingLeft: 20, color: "#a8b3c7", fontSize: 12,
              }}
            />

            {moves.map((move, idx) => (
              <Line
                key={move}
                type="monotone"
                dataKey={move}
                stroke={COLORS[idx % COLORS.length]}
                strokeWidth={2}
                dot={{ r: 3 }}
                activeDot={{ r: 5 }}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default function GraphsPanel({ results, onClear, hideTitle = false }) {
  const playersObj =
    results?.probs_by_players ??
    results?.probsPlayers ??
    results?.probs_defenderCount;

  const timeObj =
    results?.probs_by_time ??
    results?.probsTime ??
    results?.probs_timeSinceDown;

  if (!playersObj && !timeObj) {
    return (
      <section className="gp">
        <div className="gp__header">
          {!hideTitle && <h3>Analysis</h3>}
          {onClear && (
            <button className="gp__clear" onClick={onClear}>
              Clear
            </button>
          )}
        </div>
        <p className="gp__empty">No results to display.</p>
      </section>
    );
  }

  return (
    <section className="gp">
      <div className="gp__header">
        {!hideTitle && <h3>Analysis</h3>}
        {onClear && (
          <button className="gp__clear" onClick={onClear}>
            Clear
          </button>
        )}
      </div>

      <div className="gp__grid">
        <ProbLineChart
          dataObj={playersObj}
          xKey="players"
          xLabel="Number of players"
          title="Probability vs Number of Players"
          labelPrefix="Players"
          downloadName="probability_vs_players.json"
        />

        <ProbLineChart
          dataObj={timeObj}
          xKey="time"
          xLabel="Time since down started (s)"
          title="Probability vs Time Since Down Started"
          labelPrefix="Time (s)"
          downloadName="probability_vs_time.json"
        />
      </div>
    </section>
  );
}
