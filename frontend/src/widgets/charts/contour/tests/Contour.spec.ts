import { mount, enableAutoUnmount } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { settle } from '@/widgets/charts/tests/support/chartTiming'
import { createPinia, setActivePinia } from 'pinia'
import { ref, shallowRef } from 'vue'
import { Contour } from '@/widgets/charts/contour'
import { specsByName as fixtureSpecsByName } from '@/widgets/charts/tests/support/searchSpaceFixture'

const result = {
    contour: {
        x: [50, 60],
        y: [4, 8],
        z: expect.any(Array),
        x_name: 'frequency',
        y_name: 'threads',
        objective_name: 'runtime'
    }
}

const { calculatePlotMock } = vi.hoisted(() => ({
    calculatePlotMock: vi.fn()
}))

const { renderContourMock } = vi.hoisted(() => ({
    renderContourMock: vi.fn()
}))

const allRes = shallowRef<any[]>([])

// a trial with both parameters of the plot; the plot service needs two of them
const trial = (frequency: number, threads: number) => ({ configurations: { frequency, threads }, results: { runtime: 100 } })

const specsByName = ref(fixtureSpecsByName)

const plotlyInstance = ref({ react: vi.fn(), purge: vi.fn() })

vi.mock('@/entities/main/model/plot.store', () => ({
    usePlotStore: vi.fn(() => ({
        allRes
    }))
}))

vi.mock('@/entities/main', () => ({
    useMainEventStore: vi.fn(() => ({
        specsByName,
        plotlyInstance
    }))
}))

vi.mock('@/entities/main/api/main.client.store', () => ({
    MainClientApi: {
        calculatePlot: calculatePlotMock
    }
}))

vi.mock('@/widgets/charts/contour/render', () => ({
    renderContour: renderContourMock
}))



// every mounted chart watches the module-level refs below until it is unmounted; a leftover one would draw with
// its old props when a later test changes them
enableAutoUnmount(afterEach)

describe('Contour Plot', () => {
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
        return mount(Contour, {
            props: {
                contourParam1: 'frequency',
                contourParam2: 'threads',
                contourObjective: 'runtime',
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

        allRes.value = [
            {
                configurations: {
                    frequency: 50,
                    threads: 4
                },
                results: [123.4],
                time: '10m 20s',
                'measured points': 1
            },
            {
                configurations: {
                    frequency: 60,
                    threads: 8
                },
                results: [125.4],
                time: '10m 20s',
                'measured points': 1
            }
        ]

        await settle()

        expect(calculatePlotMock).toHaveBeenCalled()

        expect(calculatePlotMock).toHaveBeenLastCalledWith(
            "contour",
            {
                "trials": allRes.value,
                "param1": 'frequency',
                "param2": 'threads',
                "objective": 'runtime'
            }
        )
    })

    it('passes result from backend to render', async () => {

        calculatePlotMock.mockResolvedValue(result)

        const wrapper = mountComponent()

        await settle()

        allRes.value = [trial(50, 4), trial(60, 8)]

        await settle()

        expect(renderContourMock).toHaveBeenCalledWith(
            plotlyInstance.value,
            wrapper.find('div').element,
            result,
            specsByName.value
        )
    })

    it('draws nothing while inactive, and once with the latest data when it turns active', async () => {
        const wrapper = mountComponent({ active: false })
        await settle()
        allRes.value = [trial(50, 4), trial(60, 8)]
        await settle()
        expect(calculatePlotMock).not.toHaveBeenCalled()
        expect(renderContourMock).not.toHaveBeenCalled()

        await wrapper.setProps({ active: true })
        await settle()

        expect(calculatePlotMock).toHaveBeenCalledTimes(1)
        expect(renderContourMock).toHaveBeenCalledTimes(1)
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

    it('rerenders when contourParam1 changes', async () => {
        allRes.value = [trial(50, 4), trial(60, 8)]
        const wrapper = mountComponent()

        await settle()

        const callsBeforeChange = calculatePlotMock.mock.calls.length

        await wrapper.setProps({
            contourParam1: 'threads'
        })

        await settle()

        expect(calculatePlotMock.mock.calls.length)
            .toBeGreaterThan(callsBeforeChange)

        expect(calculatePlotMock).toHaveBeenLastCalledWith(
            "contour",
            {
                "trials": allRes.value,
                "param1": 'threads',
                "param2": 'threads',
                "objective": 'runtime'
            }
        )
    })

    it('rerenders when contourParam2 changes', async () => {
        allRes.value = [trial(50, 4), trial(60, 8)]
        const wrapper = mountComponent()

        await settle()

        const callsBeforeChange = calculatePlotMock.mock.calls.length

        await wrapper.setProps({
            contourParam2: 'frequency'
        })

        await settle()

        expect(calculatePlotMock.mock.calls.length)
            .toBeGreaterThan(callsBeforeChange)

        expect(calculatePlotMock).toHaveBeenLastCalledWith(
            "contour",
            {
                "trials": allRes.value,
                "param1": 'frequency',
                "param2": 'frequency',
                "objective": 'runtime'
            }
        )
    })

    it('rerenders when contourObjective changes', async () => {
        allRes.value = [trial(50, 4), trial(60, 8)]
        const wrapper = mountComponent()

        await settle()

        const callsBeforeChange = calculatePlotMock.mock.calls.length

        await wrapper.setProps({
            contourObjective: 'energy'
        })

        await settle()

        expect(calculatePlotMock.mock.calls.length)
            .toBeGreaterThan(callsBeforeChange)

        expect(calculatePlotMock).toHaveBeenLastCalledWith(
            "contour",
            {
                "trials": allRes.value,
                "param1": 'frequency',
                "param2": 'threads',
                "objective": 'energy'
            }
        )
    })

    it('passes an empty result to render if result is empty', async () => {
        const emptyResult = {
            contour: {}
        }

        calculatePlotMock.mockResolvedValue(emptyResult)

        const wrapper = mountComponent()

        allRes.value = [trial(50, 4), trial(60, 8)]

        await settle()

        expect(renderContourMock).toHaveBeenCalledWith(
            plotlyInstance.value,
            wrapper.find('div').element,
            emptyResult,
            specsByName.value
        )
    })

    it('leaves out trials in which a selected parameter is inactive', async () => {
        mountComponent()

        await settle()

        const active = [trial(60, 8), trial(50, 4)]
        const inactive = { configurations: { frequency: 50 }, results: { runtime: 90 } }
        allRes.value = [active[0], inactive, active[1]]

        await settle()

        expect(calculatePlotMock.mock.lastCall?.[1].trials).toEqual(active)
    })

    it.each([0, 1])('sends no request with %i trial(s) that have both parameters, and gives the renderer the empty result', async (count) => {
        // a trial without one of the parameters does not count
        allRes.value = [trial(50, 4), trial(60, 8)].slice(0, count).concat({ configurations: { frequency: 70 }, results: { runtime: 90 } } as any)
        const wrapper = mountComponent()

        await settle()

        expect(calculatePlotMock).not.toHaveBeenCalled()
        expect(renderContourMock).toHaveBeenLastCalledWith(plotlyInstance.value, wrapper.find('div').element, {}, specsByName.value)
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

        expect(renderContourMock).not.toHaveBeenCalled()
    })
})
