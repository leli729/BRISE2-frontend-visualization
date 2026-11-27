import { mount, enableAutoUnmount } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { settle } from './chartTiming'
import { createPinia, setActivePinia } from 'pinia'
import { ref, shallowRef } from 'vue'
import { Slice } from '../../widgets/charts/slice'
import { regionOf, specsByName as fixtureSpecsByName } from './searchSpaceFixture'

const { renderSliceMock } = vi.hoisted(() => ({
    renderSliceMock: vi.fn()
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

vi.mock('../../widgets/charts/slice/render', () => ({
    renderSlice: renderSliceMock
}))

// every mounted chart watches the module-level refs below until it is unmounted; a leftover one would draw into a later
// test's expectations
enableAutoUnmount(afterEach)

describe('Slice Plot', () => {
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
        return mount(Slice, {
            props: {
                region: regionOf('frequency', 'threads'),
                sliceObjective: 'runtime',
                sliceParam: 'frequency',
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
        expect(renderSliceMock).not.toHaveBeenCalled()

        await wrapper.setProps({ active: true })
        await settle()

        expect(renderSliceMock).toHaveBeenCalledTimes(1)
        expect(renderSliceMock.mock.calls[0][2]).toHaveLength(1)
    })

    it('rerenders when allRes changes', async () => {
        mountComponent()

        await settle()

        const callsBeforeChange = renderSliceMock.mock.calls.length

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

        expect(renderSliceMock.mock.calls.length)
            .toBeGreaterThan(callsBeforeChange)
    })

    it('rerenders when sliceParam changes', async () => {
        const wrapper = mountComponent()

        await settle()

        const callsBeforeChange = renderSliceMock.mock.calls.length

        await wrapper.setProps({
            sliceParam: 'threads'
        })

        await settle()

        expect(renderSliceMock.mock.calls.length)
            .toBeGreaterThan(callsBeforeChange)
    })

    it('rerenders when sliceObjective changes', async () => {
        const wrapper = mountComponent()

        await settle()

        const callsBeforeChange = renderSliceMock.mock.calls.length

        await wrapper.setProps({
            sliceObjective: 'energy'
        })

        await settle()

        expect(renderSliceMock.mock.calls.length)
            .toBeGreaterThan(callsBeforeChange)
    })

    it('draws with the parameters of the search space', async () => {
        mountComponent()
        await settle()

        allRes.value = [{ configurations: { frequency: 60, threads: 8 }, results: { runtime: 100 } }]
        await settle()

        expect(renderSliceMock.mock.lastCall?.[5]).toEqual(specsByName.value)
    })

    it('draws the trials of its region, also those in which the selected parameter is inactive', async () => {
        mountComponent()

        await settle()

        const active = { configurations: { frequency: 60 }, results: { runtime: 100 } }
        const inactive = { configurations: { threads: 8 }, results: { runtime: 90 } }
        allRes.value = [active, inactive]

        await settle()

        expect(renderSliceMock.mock.lastCall?.[2]).toEqual([active, inactive])
    })

    it('leaves out the trials of other regions', async () => {
        mountComponent()

        await settle()

        const own = { configurations: { frequency: 60 }, results: { runtime: 100 } }
        const other = { configurations: { elsewhere: 1 }, results: { runtime: 90 } }
        allRes.value = [own, other]

        await settle()

        expect(renderSliceMock.mock.lastCall?.[2]).toEqual([own])
    })
})
