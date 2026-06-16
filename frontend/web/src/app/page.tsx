import Link from "next/link";

import { RunLookupForm } from "@/components/runs/RunLookupForm";

export default function HomePage() {
  return (
    <main style={{ padding: "2rem", maxWidth: "800px", margin: "0 auto" }}>
      <h1>Enterprise Platform</h1>
      <p style={{ marginTop: "1rem", color: "#6b7280" }}>
        Internal tooling for request management and HITL approval workflows.
      </p>
      <nav style={{ marginTop: "2rem", display: "flex", gap: "1rem" }}>
        <Link href="/hitl">HITL Approval Queue</Link>
        <Link href="/governance">SLO &amp; Error Budget</Link>
        {/* "/requests" route not implemented yet — dead typedRoutes link broke `next build`. */}
      </nav>
      <section style={{ marginTop: "2rem" }}>
        <h2 style={{ fontSize: "1rem" }}>Run trace</h2>
        <p style={{ color: "#6b7280", fontSize: "0.875rem", marginTop: "0.25rem" }}>
          Look up the execution trace for a submitted request.
        </p>
        <RunLookupForm />
      </section>
    </main>
  );
}
