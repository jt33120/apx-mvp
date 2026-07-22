/** The application shell. Story 1.1 ships a single empty route — no feature,
 *  no worklist, no triage table. Those arrive with their own stories and a UX
 *  pass (no UX design contract exists yet). */
export default function App() {
  return (
    <main style={{ padding: "var(--apx-space-2)" }}>
      <h1>APX</h1>
      <p>Scaffold. No feature is wired yet.</p>
    </main>
  );
}
