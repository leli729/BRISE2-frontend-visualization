import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { Ref, WatchSource } from 'vue'
import type { ResizablePlotly } from './chart.types'

// the shortest time between the starts of two renders of one chart
export const CLIENT_REDRAW_INTERVAL_MS = 250
// the same for a chart that asks main-node for its data: each render is a request
export const PLOT_REQUEST_INTERVAL_MS = 2000
// a chart counts as in view this far above and below the viewport: under half a panel (Plotly's default height is 450 px),
// so that a panel is drawn just before it is visible while few panels are in range, each holding 3 WebGL contexts
const IN_VIEW_MARGIN = '200px 0px'

interface ChartRender {
    // the chart's element
    element: Ref<HTMLElement | null>
    // the Plotly instance, null until it has loaded
    plotly: Ref<ResizablePlotly | null>
    // what the render reads: a change of any marks the chart as needing a render; watched shallowly
    sources: WatchSource[]
    // draws the chart; `canDraw` tells an async render, after an await, whether the chart is still mounted and shown
    // eslint-disable-next-line no-unused-vars -- the name documents the parameter
    render: (canDraw: () => boolean) => void | Promise<void>
    // a chart that is not active does no work and draws once, with the latest data, when it turns active
    active: () => boolean
    // draw only while the element is in view, and release the chart's WebGL contexts when it leaves: a chart of many
    // panels would otherwise exceed the browser's limit of contexts
    drawOnlyInView?: boolean
    minIntervalMs: number
}

// Draws a chart when its sources change: at most once per `minIntervalMs` (the first change at once, the changes
// that follow within the interval as one render at its end, with the latest data), never two renders of the chart at
// the same time, and only while it is active (and in view, with `drawOnlyInView`) and Plotly is ready. With `drawOnlyInView`
// a chart that has been drawn is released when it stops being shown: purged, its WebGL contexts released, and it draws
// again once shown; without it, an inactive chart keeps its last drawing. Follows the element's width: a drawn, shown
// chart is laid out again when it changes (a hidden one, once it is shown). Purges the chart on unmount.
export function useChartRender({ element, plotly, sources, render, active, drawOnlyInView = false, minIntervalMs }: ChartRender) {
    let mounted = false
    let needsRender = true
    let running = false
    let drawn = false
    let observer: IntersectionObserver | null = null
    let resizeObserver: ResizeObserver | null = null
    // the last width of the element seen (a width of 0 is a hidden element), and whether it changed since the plot was
    // laid out
    let lastWidth: number | null = null
    let resizeNeeded = false
    // what the observer last reported; false until its first report
    const inView = ref(false)
    let lastStart = -Infinity
    let timer: ReturnType<typeof setTimeout> | null = null

    // a chart that is not observed is never held back by the view
    const shown = () => active() && (!drawOnlyInView || inView.value)

    function schedule() {
        if (!mounted || !needsRender || running || timer !== null) return
        if (!shown() || !plotly.value || !element.value) return
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
        drawn = true
        // a drawing lays the plot out at the element's current width
        resizeNeeded = false
        needsRender = false
        lastStart = Date.now()
        try {
            await render(() => mounted && shown())
        } catch (error) {
            console.error(error)
        } finally {
            running = false
        }
        // the sources changed while it ran
        schedule()
    }

    // `Plotly.purge` removes the WebGL canvases but does not release their contexts, and the browser counts a removed
    // canvas until it is collected: the contexts are taken first, as the purge removes the canvases
    function release() {
        if (!drawn || !element.value || !plotly.value) return
        const contexts = [...element.value.querySelectorAll<HTMLCanvasElement>('canvas.gl-canvas')]
            .map(canvas => canvas.getContext('webgl') as WebGLRenderingContext | null)
        plotly.value.purge(element.value)
        for (const context of contexts) context?.getExtension('WEBGL_lose_context')?.loseContext()
        drawn = false
        needsRender = true
    }

    // lays the plot out at the element's width again, without drawing it anew
    function resizeToElement() {
        if (!resizeNeeded || !drawn || !shown() || !plotly.value || !element.value) return
        resizeNeeded = false
        // Plotly returns a promise, which its types declare as void; it rejects for an element that is hidden itself
        Promise.resolve(plotly.value.Plots.resize(element.value)).catch(error => console.error(error))
    }

    watch([...sources, plotly], () => {
        needsRender = true
        schedule()
    })

    watch(shown, (isShown) => {
        if (isShown) {
            schedule()
            resizeToElement()
        } else {
            // a drawing in flight will not draw (`canDraw`): the chart needs another one when it is shown again
            if (running) needsRender = true
            if (drawOnlyInView) release()
        }
    })

    onMounted(() => {
        mounted = true
        if (drawOnlyInView && element.value) {
            observer = new IntersectionObserver(entries => {
                inView.value = entries[entries.length - 1].isIntersecting
            }, { rootMargin: IN_VIEW_MARGIN })
            observer.observe(element.value)
        }
        resizeObserver = new ResizeObserver(entries => {
            const width = entries[entries.length - 1].contentRect.width
            // the element of a hidden chart has no width
            if (width <= 0) return
            if (lastWidth !== null && width !== lastWidth) resizeNeeded = true
            lastWidth = width
            resizeToElement()
        })
        if (element.value) resizeObserver.observe(element.value)
        schedule()
    })

    onBeforeUnmount(() => {
        mounted = false
        observer?.disconnect()
        resizeObserver?.disconnect()
        if (timer !== null) clearTimeout(timer)
        timer = null
        if (element.value && plotly.value) {
            plotly.value.purge(element.value)
        }
    })
}
