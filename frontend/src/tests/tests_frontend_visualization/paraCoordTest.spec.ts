import { mount, type VueWrapper } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { settle } from './chartTiming'
import { createPinia, setActivePinia } from 'pinia'
import { ref, shallowRef } from 'vue'
import { ParaCoord } from '../../widgets/charts/para-coord'
import type { PlotlyInstance } from '../../widgets/charts/model/chart.types'
import { regionOf, specsByName as fixtureSpecsByName } from './searchSpaceFixture'
import { installIntersectionObserver, uninstallIntersectionObserver, setInView } from './intersectionObserverStub'

const { renderParaCoordMock } = vi.hoisted(() => ({
    renderParaCoordMock: vi.fn()
}))

const allRes = shallowRef<any[]>([])

const specsByName = ref(fixtureSpecsByName)

const plotlyInstance = ref<PlotlyInstance | null>({ react: vi.fn(), purge: vi.fn() })

vi.mock('../../entities/main/model/plot.store', () => ({
    usePlotStore: vi.fn(() => ({
        allRes
    }))
}))

vi.mock('../../entities/main', () => ({
    useMainEventStore: vi.fn(() => ({
        specsByName,
        plotlyInstance
    }))
}))

vi.mock('../../widgets/charts/para-coord/render', () => ({
    renderParaCoord: renderParaCoordMock
}))

describe('Parallel Coordinates', () => {
    let wrapper: VueWrapper | null = null

    beforeEach(() => {
        vi.useFakeTimers()
        setActivePinia(createPinia())

        vi.clearAllMocks()

        allRes.value = []
        plotlyInstance.value = { react: vi.fn(), purge: vi.fn() }
        // the panel is observed: by default it is reported in view as soon as it is mounted
        installIntersectionObserver()
    })

    afterEach(() => {
        vi.useRealTimers()
        uninstallIntersectionObserver()
    })

    // every mounted component keeps its watchers alive until it's unmounted, and they all share
    // the same module-level refs, so a leftover instance from an earlier test would otherwise
    // react to later tests' state changes
    afterEach(() => {
        wrapper?.unmount()
        wrapper = null
    })

   const mountComponent = (extraProps: { active?: boolean } = {}) => {
        wrapper = mount(ParaCoord, {
            props: {
                region: regionOf('frequency', 'threads'),
                paraCoordObjective: 'runtime',
                paraCoordParams: ['frequency, threads'],
                ...extraProps
            },
            global: {
                plugins: [createPinia()]
            }
        })
        return wrapper
    }

    it('draws nothing while inactive, and once with the latest data when it turns active', async () => {
        const wrapper = mountComponent({ active: false })
        await settle()
        allRes.value = [...allRes.value, { configurations: { frequency: 60, threads: 8 }, results: { runtime: 100 } }]
        await settle()
        expect(renderParaCoordMock).not.toHaveBeenCalled()

        await wrapper.setProps({ active: true })
        await settle()

        expect(renderParaCoordMock).toHaveBeenCalledTimes(1)
        expect(renderParaCoordMock.mock.calls[0][2]).toHaveLength(1)
    })

    it('draws nothing until the panel enters the view', async () => {
        installIntersectionObserver({ reportOnObserve: false })
        const wrapper = mountComponent()
        await settle()
        expect(renderParaCoordMock).not.toHaveBeenCalled()

        setInView(wrapper.element, true)
        await settle()

        expect(renderParaCoordMock).toHaveBeenCalledTimes(1)
    })

    it('purges the panel when it leaves the view, and draws it again when it comes back', async () => {
        const wrapper = mountComponent()
        await settle()
        expect(renderParaCoordMock).toHaveBeenCalledTimes(1)

        setInView(wrapper.element, false)
        await settle()
        expect(plotlyInstance.value?.purge).toHaveBeenCalledWith(wrapper.element)

        setInView(wrapper.element, true)
        await settle()

        expect(renderParaCoordMock).toHaveBeenCalledTimes(2)
    })

    it('rerenders when allRes changes', async () => {
        mountComponent()

        await settle()

        const callsBeforeChange = renderParaCoordMock.mock.calls.length

        allRes.value = [...allRes.value, {
            configurations: {
                frequency: 60,
                threads: 8
            },
            results: {
                runtime: 100
            }
        }]

        await settle()

        expect(renderParaCoordMock.mock.calls.length)
            .toBeGreaterThan(callsBeforeChange)
    })

    it('rerenders when paraCoordParams changes', async () => {
        const wrapper = mountComponent()

        await settle()

        const callsBeforeChange = renderParaCoordMock.mock.calls.length

        await wrapper.setProps({
            paraCoordParams: ['frequency']
        })

        await settle()

        expect(renderParaCoordMock.mock.calls.length)
            .toBeGreaterThan(callsBeforeChange)
    })

    it('rerenders when paraCoordObjective changes', async () => {
        const wrapper = mountComponent()

        await settle()

        const callsBeforeChange = renderParaCoordMock.mock.calls.length

        await wrapper.setProps({
            paraCoordObjective: 'energy'
        })

        await settle()

        expect(renderParaCoordMock.mock.calls.length)
            .toBeGreaterThan(callsBeforeChange)
    })

    it('purges the chart when it is unmounted', async () => {
        const wrapper = mountComponent()

        await settle()

        const element = wrapper.find('div').element

        wrapper.unmount()

        expect(plotlyInstance.value?.purge).toHaveBeenCalledWith(element)
    })

    it('renders once Plotly has finished loading', async () => {
        plotlyInstance.value = null

        mountComponent()

        await settle()

        expect(renderParaCoordMock).not.toHaveBeenCalled()

        plotlyInstance.value = { react: vi.fn(), purge: vi.fn() }

        await settle()

        expect(renderParaCoordMock).toHaveBeenCalled()
    })

    it('draws with the parameters of the search space', async () => {
        mountComponent()
        await settle()

        allRes.value = [{ configurations: { frequency: 60, threads: 8 }, results: { runtime: 100 } }]
        await settle()

        expect(renderParaCoordMock.mock.lastCall?.[5]).toEqual(specsByName.value)
    })

    it('draws the trials of its region, also those in which a selected parameter is inactive', async () => {
        const wrapper = mountComponent()

        await wrapper.setProps({
            paraCoordParams: ['frequency', 'threads']
        })
        await settle()

        const active = { configurations: { frequency: 60, threads: 8 }, results: { runtime: 100 } }
        const inactive = { configurations: { frequency: 50 }, results: { runtime: 90 } }
        allRes.value = [active, inactive]

        await settle()

        expect(renderParaCoordMock.mock.lastCall?.[2]).toEqual([active, inactive])
    })

    it('leaves out the trials of other regions', async () => {
        mountComponent()

        await settle()

        const own = { configurations: { frequency: 60, threads: 8 }, results: { runtime: 100 } }
        const other = { configurations: { elsewhere: 1 }, results: { runtime: 90 } }
        allRes.value = [own, other]

        await settle()

        expect(renderParaCoordMock.mock.lastCall?.[2]).toEqual([own])
    })
})
