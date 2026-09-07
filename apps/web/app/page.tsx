"use client";

import { FormEvent, useEffect, useState } from "react";

type Audit = {
  id: string;
  status: string;
  goal: string;
  created_at: string;
};

type Finding = {
  id: string;
  title: string;
  severity: string;
  confidence: number;
  description: string;
  recommendation: string;
};

type Recommendation = {
  id: string;
  status: string;
  action_type: string;
  rationale: string;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options?.headers ?? {}) },
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }
  return response.json();
}

export default function Home() {
  const [websiteUrl, setWebsiteUrl] = useState("https://example.com");
  const [projectName, setProjectName] = useState("Website growth workspace");
  const [goal, setGoal] = useState("Improve organic discovery and answer readiness.");
  const [audit, setAudit] = useState<Audit | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!audit || !["queued", "running"].includes(audit.status)) return;
    const timer = window.setInterval(async () => {
      try {
        const nextAudit = await api<Audit>(`/api/v1/audits/${audit.id}`);
        setAudit(nextAudit);
        if (!["queued", "running"].includes(nextAudit.status)) {
          const [nextFindings, nextRecommendations] = await Promise.all([
            api<Finding[]>(`/api/v1/audits/${audit.id}/findings`),
            api<Recommendation[]>(`/api/v1/recommendations?audit_id=${audit.id}`),
          ]);
          setFindings(nextFindings);
          setRecommendations(nextRecommendations);
        }
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "Unable to refresh audit");
      }
    }, 1500);
    return () => window.clearInterval(timer);
  }, [audit]);

  async function startAudit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setFindings([]);
    setRecommendations([]);
    try {
      const project = await api<{ id: string }>("/api/v1/projects", {
        method: "POST",
        body: JSON.stringify({ name: projectName, business_goal: goal }),
      });
      const site = await api<{ id: string }>("/api/v1/sites", {
        method: "POST",
        body: JSON.stringify({ project_id: project.id, url: websiteUrl }),
      });
      const createdAudit = await api<Audit>("/api/v1/audits", {
        method: "POST",
        body: JSON.stringify({ project_id: project.id, site_id: site.id, goal }),
      });
      const queuedAudit = await api<Audit>(`/api/v1/audits/${createdAudit.id}/run`, { method: "POST" });
      setAudit(queuedAudit);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to start audit");
    } finally {
      setLoading(false);
    }
  }

  async function decideRecommendation(id: string, decision: "approve" | "reject") {
    try {
      const result = await api<Recommendation>(`/api/v1/recommendations/${id}/${decision}`, {
        method: "POST",
        body: JSON.stringify({ reason: "Reviewed in the growth workspace" }),
      });
      setRecommendations((current) => current.map((item) => (item.id === id ? result : item)));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to update recommendation");
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand-mark">S</div>
        <div>
          <p className="eyebrow">SIGNAL / GROWTH INTELLIGENCE</p>
          <h1>Turn website evidence into approved momentum.</h1>
        </div>
        <div className="status-pill"><span /> Local control plane</div>
      </header>

      <section className="hero-grid">
        <div className="hero-copy">
          <p className="eyebrow accent">EVIDENCE-FIRST AGENT</p>
          <h2>Find the leaks before you pour in more traffic.</h2>
          <p className="lede">A bounded audit of technical SEO, answer readiness, and content opportunity. Every recommendation keeps its evidence attached and every write stays behind approval.</p>
          <div className="signal-row"><span>01 / Crawl</span><span>02 / Analyze</span><span>03 / Approve</span></div>
        </div>
        <form className="audit-card" onSubmit={startAudit}>
          <div className="card-header"><span>NEW AUDIT</span><span className="mono">v0.1 / controlled</span></div>
          <label>Website URL<input data-testid="website-url" value={websiteUrl} onChange={(event) => setWebsiteUrl(event.target.value)} type="url" required /></label>
          <label>Workspace name<input data-testid="project-name" value={projectName} onChange={(event) => setProjectName(event.target.value)} required /></label>
          <label>Growth objective<textarea data-testid="growth-goal" value={goal} onChange={(event) => setGoal(event.target.value)} rows={3} required /></label>
          <button data-testid="start-audit" disabled={loading} type="submit">{loading ? "Queueing audit..." : "Start evidence sweep"}<span>↗</span></button>
          <p className="form-note">Read-only crawl. No CMS credentials. No production writes.</p>
        </form>
      </section>

      {error && <div className="error-banner">{error}</div>}

      <section className="workspace-grid">
        <div className="panel panel-wide">
          <div className="panel-heading"><div><p className="eyebrow">RUN STATUS</p><h3>{audit ? "Live audit stream" : "Waiting for a signal"}</h3></div>{audit && <span className={`state state-${audit.status}`}>{audit.status.replaceAll("_", " ")}</span>}</div>
          {audit ? <div className="run-summary"><div><span className="metric-label">RUN ID</span><strong className="mono">{audit.id.slice(0, 8)}...</strong></div><div><span className="metric-label">OBJECTIVE</span><strong>{audit.goal}</strong></div><div><span className="metric-label">MODE</span><strong>bounded / human gate</strong></div></div> : <div className="empty-state"><span className="empty-orbit" /><p>Enter a website above to create the first evidence-backed audit.</p></div>}
        </div>
        <div className="panel score-panel"><p className="eyebrow">SIGNAL MIX</p><div className="score-ring"><strong>{findings.length ? Math.max(42, 100 - findings.length * 4) : "--"}</strong><span>readiness</span></div><p className="muted">The score becomes meaningful after the first completed crawl.</p></div>
      </section>

      <section className="results-section">
        <div className="section-heading"><div><p className="eyebrow accent">FINDINGS / {findings.length.toString().padStart(2, "0")}</p><h2>Where attention compounds.</h2></div><p className="section-note">Rules establish facts. NIM adds context. You decide what ships.</p></div>
        <div className="finding-list">{findings.length ? findings.map((finding) => <article className="finding-card" key={finding.id}><div className={`severity severity-${finding.severity}`} /><div className="finding-body"><div className="finding-topline"><span className="eyebrow">{finding.severity} / {(finding.confidence * 100).toFixed(0)}% confidence</span><span className="mono">{finding.id.slice(0, 8)}</span></div><h3>{finding.title}</h3><p>{finding.description}</p><div className="recommendation"><span>RECOMMENDATION</span>{finding.recommendation}</div></div></article>) : <div className="empty-results">Findings will appear here with page evidence and confidence after the crawl.</div>}</div>
      </section>

      <section className="results-section approval-section">
        <div className="section-heading"><div><p className="eyebrow accent">APPROVAL QUEUE / {recommendations.filter((item) => item.status === "pending_approval").length.toString().padStart(2, "0")}</p><h2>Nothing moves without a human.</h2></div><p className="section-note">Approved recommendations are recorded, not silently published.</p></div>
        <div className="approval-list">{recommendations.length ? recommendations.map((recommendation) => <article className="approval-card" key={recommendation.id}><div><span className="eyebrow">{recommendation.action_type}</span><p>{recommendation.rationale}</p></div>{recommendation.status === "pending_approval" ? <div className="approval-actions"><button className="ghost-button" onClick={() => decideRecommendation(recommendation.id, "reject")}>Reject</button><button className="solid-button" onClick={() => decideRecommendation(recommendation.id, "approve")}>Approve</button></div> : <span className={`state state-${recommendation.status}`}>{recommendation.status}</span>}</article>) : <div className="empty-results">Recommendations generated from this audit will wait here for review.</div>}</div>
      </section>
    </main>
  );
}
