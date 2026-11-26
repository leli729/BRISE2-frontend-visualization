import { flushPromises } from '@vue/test-utils'
import { vi } from 'vitest'
import { CLIENT_REDRAW_INTERVAL_MS, PLOT_REQUEST_INTERVAL_MS } from '../../widgets/charts/model/use-chart-render'

// longer than the longest redraw interval of the charts
export const REDRAW_WAIT_MS = Math.max(CLIENT_REDRAW_INTERVAL_MS, PLOT_REQUEST_INTERVAL_MS) + 1

// lets the pending promises settle and a redraw that waits for the end of its interval happen; needs fake timers
export async function settle() {
    await flushPromises()
    vi.advanceTimersByTime(REDRAW_WAIT_MS)
    await flushPromises()
}
