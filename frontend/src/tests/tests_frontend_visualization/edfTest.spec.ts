import { mount } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { settle } from './chartTiming'
import { createPinia, setActivePinia } from 'pinia'
import { ref, shallowRef } from 'vue'
import { Edf } from '../../widgets/charts/edf'

const { renderEdfMock } = vi.hoisted(() => ({
    renderEdfMock: vi.fn()
}))

const allRes = shallowRef<any[]>([])

const experiment_description = ref({
    Context: {
        TaskConfiguration: {
            Objectives: {
                runtime: {
                    Name: 'runtime',
                    Minimization: true
                }
            }
        },
    }
})

const plotlyInstance = ref({ react: vi.fn(), purge: vi.fn() })

vi.mock('../../entities/main/model/plot.store', () => ({
    usePlotStore: vi.fn(() => ({
        allRes
    }))
}))

vi.mock('../../entities/main', () => ({
    useMainEventStore: vi.fn(() => ({
        experiment_description,
        plotlyInstance
    }))
}))

vi.mock('../../widgets/charts/edf/render', () => ({
    renderEdf: renderEdfMock
}))

describe('EDF Plot', () => {
    beforeEach(() => {
        vi.useFakeTimers()
        setActivePinia(createPinia())

        vi.clearAllMocks()

        allRes.value = []

        experiment_description.value = {
            Context: {
                TaskConfiguration: {
                    Objectives: {
                        runtime: {
                            Name: 'runtime',
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

    const mountComponent = () => {
        return mount(Edf, {
            global: {
                plugins: [createPinia()]
            }
        })
    }

    it('rerenders when allRes changes', async () => {
        const wrapper = mountComponent()

        await settle()

        const callsBeforeChange = renderEdfMock.mock.calls.length

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

        expect(renderEdfMock.mock.calls.length)
            .toBeGreaterThan(callsBeforeChange)

        expect(renderEdfMock).toHaveBeenLastCalledWith(
            plotlyInstance.value,
            wrapper.find('div').element,
            allRes.value
        )
    })
})