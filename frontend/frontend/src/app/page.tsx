import Link from "next/link";

export default function HomePage() {
  return (
    <main style={{ padding: "2rem", maxWidth: "800px", margin: "0 auto" }}>
      <h1>Enterprise Platform</h1>
      <p style={{ marginTop: "1rem", color: "#6b7280" }}>
        Internal tooling for request management and HITL approval workflows.
      </p>
      <nav style={{ marginTop: "2rem", display: "flex", gap: "1rem" }}>
        <Link href="/hitl">HITL Approval Queue</Link>
        <Link href="/requests">Requests</Link>
      </nav>
    </main>
  );
}
