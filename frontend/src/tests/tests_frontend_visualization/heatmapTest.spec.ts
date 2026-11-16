import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { ref } from 'vue'
import { Heatmap } from '../../widgets/charts/heatmap'
import { theme } from '../../widgets/charts/model/heatmap-theme'
import { Color } from '../../widgets/charts/model/chart.types'
import type { ParameterSpec, SearchSpaceRegion } from '../../entities/experiment/model/experiment.model'
import { N0, N1, O1, n1, categoricalSpecsByName } from './searchSpaceFixture'

const { renderHeatmapMock } = vi.hoisted(() => ({
    renderHeatmapMock: vi.fn()
}))

globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
}

// the region under N01 holds three parameters: a configuration of the other branch has none of them
const M1 = `${N0}.N01.M1`
const K1 = `${N0}.N01.K1`
const nominal = (name: string): ParameterSpec => ({
    Name: name, Type: 'NominalHyperparameter', Level: 0, Categories: [`${name}.A`, `${name}.B`], Inactive: 'inactive'
})
const m1 = nominal(M1)
const k1 = nominal(K1)
const regionN01: SearchSpaceRegion = { ActivationCategory: `${N0}.N01`, Parameters: [n1, m1, k1] }
const specsOfRegion = { ...categoricalSpecsByName, [M1]: m1, [K1]: k1 }

const measuredN01 = { configurations: { [N0]: `${N0}.N01`, [N1]: `${N1}.N11`, [M1]: `${M1}.A`, [K1]: `${K1}.B` }, results: { runtime: 5 } }
const measuredN02 = { configurations: { [N0]: `${N0}.N02`, [O1]: `${O1}.O11` }, results: { runtime: 9 } }

const allRes = ref<any[]>([])
const solution = ref<any>(null)
const specsByName = ref(specsOfRegion)
const plotlyInstance = ref<any>({ react: vi.fn(), purge: vi.fn() })

vi.mock('../../entities/main/model/plot.store', () => ({
    usePlotStore: vi.fn(() => ({
        allRes,
        solution
    }))
}))

vi.mock('../../entities/main', () => ({
    useMainEventStore: vi.fn(() => ({
        specsByName,
        plotlyInstance
    }))
}))

vi.mock('../../widgets/charts/heatmap/render', () => ({
    renderHeatmap: renderHeatmapMock
}))

// a chart left mounted by a test would draw again when the next test sets the shared Plotly
enableAutoUnmount(afterEach)

describe('Heatmap', () => {
    beforeEach(() => {
        setActivePinia(createPinia())
        vi.clearAllMocks()
        allRes.value = []
        solution.value = null
        plotlyInstance.value = { react: vi.fn(), purge: vi.fn() }
        theme.value.color = Color[0] // the colour scale is shared by every chart, so a test must not leave its choice
    })

    const mountComponent = (region: SearchSpaceRegion = regionN01) => mount(Heatmap, {
        props: {
            region,
            heatmapParam1: N1,
            heatmapParam2: M1,
            heatmapObjective: 'runtime'
        },
        global: { plugins: [createPinia()] }
    })

    const lastRender = () => renderHeatmapMock.mock.calls.at(-1)!

    it('draws the measured configurations of its region only', async () => {
        allRes.value = [measuredN01, measuredN02]
        mountComponent()
        await flushPromises()

        expect(lastRender()[2]).toEqual([measuredN01])
    })

    it('draws the parameters and the objective it is given, with the specifications and the solution', async () => {
        allRes.value = [measuredN01]
        solution.value = measuredN01
        mountComponent()
        await flushPromises()

        const [, , trials, param1, param2, objective, specs, drawnSolution] = lastRender()
        expect([trials, param1, param2, objective]).toEqual([[measuredN01], N1, M1, 'runtime'])
        expect(specs).toEqual(specsOfRegion)
        expect(drawnSolution).toEqual(measuredN01)
    })

    it('draws no solution of another region', async () => {
        allRes.value = [measuredN01, measuredN02]
        solution.value = measuredN02
        mountComponent()
        await flushPromises()

        expect(lastRender()[7]).toBeNull()
    })

    it('draws the solution once it arrives', async () => {
        // at the end of a run the solution is usually a measured point already: only the solution changes
        allRes.value = [measuredN01]
        mountComponent()
        await flushPromises()

        solution.value = measuredN01
        await flushPromises()

        expect(lastRender()[7]).toEqual(measuredN01)
    })

    it('rerenders when allRes changes', async () => {
        mountComponent()
        await flushPromises()
        const callsBeforeChange = renderHeatmapMock.mock.calls.length

        allRes.value.push(measuredN01)
        await flushPromises()

        expect(renderHeatmapMock.mock.calls.length).toBeGreaterThan(callsBeforeChange)
    })

    it.each([
        ['heatmapParam1', K1],
        ['heatmapParam2', K1],
        ['heatmapObjective', 'energy']
    ])('rerenders when %s changes', async (prop, value) => {
        const wrapper = mountComponent()
        await flushPromises()
        const callsBeforeChange = renderHeatmapMock.mock.calls.length

        await wrapper.setProps({ [prop]: value })
        await flushPromises()

        expect(renderHeatmapMock.mock.calls.length).toBeGreaterThan(callsBeforeChange)
    })

    it('rerenders when the colour scale changes', async () => {
        const wrapper = mountComponent()
        await flushPromises()
        const callsBeforeChange = renderHeatmapMock.mock.calls.length

        await wrapper.find('select').setValue('Greens')
        await flushPromises()

        expect(renderHeatmapMock.mock.calls.length).toBeGreaterThan(callsBeforeChange)
    })

    it('sets the shared colour scale', async () => {
        const wrapper = mountComponent()
        await flushPromises()

        await wrapper.find('select').setValue('Jet')
        await flushPromises()

        expect(theme.value.color).toBe('Jet')
    })

    it('draws once Plotly has loaded', async () => {
        plotlyInstance.value = null
        mountComponent()
        await flushPromises()
        expect(renderHeatmapMock).not.toHaveBeenCalled()

        plotlyInstance.value = { react: vi.fn(), purge: vi.fn() }
        await flushPromises()

        expect(renderHeatmapMock).toHaveBeenCalled()
    })

    it('purges its plot when it goes away', async () => {
        const wrapper = mountComponent()
        await flushPromises()

        wrapper.unmount()

        expect(plotlyInstance.value.purge).toHaveBeenCalled()
    })
})
