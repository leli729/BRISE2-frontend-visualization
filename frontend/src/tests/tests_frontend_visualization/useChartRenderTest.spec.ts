import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { defineComponent, h, ref, shallowRef } from 'vue'
import { useChartRender } from '../../widgets/charts/model/use-chart-render'
import { installIntersectionObserver, uninstallIntersectionObserver, setInView, createdObservers } from './intersectionObserverStub'

const INTERVAL_MS = 250

// every mounted chart watches the module-level sources below until it is unmounted
enableAutoUnmount(afterEach)

type Drawing = Parameters<typeof useChartRender>[0]['render']

const plotly = shallowRef<any>(null)
const data = ref(0)
const active = ref(true)
// the value of the source each drawing saw
let seen: number[] = []

function mountChart(render: Drawing = () => { seen.push(data.value) }, options: { drawOnlyInView?: boolean } = {}) {
    const drawing = vi.fn(render)
    const Chart = defineComponent({
        setup() {
            const element = ref<HTMLElement | null>(null)
            useChartRender({
                element,
                plotly,
                sources: [data],
                render: drawing,
                active: () => active.value,
                minIntervalMs: INTERVAL_MS,
                ...options
            })
            return () => h('div', { ref: element })
        }
    })
    return { wrapper: mount(Chart), drawing }
}

