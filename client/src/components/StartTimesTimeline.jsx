import React, { useEffect, useMemo, useState } from "react";
import { MdChevronLeft, MdChevronRight } from "react-icons/md";

export default function StartTimesTimeline({ hasSource }) {
  const [rows, setRows] = useState([]);

  useEffect(() => {
    if (!hasSource) setRows([]);
  }, [hasSource]);
  useEffect(() => {
  const clear = () => setRows([]);
  window.addEventListener("vp:clear-start-times", clear);
  return () => window.removeEventListener("vp:clear-start-times", clear);
}, []);

  // Listen for add-start-time events
  useEffect(() => {
    const handler = (e) => {
      const t = e.detail?.time;
      if (t == null || !isFinite(t)) return;

      const FPS = 30;
      const timeKey = Math.round(t * FPS) / FPS;

      const newEntry = {
        id: crypto?.randomUUID?.() ?? Date.now(),
        raw: timeKey,
        clock: fmtClock(timeKey),
      };

      setRows((prev) => {
        const next = [...prev, newEntry];
        next.sort((a, b) => a.raw - b.raw);
        return next;
      });
    };

    window.addEventListener("vp:add-start-time", handler);
    return () => window.removeEventListener("vp:add-start-time", handler);
  }, []);

  const fmtClock = (s) => {
    const ms = Math.floor((s % 1) * 100);
    const sec = Math.floor(s) % 60;
    const min = Math.floor(s / 60);
    return `${String(min).padStart(2, "0")}:${String(sec).padStart(2, "0")}.${String(ms).padStart(2, "0")}`;
  };

  // Search/filter
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter((r) => r.clock.toLowerCase().includes(q));
  }, [rows, query]);

  // Selection
  const [selected, setSelected] = useState(new Set());
  const isSelected = (id) => selected.has(id);

  const toggle = (id) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const toggleAllFiltered = () => {
    setSelected((prev) => {
      const ids = filtered.map((r) => r.id);
      const allSelected = ids.every((id) => prev.has(id));
      const next = new Set(prev);
      for (const id of ids) {
        allSelected ? next.delete(id) : next.add(id);
      }
      return next;
    });
  };

  const deleteSelected = () => {
    setRows((prev) => prev.filter((r) => !selected.has(r.id)));
    setSelected(new Set());
  };

  // Export helpers
  const download = (filename, text, type) => {
    const blob = new Blob([text], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const toCSV = () => {
    let csv = "StartTime\n";
    for (const r of rows) csv += `${r.clock}\n`;
    return csv;
  };

  const exportCSV = () =>
    download(`start_times_${Date.now()}.csv`, toCSV(), "text/csv");

  const exportJSON = () =>
    download(
      `start_times_${Date.now()}.json`,
      JSON.stringify(rows.map((r) => ({ StartTime: r.clock })), null, 2),
      "application/json"
    );

  // Pagination – matches AnnotationTimeline
  const PAGE_SIZE = 10;
  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageStart = (page - 1) * PAGE_SIZE;
  const pageRows = filtered.slice(pageStart, pageStart + PAGE_SIZE);

  useEffect(() => setPage(1), [filtered]);

  if (!hasSource) return null;

  return (
    <section className="timeline">
      <h2>Start Times</h2>

      {/* Filters row – matches annotation UI */}
      <div
        className="timeline__filters"
        style={{
          display: "grid",
          gap: 8,
          gridTemplateColumns: "1fr 180px",
          marginBottom: 12,
        }}
      >
        <input
          type="text"
          placeholder="Search…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />

        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button
            className="btn--export"
            onClick={exportJSON}
            disabled={rows.length === 0}
          >
            Export JSON
          </button>
          <button
            className="btn--export"
            onClick={exportCSV}
            disabled={rows.length === 0}
          >
            Export CSV
          </button>
        </div>
      </div>

      {/* Buttons row – matches annotation buttons */}
      <div className="timeline__buttons" style={{ marginBottom: 12 }}>
        <button onClick={toggleAllFiltered}>
          {filtered.length > 0 &&
          filtered.every((r) => selected.has(r.id))
            ? "Unselect All (Filtered)"
            : "Select All (Filtered)"}
        </button>

        <button
          className="btn--danger"
          onClick={deleteSelected}
          disabled={selected.size === 0}
        >
          Delete Selected
        </button>
      </div>

      {/* Table identical to AnnotationTimeline */}
      {filtered.length === 0 ? (
        <p className="timeline__empty">No start times added.</p>
      ) : (
        <>
          <table className="timeline__table">
            <thead>
              <tr>
                <th style={{ width: 28 }}>
                  <input
                    type="checkbox"
                    checked={
                      filtered.length > 0 &&
                      filtered.every((r) => selected.has(r.id))
                    }
                    onChange={toggleAllFiltered}
                  />
                </th>
                <th style={{ width: 160 }}>Start Time</th>
                <th style={{ width: 80 }}></th>
              </tr>
            </thead>

            <tbody>
              {pageRows.map((r) => (
                <tr key={r.id}>
                  <td>
                    <input
                      type="checkbox"
                      checked={isSelected(r.id)}
                      onChange={() => toggle(r.id)}
                    />
                  </td>

                  <td>{r.clock}</td>

                  <td>
                    <button
                      className="btn--danger"
                      onClick={() => {
                        setRows((prev) => prev.filter((x) => x.id !== r.id));
                        setSelected((prev) => {
                          const next = new Set(prev);
                          next.delete(r.id);
                          return next;
                        });
                      }}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {totalPages > 1 && (
            <div className="pager">
              <button
                className="pagerBtn"
                onClick={() => page > 1 && setPage(page - 1)}
                disabled={page <= 1}
              >
                <MdChevronLeft size={20} />
              </button>

              <span className="pagerLabel">
                {page} of {totalPages}
              </span>

              <button
                className="pagerBtn"
                onClick={() => page < totalPages && setPage(page + 1)}
                disabled={page >= totalPages}
              >
                <MdChevronRight size={20} />
              </button>
            </div>
          )}
        </>
      )}
    </section>
  );
}
