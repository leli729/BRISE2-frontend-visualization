import { mount, enableAutoUnmount } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { settle } from '@/widgets/charts/tests/support/chartTiming'
import { createPinia, setActivePinia } from 'pinia'
import { ref, shallowRef } from 'vue'
import { HypImp } from '@/widgets/charts/hyp-imp'
import { regionOf } from '@/widgets/charts/tests/support/searchSpaceFixture'

const result = {
    importances: {
        frequency: 0.8,
        threads: 0.2
    }
}

const { calculatePlotMock } = vi.hoisted(() => ({
    calculatePlotMock: vi.fn()
}))

const { renderHypImpMock } = vi.hoisted(() => ({
    renderHypImpMock: vi.fn()
}))

const allRes = shallowRef<any[]>([])

// a trial of the region; the plot service needs two of them
const trial = (frequency: number, threads: number) => ({ configurations: { frequency, threads }, results: { runtime: 100 } })

const plotlyInstance = ref({ react: vi.fn(), purge: vi.fn() })

vi.mock('@/entities/main/model/plot.store', () => ({
    usePlotStore: vi.fn(() => ({
        allRes
    }))
}))

vi.mock('@/entities/main', () => ({
    useMainEventStore: vi.fn(() => ({
        plotlyInstance
    }))
}))

vi.mock('@/entities/main/api/main.client.store', () => ({
    MainClientApi: {
        calculatePlot: calculatePlotMock
    }
}))

vi.mock('@/widgets/charts/hyp-imp/render', () => ({
    renderHypImp: renderHypImpMock
}))



// every mounted chart watches the module-level refs below until it is unmounted; a leftover one would draw with
// its old props when a later test changes them
enableAutoUnmount(afterEach)

