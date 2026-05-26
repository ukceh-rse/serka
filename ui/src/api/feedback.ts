export async function submitFeedback(payload: Record<string, unknown>): Promise<void> {
  const res = await fetch('/v1/feedback/submit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`Feedback failed: ${res.statusText}`)
}
