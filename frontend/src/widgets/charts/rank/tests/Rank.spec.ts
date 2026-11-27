import { mount, enableAutoUnmount } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { settle } from '@/widgets/charts/tests/support/chartTiming'
import { createPinia, setActivePinia } from 'pinia'
import { ref, shallowRef } from 'vue'
import { Rank } from '@/widgets/charts/rank'
import { regionOf, specsByName as fixtureSpecsByName } from '@/widgets/charts/tests/support/searchSpaceFixture'

const { renderRankMock } = vi.hoisted(() => ({
    renderRankMock: vi.fn()
}))

const allRes = shallowRef<any[]>([])

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

vi.mock('@/widgets/charts/rank/render', () => ({
    renderRank: renderRankMock
}))

// every mounted chart watches the module-level refs below until it is unmounted; a leftover one would draw into a later
// test's expectations
enableAutoUnmount(afterEach)

describe('Rank Plot', () => {
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
        return mount(Rank, {
            props: {
                region: regionOf('frequency', 'threads'),
                rankParam1: 'threads',
                rankParam2: 'frequency',
                rankObjective: 'runtime',
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
        expect(renderRankMock).not.toHaveBeenCalled()

        await wrapper.setProps({ active: true })
        await settle()

        expect(renderRankMock).toHaveBeenCalledTimes(1)
        expect(renderRankMock.mock.calls[0][2]).toHaveLength(1)
    })

    it('rerenders when allRes changes', async () => {
        mountComponent()

        await settle()

        const callsBeforeChange = renderRankMock.mock.calls.length

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

        expect(renderRankMock.mock.calls.length)
            .toBeGreaterThan(callsBeforeChange)
    })

    it('rerenders when rankParam1 changes', async () => {
        const wrapper = mountComponent()

        await settle()

        const callsBeforeChange = renderRankMock.mock.calls.length

        await wrapper.setProps({
            rankParam1: 'frequency'
        })

        await settle()

        expect(renderRankMock.mock.calls.length)
            .toBeGreaterThan(callsBeforeChange)
    })

    it('rerenders when rankParam2 changes', async () => {
        const wrapper = mountComponent()

        await settle()

        const callsBeforeChange = renderRankMock.mock.calls.length

        await wrapper.setProps({
            rankParam2: 'threads'
        })

        await settle()

        expect(renderRankMock.mock.calls.length)
            .toBeGreaterThan(callsBeforeChange)
    })

    it('rerenders when rankObjective changes', async () => {
        const wrapper = mountComponent()

        await settle()

        const callsBeforeChange = renderRankMock.mock.calls.length

        await wrapper.setProps({
            rankObjective: 'energy'
        })

        await settle()

        expect(renderRankMock.mock.calls.length)
            .toBeGreaterThan(callsBeforeChange)
    })

    it('draws with the parameters of the search space', async () => {
        mountComponent()
        await settle()

        allRes.value = [{ configurations: { frequency: 60, threads: 8 }, results: { runtime: 100 } }]
        await settle()

        expect(renderRankMock.mock.lastCall?.[6]).toEqual(specsByName.value)
    })

    it('draws the trials of its region, also those in which a selected parameter is inactive', async () => {
        mountComponent()

        await settle()

        const active = { configurations: { frequency: 60, threads: 8 }, results: { runtime: 100 } }
        const inactive = { configurations: { frequency: 50 }, results: { runtime: 90 } }
        allRes.value = [active, inactive]

        await settle()

        expect(renderRankMock.mock.lastCall?.[2]).toEqual([active, inactive])
    })

    it('leaves out the trials of other regions', async () => {
        mountComponent()

        await settle()

        const own = { configurations: { frequency: 60, threads: 8 }, results: { runtime: 100 } }
        const other = { configurations: { elsewhere: 1 }, results: { runtime: 90 } }
        allRes.value = [own, other]

        await settle()

        expect(renderRankMock.mock.lastCall?.[2]).toEqual([own])
    })
})
