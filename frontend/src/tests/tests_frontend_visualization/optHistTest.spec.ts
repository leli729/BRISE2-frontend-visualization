import { mount, enableAutoUnmount } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { settle } from './chartTiming'
import { createPinia, setActivePinia } from 'pinia'
import { ref, shallowRef } from 'vue'
import { OptHist } from '../../widgets/charts/opt-hist'
import type { PointExp } from '../../entities/main/model/plot.store'

const { renderOptHistMock } = vi.hoisted(() => ({
    renderOptHistMock: vi.fn()
}))

const allRes = shallowRef<any[]>([])
const solution = ref<PointExp | null>(null)

const experiment_description = ref({
    Context: {
        TaskConfiguration: {
            Objectives: {
                runtime: {
                    Name: 'runtime',
                    Minimization: true
                },
                energy: {
                    Name: 'energy',
                    Minimization: true
                }
            }
        },
    }
})

const plotlyInstance = ref({ react: vi.fn(), purge: vi.fn() })

vi.mock('../../entities/main/model/plot.store', () => ({
    usePlotStore: vi.fn(() => ({
        allRes,
        solution
    }))
}))

vi.mock('../../entities/main', () => ({
    useMainEventStore: vi.fn(() => ({
        experiment_description,
        plotlyInstance
    }))
}))

vi.mock('../../widgets/charts/opt-hist/render', () => ({
    renderOptHist: renderOptHistMock
}))

// every mounted chart watches the module-level refs below until it is unmounted; a leftover one would draw into a later
// test's expectations
enableAutoUnmount(afterEach)

describe('Optimization History', () => {
    beforeEach(() => {
        vi.useFakeTimers()
        setActivePinia(createPinia())

        vi.clearAllMocks()

        allRes.value = []
        solution.value = null

        experiment_description.value = {
            Context: {
                TaskConfiguration: {
                    Objectives: {
                        runtime: {
                            Name: 'runtime',
                            Minimization: true
                        },
                        energy: {
                            Name: 'energy',
                            Minimization: true
                        }
                    }
                },
            }
        }
    })

    afterEach(() => {
        vi.useRealTimers()
    })

   const mountComponent = (extraProps: { active?: boolean } = {}) => {
        return mount(OptHist, {
            props: {
                optHistObjective: 'runtime',
                ...extraProps
            },
            global: {
                plugins: [createPinia()]
            }
        })
    }

    it('draws nothing while inactive, and once with the latest data when it turns active', async () => {
        const wrapper = mountComponent({ active: false })
        await settle()
        allRes.value = [...allRes.value, { configurations: { frequency: 60, threads: 8 }, results: { runtime: 100 } }]
        await settle()
        expect(renderOptHistMock).not.toHaveBeenCalled()

        await wrapper.setProps({ active: true })
        await settle()

        expect(renderOptHistMock).toHaveBeenCalledTimes(1)
        expect(renderOptHistMock.mock.calls[0][2]).toHaveLength(1)
    })

    it('rerenders when allRes changes', async () => {
        mountComponent()

        await settle()

        const callsBeforeChange = renderOptHistMock.mock.calls.length

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

        expect(renderOptHistMock.mock.calls.length)
            .toBeGreaterThan(callsBeforeChange)
    })

    it('rerenders when optHistObjective changes', async () => {
        const wrapper = mountComponent()

        await settle()

        const callsBeforeChange = renderOptHistMock.mock.calls.length

        await wrapper.setProps({
            optHistObjective: 'energy'
        })

        await settle()

        expect(renderOptHistMock.mock.calls.length)
            .toBeGreaterThan(callsBeforeChange)
    })

    it('purges the chart when it is unmounted', async () => {
        const wrapper = mountComponent()

        await settle()

        const element = wrapper.find('div').element

        wrapper.unmount()

        expect(plotlyInstance.value.purge).toHaveBeenCalledWith(element)
    })
})