describe('Hyperparameter Importances', () => {
    beforeEach(() => {
        vi.useFakeTimers()
        setActivePinia(createPinia())

        vi.clearAllMocks()

        allRes.value = []

    })

    afterEach(() => {
        vi.useRealTimers()
    })

    const mountComponent = (extraProps: { active?: boolean } = {}) => {
        return mount(HypImp, {
            props: {
                region: regionOf('frequency', 'threads'),
                hypImpParams: ['frequency', 'threads'],
                hypImpObjective: 'runtime',
                ...extraProps
            },
            global: {
                plugins: [createPinia()]
            }
        })
    }

    it('calls backend with the correct parameters and objective when allRes changes', async () => {
        mountComponent()

        await settle()

        allRes.value = [trial(50, 4), trial(60, 8)]

        await settle()

        expect(calculatePlotMock).toHaveBeenCalled()

        expect(calculatePlotMock).toHaveBeenLastCalledWith(
            'hyperparameter_importances',
            {
                trials: allRes.value,
                parameters: ['frequency', 'threads'],
                objective: 'runtime'
            }
        )
    })

    it('passes result from backend to render', async () => {

        calculatePlotMock.mockResolvedValue(result)

        const wrapper = mountComponent()

        await settle()

        allRes.value = [trial(50, 4), trial(60, 8)]

        await settle()

        expect(renderHypImpMock).toHaveBeenCalledWith(
            plotlyInstance.value,
            wrapper.find('div').element,
            result
        )
    })

    it('draws nothing while inactive, and once with the latest data when it turns active', async () => {
        const wrapper = mountComponent({ active: false })
        await settle()
        allRes.value = [trial(50, 4), trial(60, 8)]
        await settle()
        expect(calculatePlotMock).not.toHaveBeenCalled()
        expect(renderHypImpMock).not.toHaveBeenCalled()

        await wrapper.setProps({ active: true })
        await settle()

        expect(calculatePlotMock).toHaveBeenCalledTimes(1)
        expect(renderHypImpMock).toHaveBeenCalledTimes(1)
        expect(calculatePlotMock.mock.calls[0][1].trials).toHaveLength(2)
    })

    it('rerenders when allRes changes', async () => {
        allRes.value = [trial(50, 4)]
        mountComponent()

        await settle()
        const callsBeforeChange = calculatePlotMock.mock.calls.length

        // the second trial: the plot service needs two
        allRes.value = [...allRes.value, trial(60, 8)]

        await settle()

        expect(calculatePlotMock.mock.calls.length)
            .toBeGreaterThan(callsBeforeChange)
    })

    it('rerenders when hypImpParams changes', async () => {
        allRes.value = [trial(50, 4), trial(60, 8)]
        const wrapper = mountComponent()

        await settle()

        const callsBeforeChange = calculatePlotMock.mock.calls.length

        await wrapper.setProps({
            hypImpParams: ['frequency']
        })

        await settle()

        expect(calculatePlotMock.mock.calls.length)
            .toBeGreaterThan(callsBeforeChange)

        expect(calculatePlotMock).toHaveBeenLastCalledWith(
            'hyperparameter_importances',
            expect.objectContaining({
                parameters: ['frequency']
            })
        )
    })

    it('rerenders when hypImpObjective changes', async () => {
        allRes.value = [trial(50, 4), trial(60, 8)]
        const wrapper = mountComponent()

        await settle()

        const callsBeforeChange = calculatePlotMock.mock.calls.length

        await wrapper.setProps({
            hypImpObjective: 'energy'
        })

        await settle()

        expect(calculatePlotMock.mock.calls.length)
            .toBeGreaterThan(callsBeforeChange)

        expect(calculatePlotMock).toHaveBeenLastCalledWith(
            'hyperparameter_importances',
            expect.objectContaining({
                objective: 'energy'
            })
        )
    })

    it('passes an empty result to render if result is empty', async () => {
        const emptyResult = {
            importances: {}
        }

        calculatePlotMock.mockResolvedValue(emptyResult)

        const wrapper = mountComponent()

        allRes.value = [trial(50, 4), trial(60, 8)]

        await settle()

        expect(renderHypImpMock).toHaveBeenCalledWith(
            plotlyInstance.value,
            wrapper.find('div').element,
            emptyResult
        )
    })

    it('sends the trials of its region, also those in which a selected parameter is inactive', async () => {
        mountComponent()

        await settle()

        const active = { configurations: { frequency: 60, threads: 8 }, results: { runtime: 100 } }
        const inactive = { configurations: { frequency: 50 }, results: { runtime: 90 } }
        allRes.value = [active, inactive]

        await settle()

        expect(calculatePlotMock.mock.lastCall?.[1].trials).toEqual([active, inactive])
    })

    it('leaves out the trials of other regions', async () => {
        mountComponent()

        await settle()

        const own = [trial(60, 8), trial(50, 4)]
        const other = { configurations: { elsewhere: 1 }, results: { runtime: 90 } }
        allRes.value = [own[0], other, own[1]]

        await settle()

        expect(calculatePlotMock.mock.lastCall?.[1].trials).toEqual(own)
    })

    it.each([0, 1])('sends no request with %i trial(s) of its region, and gives the renderer the empty result', async (count) => {
        allRes.value = [trial(50, 4), trial(60, 8)].slice(0, count)
        const wrapper = mountComponent()

        await settle()

        expect(calculatePlotMock).not.toHaveBeenCalled()
        expect(renderHypImpMock).toHaveBeenLastCalledWith(plotlyInstance.value, wrapper.find('div').element, {})
    })

    it('counts only the trials of its region towards the two the plot service needs', async () => {
        allRes.value = [trial(50, 4), { configurations: { elsewhere: 1 }, results: { runtime: 90 } }]
        mountComponent()

        await settle()

        expect(calculatePlotMock).not.toHaveBeenCalled()
    })

    it('draws nothing when the reply arrives after the chart stopped being shown', async () => {
        allRes.value = [trial(50, 4), trial(60, 8)]
        let reply: () => void = () => {}
        calculatePlotMock.mockReturnValueOnce(new Promise(resolve => { reply = () => resolve(result) }))
        const wrapper = mountComponent()
        await settle()

        await wrapper.setProps({ active: false })
        reply()
        await settle()

        expect(renderHypImpMock).not.toHaveBeenCalled()
    })
})
