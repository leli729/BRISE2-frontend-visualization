import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { defineComponent, h, ref, shallowRef } from 'vue'
import { useChartRender } from '../../widgets/charts/model/use-chart-render'

const INTERVAL_MS = 250

// every mounted chart watches the module-level sources below until it is unmounted
enableAutoUnmount(afterEach)

type Drawing = Parameters<typeof useChartRender>[0]['render']

const plotly = shallowRef<any>(null)
const data = ref(0)
const active = ref(true)
// the value of the source each drawing saw
let seen: number[] = []

function mountChart(render: Drawing = () => { seen.push(data.value) }) {
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
                minIntervalMs: INTERVAL_MS
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

    it('tells a drawing that resumes after unmount that the chart is gone', async () => {
        let resume: () => void = () => {}
        let mountedWhenResumed: boolean | undefined
        const { wrapper } = mountChart(async (isMounted) => {
            await new Promise<void>(resolve => { resume = resolve })
            mountedWhenResumed = isMounted()
        })
        await flushPromises()

        wrapper.unmount()
        resume()
        await flushPromises()

        expect(mountedWhenResumed).toBe(false)
    })
})
