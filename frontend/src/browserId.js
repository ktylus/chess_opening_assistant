const STORAGE_KEY = 'chess-opening-assistant.browser-id'
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
let fallbackId

export function getBrowserId() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored && UUID_PATTERN.test(stored)) return stored
  } catch {
    // Storage can be blocked; questions should still work.
  }

  fallbackId ??= crypto.randomUUID()
  try {
    localStorage.setItem(STORAGE_KEY, fallbackId)
  } catch {
    // Keep the same ID for this page's lifetime when persistence is unavailable.
  }
  return fallbackId
}
