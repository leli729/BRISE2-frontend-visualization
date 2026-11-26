import { mount, enableAutoUnmount } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { settle } from './chartTiming'
import { createPinia, setActivePinia } from 'pinia'
import { ref, shallowRef } from 'vue'
import { Contour } from '../../widgets/charts/contour'
import { specsByName as fixtureSpecsByName } from './searchSpaceFixture'

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

const specsByName = ref(fixtureSpecsByName)

const plotlyInstance = ref({ react: vi.fn(), purge: vi.fn() })

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

vi.mock('../../entities/main/api/main.client.store', () => ({
    MainClientApi: {
        calculatePlot: calculatePlotMock
    }
}))

vi.mock('../../widgets/charts/contour/render', () => ({
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

    const mountComponent = () => {
        return mount(Contour, {
            props: {
                contourParam1: 'frequency',
                contourParam2: 'threads',
                contourObjective: 'runtime'
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

            allRes.value = [
                {
                    configurations: {
                        frequency: 50,
                        threads: 4
                    },
                    results: [123.4],
                    time: '10m 20s',
                    'measured points': 1
                }
            ]
        
        await settle()

        expect(renderContourMock).toHaveBeenCalledWith(
            plotlyInstance.value,
            wrapper.find('div').element,
            result,
            specsByName.value
        )
    })

    it('rerenders when allRes changes', async () => {
        mountComponent()

        await settle()

        const callsBeforeChange = calculatePlotMock.mock.calls.length

        allRes.value = [...allRes.value, {
            configurations: {
                frequency: 60,
                threads: 8
            },
            results: [100]
        }]

        await settle()

        expect(calculatePlotMock.mock.calls.length)
            .toBeGreaterThan(callsBeforeChange)
    })

    it('rerenders when contourParam1 changes', async () => {
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

         allRes.value = [...allRes.value, {
            configurations: {
                frequency: 50,
                threads: 4
            },
            results: [100],
            time: '10m 20s',
            'measured points': 1
        }]

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

        const active = { configurations: { frequency: 60, threads: 8 }, results: { runtime: 100 } }
        const inactive = { configurations: { frequency: 50 }, results: { runtime: 90 } }
        allRes.value = [active, inactive]

        await settle()

        expect(calculatePlotMock.mock.lastCall?.[1].trials).toEqual([active])
    })
})
