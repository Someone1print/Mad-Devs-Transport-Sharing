/**
 * The id of the ride this browser last knew as active, per rider. A tab closed mid-ride (or a
 * socket that was down) misses the `ride.finished` event; on return the ride is looked up by this
 * id and, if it ended meanwhile (a flat battery), the receipt is shown once.
 */
const KEY = 'transport-sharing.active-ride'

export function rememberRide(userId: number, rideId: number): void {
  try {
    localStorage.setItem(`${KEY}.${userId}`, String(rideId))
  } catch {
    // storage unavailable: a finish while away will only show up in the history and the mailbox
  }
}

export function recallRide(userId: number): number | null {
  try {
    const raw = localStorage.getItem(`${KEY}.${userId}`)
    const id = raw === null ? Number.NaN : Number(raw)
    return Number.isInteger(id) ? id : null
  } catch {
    return null
  }
}

export function forgetRide(userId: number): void {
  try {
    localStorage.removeItem(`${KEY}.${userId}`)
  } catch {
    // nothing to forget
  }
}
