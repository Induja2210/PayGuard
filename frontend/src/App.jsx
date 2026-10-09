import { useEffect, useState, useCallback } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

const money = (n) => Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });

function RiskBadge({ risk }) {
  const level = risk >= 80 ? "high" : risk >= 50 ? "medium" : "low";
  return <span className={`badge ${level}`}>{risk}%</span>;
}

function StatusTag({ status }) {
  const text = {
    pending: "Needs review",
    cleared: "Safe",
    confirmed_fraud: "Confirmed fraud",
    marked_safe: "Marked safe",
  }[status] || status;
  return <span className={`tag ${status}`}>{text}</span>;
}

export default function App() {
  const [tab, setTab] = useState("feed");
  const [txns, setTxns] = useState([]);
  const [queue, setQueue] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [selected, setSelected] = useState(null);
  const [live, setLive] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [t, q, m] = await Promise.all([
        fetch(`${API}/transactions?limit=100`).then((r) => r.json()),
        fetch(`${API}/queue`).then((r) => r.json()),
        fetch(`${API}/metrics`).then((r) => r.json()),
      ]);
      setTxns(t);
      setQueue(q);
      setMetrics(m);
      setError("");
    } catch {
      setError("Can't reach the API. Is the backend running on port 8000?");
    }
  }, []);

  // Refresh data every 3 seconds
  useEffect(() => {
    load();
    const id = setInterval(load, 3000);
    return () => clearInterval(id);
  }, [load]);

  // Live feed: add a new payment every 2 seconds
  useEffect(() => {
    if (!live) return;
    const id = setInterval(async () => {
      await fetch(`${API}/simulate`, { method: "POST" });
      load();
    }, 2000);
    return () => clearInterval(id);
  }, [live, load]);

  async function review(id, decision) {
    await fetch(`${API}/transactions/${id}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision }),
    });
    setSelected((s) =>
      s && s.id === id
        ? { ...s, status: decision === "fraud" ? "confirmed_fraud" : "marked_safe" }
        : s
    );
    load();
  }

  const list = tab === "queue" ? queue : txns;

  const chartData = metrics
    ? [
        { name: "Safe", value: metrics.total - metrics.flagged, color: "#16a34a" },
        { name: "Flagged", value: metrics.flagged, color: "#dc2626" },
        { name: "Confirmed", value: metrics.confirmed, color: "#7c3aed" },
        { name: "Marked safe", value: metrics.marked_safe, color: "#0891b2" },
      ]
    : [];

  return (
    <div className="app">
      <header>
        <div>
          <h1>PayGuard</h1>
          <p>Real-time payment fraud monitoring</p>
        </div>
        <button className={live ? "btn stop" : "btn"} onClick={() => setLive(!live)}>
          {live ? "Pause live feed" : "Start live feed"}
        </button>
      </header>

      {error && <div className="error">{error}</div>}

      {metrics && (
        <div className="cards">
          <div className="card"><span>Payments checked</span><strong>{metrics.total}</strong></div>
          <div className="card"><span>Flagged as fraud</span><strong>{metrics.flagged}</strong></div>
          <div className="card"><span>Awaiting review</span><strong>{queue.length}</strong></div>
          <div className="card"><span>Precision</span><strong>{metrics.precision ?? "–"}%</strong></div>
          <div className="card"><span>Recall</span><strong>{metrics.recall ?? "–"}%</strong></div>
        </div>
      )}

      <nav className="tabs">
        <button className={tab === "feed" ? "on" : ""} onClick={() => setTab("feed")}>Live feed</button>
        <button className={tab === "queue" ? "on" : ""} onClick={() => setTab("queue")}>
          Review queue ({queue.length})
        </button>
        <button className={tab === "metrics" ? "on" : ""} onClick={() => setTab("metrics")}>Metrics</button>
      </nav>

      <div className={selected && tab !== "metrics" ? "main split" : "main"}>
        {tab !== "metrics" ? (
          <div className="panel table-wrap">
            {list.length === 0 ? (
              <p className="empty">
                {tab === "queue" ? "No flagged payments waiting." : "No payments yet. Click Start live feed."}
              </p>
            ) : (
              <table>
                <thead>
                  <tr><th>ID</th><th>Time</th><th>Type</th><th>Amount</th><th>Risk</th><th>Status</th></tr>
                </thead>
                <tbody>
                  {list.map((t) => (
                    <tr key={t.id} onClick={() => setSelected(t)} className={selected?.id === t.id ? "active" : ""}>
                      <td>#{t.id}</td>
                      <td>{t.created_at.slice(11)}</td>
                      <td>{t.type}</td>
                      <td>{money(t.amount)}</td>
                      <td><RiskBadge risk={t.risk} /></td>
                      <td><StatusTag status={t.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        ) : (
          <div className="panel">
            <h2>Outcomes</h2>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartData}>
                <XAxis dataKey="name" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="value">
                  {chartData.map((d) => <Cell key={d.name} fill={d.color} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <p className="note">
              Precision: of the payments we flagged, how many were real fraud. Recall: of all real fraud, how many we caught.
            </p>
          </div>
        )}

        {selected && tab !== "metrics" && (
          <aside className="panel detail">
            <div className="detail-head">
              <h2>Payment #{selected.id}</h2>
              <button className="close" onClick={() => setSelected(null)}>✕</button>
            </div>
            <RiskBadge risk={selected.risk} />
            <StatusTag status={selected.status} />

            <h3>Why?</h3>
            <ul>{selected.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>

            <h3>Details</h3>
            <dl>
              <dt>Type</dt><dd>{selected.type}</dd>
              <dt>Amount</dt><dd>{money(selected.amount)}</dd>
              <dt>Sender before</dt><dd>{money(selected.oldbalanceOrg)}</dd>
              <dt>Sender after</dt><dd>{money(selected.newbalanceOrig)}</dd>
              <dt>Receiver before</dt><dd>{money(selected.oldbalanceDest)}</dd>
              <dt>Receiver after</dt><dd>{money(selected.newbalanceDest)}</dd>
            </dl>

            {selected.status === "pending" && (
              <div className="actions">
                <button className="btn danger" onClick={() => review(selected.id, "fraud")}>Confirm fraud</button>
                <button className="btn ghost" onClick={() => review(selected.id, "safe")}>Mark safe</button>
              </div>
            )}
          </aside>
        )}
      </div>
    </div>
  );
}