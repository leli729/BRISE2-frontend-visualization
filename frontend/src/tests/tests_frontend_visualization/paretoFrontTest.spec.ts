import { mount, enableAutoUnmount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { settle } from './chartTiming'
import { createPinia, setActivePinia } from 'pinia'
import { ref, shallowRef } from 'vue'
import { ParetoFront } from '../../widgets/charts/pareto-front'

const result = {
    "objective_names": ['energy', 'runtime'],
    "all_points": [
        {
            'energy': 100,
            'runtime': 150
        },
        {
            'energy': 120,
            'runtime': 160
        }
    ],
    "pareto_points": [
        {
            'energy': 100,
            'runtime': 150
        } 
    ]
}

const { calculatePlotMock } = vi.hoisted(() => ({
    calculatePlotMock: vi.fn()
}))

const { renderParetoFrontMock } = vi.hoisted(() => ({
    renderParetoFrontMock: vi.fn()
}))

const allRes = shallowRef<any[]>([])

const plotlyInstance = ref({ react: vi.fn(), purge: vi.fn() })

vi.mock('../../entities/main/model/plot.store', () => ({
    usePlotStore: vi.fn(() => ({
        allRes
    }))
}))

vi.mock('../../entities/main', () => ({
    useMainEventStore: vi.fn(() => ({
        plotlyInstance
    }))
}))

vi.mock('../../entities/main/api/main.client.store', () => ({
    MainClientApi: {
        calculatePlot: calculatePlotMock
    }
}))

vi.mock('../../widgets/charts/pareto-front/render', () => ({
    renderParetoFront: renderParetoFrontMock
}))



// every mounted chart watches the module-level refs below until it is unmounted; a leftover one would draw with
// its old props when a later test changes them
enableAutoUnmount(afterEach)

describe('Pareto Front', () => {
    beforeEach(() => {
        vi.useFakeTimers()
        setActivePinia(createPinia())

        vi.resetAllMocks()

        allRes.value = []

    })

    afterEach(() => {
        vi.useRealTimers()
    })

    const mountComponent = (extraProps: { active?: boolean } = {}) => {
        return mount(ParetoFront, {
            props: {
                paretoObjective1: 'energy',
                paretoObjective2: 'runtime',
                onlyShowParetoFront: false,
                ...extraProps
            },
            global: {
                plugins: [createPinia()]
            }
        })
    }

    it('calls backend with the correct objectives when allRes changes', async () => {
        mountComponent()

        await settle()

        allRes.value = [
            {
                configurations: {
                    frequency: 50,
                    threads: 4
                },
                results: [123.4, 234.5],
                time: '10m 20s',
                'measured points': 1
            }
        ]

        await settle()

        expect(calculatePlotMock).toHaveBeenCalled()

        expect(calculatePlotMock).toHaveBeenLastCalledWith(
            'pareto_front',
            {
                trials: allRes.value,
                objective1: 'energy',
                objective2: 'runtime'
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
                    results: [100, 150],
                    time: '10m 20s',
                    'measured points': 1
                },
                {
                    configurations: {
                        frequency: 60,
                        threads: 8
                    },
                    results: [120, 160],
                    time: '10m 30s',
                    'measured points': 1
                }
            ]
        
        await settle()

        expect(renderParetoFrontMock).toHaveBeenCalledWith(
            plotlyInstance.value,
            wrapper.find('div').element,
            result,
            false
        )
    })

    it('draws nothing while inactive, and once with the latest data when it turns active', async () => {
        const wrapper = mountComponent({ active: false })
        await settle()
        allRes.value = [...allRes.value, { configurations: { frequency: 60, threads: 8 }, results: [100] }]
        await settle()
        expect(calculatePlotMock).not.toHaveBeenCalled()
        expect(renderParetoFrontMock).not.toHaveBeenCalled()

        await wrapper.setProps({ active: true })
        await settle()

        expect(calculatePlotMock).toHaveBeenCalledTimes(1)
        expect(renderParetoFrontMock).toHaveBeenCalledTimes(1)
        expect(calculatePlotMock.mock.calls[0][1].trials).toHaveLength(1)
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

    it('rerenders when paretoObjective1 changes', async () => {
        const wrapper = mountComponent()

        await settle()

        const callsBeforeChange = calculatePlotMock.mock.calls.length

        await wrapper.setProps({
            paretoObjective1: 'runtime'
        })

        await settle()

        expect(calculatePlotMock.mock.calls.length)
            .toBeGreaterThan(callsBeforeChange)

        expect(calculatePlotMock).toHaveBeenLastCalledWith(
            'pareto_front',
            expect.objectContaining({
                objective1: 'runtime'
            })
        )
    })

   it('rerenders when paretoObjective2 changes', async () => {
        const wrapper = mountComponent()

        await settle()

        const callsBeforeChange = calculatePlotMock.mock.calls.length

        await wrapper.setProps({
            paretoObjective2: 'energy'
        })

        await settle()

        expect(calculatePlotMock.mock.calls.length)
            .toBeGreaterThan(callsBeforeChange)

        expect(calculatePlotMock).toHaveBeenLastCalledWith(
            'pareto_front',
            expect.objectContaining({
                objective2: 'energy'
            })
        )
    })

    describe('the "show only Pareto front" switch', () => {
        const trials = [
            { configurations: { frequency: 50, threads: 4 }, results: [100, 150] },
            { configurations: { frequency: 60, threads: 8 }, results: [120, 160] }
        ]

        it('redraws at once from the last reply, without a request', async () => {
            // the reply to the request of the mount, and the later one, which is the last
            calculatePlotMock.mockResolvedValueOnce({ ...result, all_points: [] }).mockResolvedValue(result)
            const wrapper = mountComponent()
            await settle()
            allRes.value = trials
            await flushPromises()
            expect(renderParetoFrontMock).toHaveBeenLastCalledWith(plotlyInstance.value, wrapper.find('div').element, result, false)
            const requests = calculatePlotMock.mock.calls.length
            const drawings = renderParetoFrontMock.mock.calls.length

            // the drawing above started a new interval: the switch does not wait for it
            await wrapper.setProps({ onlyShowParetoFront: true })
            await flushPromises()

            expect(calculatePlotMock).toHaveBeenCalledTimes(requests)
            expect(renderParetoFrontMock).toHaveBeenCalledTimes(drawings + 1)
            expect(renderParetoFrontMock).toHaveBeenLastCalledWith(plotlyInstance.value, wrapper.find('div').element, result, true)
        })

        it('draws nothing before the first reply has arrived, and the reply is drawn with the switch as it is then', async () => {
            let reply: () => void = () => {}
            calculatePlotMock.mockReturnValue(new Promise(resolve => { reply = () => resolve(result) }))
            const wrapper = mountComponent()
            await settle()

            await wrapper.setProps({ onlyShowParetoFront: true })
            await settle()
            expect(renderParetoFrontMock).not.toHaveBeenCalled()
            expect(calculatePlotMock).toHaveBeenCalledTimes(1)

            reply()
            await settle()

            expect(renderParetoFrontMock).toHaveBeenCalledTimes(1)
            expect(renderParetoFrontMock).toHaveBeenLastCalledWith(plotlyInstance.value, wrapper.find('div').element, result, true)
        })

        it('draws nothing while the chart is inactive', async () => {
            calculatePlotMock.mockResolvedValue(result)
            const wrapper = mountComponent()
            await settle()
            await wrapper.setProps({ active: false })
            const drawings = renderParetoFrontMock.mock.calls.length

            await wrapper.setProps({ onlyShowParetoFront: true })
            await settle()

            expect(renderParetoFrontMock).toHaveBeenCalledTimes(drawings)
        })
    })

    it('passes an empty result to render if result is empty', async () => {
        const emptyResult = {
            "objective_names": [],
            "all_points": [], 
            "pareto_points": []
        }

        calculatePlotMock.mockResolvedValue(emptyResult)

        const wrapper = mountComponent()

        allRes.value = [...allRes.value, {
            configurations: {
                frequency: 50,
                threads: 4
            },
            results: [100, 150],
            time: '10m 20s',
            'measured points': 1
        }]

        await settle()

        expect(calculatePlotMock).toHaveBeenCalled()

        expect(renderParetoFrontMock).toHaveBeenLastCalledWith(
            plotlyInstance.value,
            wrapper.find('div').element,
            emptyResult,
            false
        )
    })

    it('draws nothing when the reply arrives after the chart stopped being shown', async () => {
        let reply: () => void = () => {}
        calculatePlotMock.mockReturnValueOnce(new Promise(resolve => { reply = () => resolve(result) }))
        const wrapper = mountComponent()
        await settle()

        await wrapper.setProps({ active: false })
        reply()
        await settle()

        expect(renderParetoFrontMock).not.toHaveBeenCalled()
    })
})
