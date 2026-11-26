import { onBeforeUnmount, onMounted, watch } from 'vue'
import type { Ref, WatchSource } from 'vue'
import type { PlotlyInstance } from './chart.types'

// the shortest time between the starts of two renders of one chart
export const CLIENT_REDRAW_INTERVAL_MS = 250
// the same for a chart that asks main-node for its data: each render is a request
export const PLOT_REQUEST_INTERVAL_MS = 2000

interface ChartRender {
    // the chart's element
    element: Ref<HTMLElement | null>
    // the Plotly instance, null until it has loaded
    plotly: Ref<PlotlyInstance | null>
    // what the render reads: a change of any marks the chart as needing a render; watched shallowly
    sources: WatchSource[]
    // draws the chart; `isMounted` tells an async render, after an await, that the chart is gone
    // eslint-disable-next-line no-unused-vars -- the name documents the parameter
    render: (isMounted: () => boolean) => void | Promise<void>
    // a chart that is not active does no work and draws once, with the latest data, when it turns active
    active: () => boolean
    minIntervalMs: number
}

// Draws a chart when its sources change: at most once per `minIntervalMs` (the first change at once, the changes
// that follow within the interval as one render at its end, with the latest data), never two renders of the chart at
// the same time, and only while it is active and Plotly is ready. Purges the chart on unmount.
export function useChartRender({ element, plotly, sources, render, active, minIntervalMs }: ChartRender) {
    let mounted = false
    let needsRender = true
    let running = false
    let lastStart = -Infinity
    let timer: ReturnType<typeof setTimeout> | null = null

    function schedule() {
        if (!mounted || !needsRender || running || timer !== null) return
        if (!active() || !plotly.value || !element.value) return
        const wait = lastStart + minIntervalMs - Date.now()
        if (wait > 0) {
            timer = setTimeout(() => {
                timer = null
                schedule()
            }, wait)
            return
        }
        void run()
    }

    async function run() {
        running = true
        needsRender = false
        lastStart = Date.now()
        try {
            await render(() => mounted)
        } catch (error) {
            console.error(error)
        } finally {
            running = false
        }
        // the sources changed while it ran
        schedule()
    }

    watch([...sources, plotly], () => {
        needsRender = true
        schedule()
    })

    watch(active, schedule)

    onMounted(() => {
        mounted = true
        schedule()
    })

    onBeforeUnmount(() => {
        mounted = false
        if (timer !== null) clearTimeout(timer)
        timer = null
        if (element.value && plotly.value) {
            plotly.value.purge(element.value)
        }
    })
}