describe('useChartRender', () => {
    beforeEach(() => {
        vi.useFakeTimers()
        plotly.value = { react: vi.fn(), purge: vi.fn() }
        data.value = 0
        active.value = true
        seen = []
    })

    afterEach(() => {
        vi.useRealTimers()
        uninstallIntersectionObserver()
    })

    it('draws once on mount when Plotly is ready and the chart is active', async () => {
        const { drawing } = mountChart()
        await flushPromises()

        expect(drawing).toHaveBeenCalledTimes(1)
    })

    it('draws nothing before Plotly is ready and once when it is', async () => {
        plotly.value = null
        const { drawing } = mountChart()
        await flushPromises()
        expect(drawing).not.toHaveBeenCalled()

        plotly.value = { react: vi.fn(), purge: vi.fn() }
        await flushPromises()

        expect(drawing).toHaveBeenCalledTimes(1)
    })

    it('draws nothing while inactive, and once with the latest data when it turns active after a change', async () => {
        active.value = false
        const { drawing } = mountChart()
        await flushPromises()
        data.value = 1
        await flushPromises()
        vi.advanceTimersByTime(4 * INTERVAL_MS)
        await flushPromises()
        expect(drawing).not.toHaveBeenCalled()

        active.value = true
        await flushPromises()

        expect(drawing).toHaveBeenCalledTimes(1)
        expect(seen).toEqual([1])
    })

    it('draws nothing when it turns active again without a change since its last drawing', async () => {
        const { drawing } = mountChart()
        await flushPromises()

        active.value = false
        await flushPromises()
        active.value = true
        await flushPromises()
        vi.advanceTimersByTime(4 * INTERVAL_MS)
        await flushPromises()

        expect(drawing).toHaveBeenCalledTimes(1)
    })

    it('draws a change at once, then coalesces the changes of the interval into one drawing with the latest data', async () => {
        const { drawing } = mountChart()
        await flushPromises()
        vi.advanceTimersByTime(4 * INTERVAL_MS)

        data.value = 1
        await flushPromises()
        expect(drawing).toHaveBeenCalledTimes(2)

        data.value = 2
        await flushPromises()
        data.value = 3
        await flushPromises()
        expect(drawing).toHaveBeenCalledTimes(2)

        vi.advanceTimersByTime(INTERVAL_MS)
        await flushPromises()

        expect(drawing).toHaveBeenCalledTimes(3)
        expect(seen).toEqual([0, 1, 3])
    })

    it('draws nothing when its redraw falls due while it is inactive, and once with the latest data when it turns active', async () => {
        const { drawing } = mountChart()
        await flushPromises()
        vi.advanceTimersByTime(4 * INTERVAL_MS)
        data.value = 1
        await flushPromises()
        data.value = 2
        await flushPromises()
        expect(drawing).toHaveBeenCalledTimes(2)

        active.value = false
        await flushPromises()
        vi.advanceTimersByTime(4 * INTERVAL_MS)
        await flushPromises()
        expect(drawing).toHaveBeenCalledTimes(2)

        active.value = true
        await flushPromises()

        expect(drawing).toHaveBeenCalledTimes(3)
        expect(seen).toEqual([0, 1, 2])
    })

    it('starts no second drawing while one is in flight, and draws once more when it ends', async () => {
        let finish: () => void = () => {}
        const { drawing } = mountChart(() => new Promise<void>(resolve => { finish = resolve }))
        await flushPromises()
        expect(drawing).toHaveBeenCalledTimes(1)

        vi.advanceTimersByTime(4 * INTERVAL_MS)
        data.value = 1
        await flushPromises()
        vi.advanceTimersByTime(4 * INTERVAL_MS)
        await flushPromises()
        expect(drawing).toHaveBeenCalledTimes(1)

        finish()
        await flushPromises()
        vi.advanceTimersByTime(INTERVAL_MS)
        await flushPromises()

        expect(drawing).toHaveBeenCalledTimes(2)
    })

    it('draws nothing after unmount, a pending drawing included, and purges its element', async () => {
        const { wrapper, drawing } = mountChart()
        await flushPromises()
        const element = wrapper.element
        data.value = 1
        await flushPromises()

        wrapper.unmount()
        vi.advanceTimersByTime(4 * INTERVAL_MS)
        await flushPromises()

        expect(drawing).toHaveBeenCalledTimes(1)
        expect(plotly.value.purge).toHaveBeenCalledWith(element)
    })

    it('tells a drawing that resumes after unmount that it can no longer draw', async () => {
        let resume: () => void = () => {}
        let canDrawWhenResumed: boolean | undefined
        const { wrapper } = mountChart(async (canDraw) => {
            await new Promise<void>(resolve => { resume = resolve })
            canDrawWhenResumed = canDraw()
        })
        await flushPromises()

        wrapper.unmount()
        resume()
        await flushPromises()

        expect(canDrawWhenResumed).toBe(false)
    })

    it('tells a drawing that resumes after the chart stopped being shown that it can not draw, and draws once more when it is shown again', async () => {
        const canDrawWhenResumed: boolean[] = []
        let resume: () => void = () => {}
        const { drawing } = mountChart(async (canDraw) => {
            await new Promise<void>(resolve => { resume = resolve })
            canDrawWhenResumed.push(canDraw())
        })
        await flushPromises()
        expect(drawing).toHaveBeenCalledTimes(1)

        active.value = false
        await flushPromises()
        resume()
        await flushPromises()
        expect(canDrawWhenResumed).toEqual([false])

        vi.advanceTimersByTime(4 * INTERVAL_MS)
        active.value = true
        await flushPromises()
        expect(drawing).toHaveBeenCalledTimes(2)
        resume()
        await flushPromises()

        expect(canDrawWhenResumed).toEqual([false, true])
    })

    describe('draw only in view', () => {
        const chartInView = (render?: Drawing) => mountChart(render, { drawOnlyInView: true })

        // a canvas of Plotly's WebGL layers, whose context can be released with `loseContext`
        function glCanvas() {
            const loseContext = vi.fn()
            const canvas = document.createElement('canvas')
            canvas.className = 'gl-canvas'
            canvas.getContext = vi.fn(() => ({ getExtension: (name: string) => name === 'WEBGL_lose_context' ? { loseContext } : null })) as any
            return { canvas, loseContext }
        }

        it('draws nothing before the chart is reported in view, and once after', async () => {
            installIntersectionObserver({ reportOnObserve: false })
            const { wrapper, drawing } = chartInView()
            await flushPromises()
            expect(drawing).not.toHaveBeenCalled()

            setInView(wrapper.element, true)
            await flushPromises()

            expect(drawing).toHaveBeenCalledTimes(1)
        })

        it('releases the WebGL contexts of its canvases when it leaves the view, although the purge removes the canvases', async () => {
            installIntersectionObserver()
            const { wrapper, drawing } = chartInView()
            await flushPromises()
            expect(drawing).toHaveBeenCalledTimes(1)
            const first = glCanvas()
            const second = glCanvas()
            const other = document.createElement('canvas')
            other.getContext = vi.fn() as any
            wrapper.element.append(first.canvas, second.canvas, other)
            // Plotly's purge removes the canvases from the element
            plotly.value.purge.mockImplementation((element: HTMLElement) => {
                element.querySelectorAll('.gl-canvas').forEach(canvas => canvas.remove())
            })

            setInView(wrapper.element, false)
            await flushPromises()

            expect(plotly.value.purge).toHaveBeenCalledWith(wrapper.element)
            expect(first.loseContext).toHaveBeenCalledTimes(1)
            expect(second.loseContext).toHaveBeenCalledTimes(1)
            expect(other.getContext).not.toHaveBeenCalled()
        })

        it('releases the chart when it turns inactive while in view', async () => {
            installIntersectionObserver()
            const { wrapper } = chartInView()
            await flushPromises()

            active.value = false
            await flushPromises()

            expect(plotly.value.purge).toHaveBeenCalledWith(wrapper.element)
        })

        it('does not release a chart that was never drawn: mounted off screen, then its tab is left', async () => {
            installIntersectionObserver({ reportOnObserve: false })
            const { drawing } = chartInView()
            await flushPromises()
            expect(drawing).not.toHaveBeenCalled()

            active.value = false
            await flushPromises()

            expect(plotly.value.purge).not.toHaveBeenCalled()
        })

        it('draws once with the latest data when it comes back in view, and nothing while it was out of it', async () => {
            installIntersectionObserver()
            const { wrapper, drawing } = chartInView()
            await flushPromises()
            vi.advanceTimersByTime(4 * INTERVAL_MS)
            setInView(wrapper.element, false)
            await flushPromises()

            data.value = 1
            await flushPromises()
            data.value = 2
            await flushPromises()
            vi.advanceTimersByTime(4 * INTERVAL_MS)
            await flushPromises()
            expect(drawing).toHaveBeenCalledTimes(1)

            setInView(wrapper.element, true)
            await flushPromises()

            expect(drawing).toHaveBeenCalledTimes(2)
            expect(seen).toEqual([0, 2])
        })

        it('draws again when it comes back in view although its data did not change, as its drawing was purged', async () => {
            installIntersectionObserver()
            const { wrapper, drawing } = chartInView()
            await flushPromises()
            vi.advanceTimersByTime(4 * INTERVAL_MS)
            setInView(wrapper.element, false)
            await flushPromises()

            setInView(wrapper.element, true)
            await flushPromises()

            expect(drawing).toHaveBeenCalledTimes(2)
        })

        it('draws nothing when a drawing falls due after it left the view, and once with the latest data when it comes back', async () => {
            installIntersectionObserver()
            const { wrapper, drawing } = chartInView()
            await flushPromises()
            vi.advanceTimersByTime(4 * INTERVAL_MS)
            data.value = 1
            await flushPromises()
            data.value = 2
            await flushPromises()
            expect(drawing).toHaveBeenCalledTimes(2)

            setInView(wrapper.element, false)
            await flushPromises()
            vi.advanceTimersByTime(4 * INTERVAL_MS)
            await flushPromises()
            expect(drawing).toHaveBeenCalledTimes(2)

            setInView(wrapper.element, true)
            await flushPromises()

            expect(drawing).toHaveBeenCalledTimes(3)
            expect(seen).toEqual([0, 1, 2])
        })

        it('is not observed without the option', async () => {
            installIntersectionObserver({ reportOnObserve: false })
            const { drawing } = mountChart()
            await flushPromises()

            expect(drawing).toHaveBeenCalledTimes(1)
            expect(createdObservers()).toHaveLength(0)
        })

        it('stops observing when it is unmounted', async () => {
            installIntersectionObserver()
            const { wrapper } = chartInView()
            await flushPromises()
            expect(createdObservers()).toHaveLength(1)

            wrapper.unmount()

            expect(createdObservers()[0].disconnected).toBe(true)
        })
    })
})
