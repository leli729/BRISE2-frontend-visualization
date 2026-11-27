import { mount, shallowMount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import { createPinia } from 'pinia'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import { VCheckbox, VSelect } from 'vuetify/components'
import RegionTitle from '@/entities/experiment/ui/RegionTitle.vue'
import { Rank, RankRegionPanel } from '@/widgets/charts/rank'
import { Slice, SliceRegionPanel } from '@/widgets/charts/slice'
import { Contour, ContourRegionPanel } from '@/widgets/charts/contour'
import { Heatmap, HeatmapRegionPanel } from '@/widgets/charts/heatmap'
import { ParaCoord, ParaCoordRegionPanel } from '@/widgets/charts/para-coord'
import { HypImp, HypImpRegionPanel } from '@/widgets/charts/hyp-imp'
import { ALPHA, BETA, FLAG, GAMMA, N0, N1, O1, alpha, beta, flag, flatCategoricalRegion, n0, n1, o1, regionA, regionB } from '@/widgets/charts/tests/support/searchSpaceFixture'
import type { SearchSpaceRegion } from '@/entities/experiment/model/experiment.model'

const vuetify = createVuetify({ components, directives })


const mountPanel = (panel: any, props: Record<string, unknown>) => shallowMount(panel, {
    props,
    global: {
        plugins: [vuetify, createPinia()]
    }
})

// a region without the single-category parameter
const regionAB: SearchSpaceRegion = {
    ActivationCategory: regionA.ActivationCategory,
    Parameters: regionA.Parameters.filter(parameter => parameter.Name !== FLAG)
}

describe('Region panels', () => {
    it('slice panel selects the first parameter of its region', () => {
        const wrapper = mountPanel(SliceRegionPanel, {
            region: regionAB,
            showTitle: false,
            sliceObjective: 'runtime'
        })

        expect(wrapper.findComponent(Slice).props('sliceParam')).toBe(ALPHA)
    })

    it('slice panel selects the first parameter of a new region', async () => {
        const wrapper = mountPanel(SliceRegionPanel, {
            region: regionAB,
            showTitle: false,
            sliceObjective: 'runtime'
        })

        await wrapper.setProps({ region: regionB })

        expect(wrapper.findComponent(Slice).props('sliceParam')).toBe(GAMMA)
    })

    it('shows the region title only when asked to', async () => {
        const wrapper = mountPanel(SliceRegionPanel, {
            region: regionAB,
            showTitle: true,
            sliceObjective: 'runtime'
        })

        expect(wrapper.findComponent(RegionTitle).props('region')).toEqual(regionAB)

        await wrapper.setProps({ showTitle: false })

        expect(wrapper.findComponent(RegionTitle).exists()).toBe(false)
    })

    it('contour panel selects the first two parameters of its region that can span an axis', () => {
        const wrapper = mountPanel(ContourRegionPanel, {
            region: regionA,
            showTitle: false,
            contourObjective: 'runtime'
        })

        const contour = wrapper.findComponent(Contour)
        expect(contour.props('contourParam1')).toBe(ALPHA)
        expect(contour.props('contourParam2')).toBe(BETA)
    })

    it('contour panel explains instead of plotting a region with fewer than two parameters', () => {
        const wrapper = mountPanel(ContourRegionPanel, {
            region: regionB,
            showTitle: false,
            contourObjective: 'runtime'
        })

        expect(wrapper.findComponent(Contour).exists()).toBe(false)
        expect(wrapper.text()).toContain('Not enough parameters in this region for a contour plot.')
    })

    it('parallel coordinates panel selects all parameters of its region', () => {
        const wrapper = mountPanel(ParaCoordRegionPanel, {
            region: regionA,
            showTitle: false,
            paraCoordObjective: 'runtime'
        })

        expect(wrapper.findComponent(ParaCoord).props('paraCoordParams')).toEqual([ALPHA, FLAG, BETA])
    })

    it('hyperparameter importances panel selects all parameters of its region', () => {
        const wrapper = mountPanel(HypImpRegionPanel, {
            region: regionA,
            showTitle: false,
            hypImpObjective: 'runtime'
        })

        expect(wrapper.findComponent(HypImp).props('hypImpParams')).toEqual([ALPHA, FLAG, BETA])
    })

    it('rank panel selects the first two parameters of its region that can span an axis', () => {
        const wrapper = mountPanel(RankRegionPanel, {
            region: regionA,
            showTitle: false,
            rankObjective: 'runtime'
        })

        const rank = wrapper.findComponent(Rank)
        expect(rank.props('rankParam1')).toBe(ALPHA)
        expect(rank.props('rankParam2')).toBe(BETA)
    })

    it('rank panel never offers the parameter chosen for one axis on the other axis', () => {
        const wrapper = mountPanel(RankRegionPanel, {
            region: regionA,
            showTitle: false,
            rankObjective: 'runtime'
        })

        const [axis1, axis2] = wrapper.findAllComponents(VSelect)
        expect(axis1.props('items')).toEqual([ALPHA])
        expect(axis2.props('items')).toEqual([BETA])
    })

    it('rank panel explains instead of plotting a region with fewer than two parameters', () => {
        const wrapper = mountPanel(RankRegionPanel, {
            region: regionB,
            showTitle: false,
            rankObjective: 'runtime'
        })

        expect(wrapper.findComponent(Rank).exists()).toBe(false)
        expect(wrapper.text()).toContain('Not enough parameters in this region for a rank plot.')
    })

    it('hyperparameter importances panel keeps the last selected parameter checked', async () => {
        // full mount, so that the checkboxes inside the list items are rendered; only the chart is stubbed
        const wrapper = mount(HypImpRegionPanel, {
            props: {
                region: regionAB,
                showTitle: false,
                hypImpObjective: 'runtime'
            },
            global: {
                plugins: [vuetify, createPinia()],
                stubs: { HypImp: true }
            }
        })

        const [alphaBox, betaBox] = wrapper.findAllComponents(VCheckbox)
        expect(alphaBox.props('disabled')).toBe(false)
        expect(betaBox.props('disabled')).toBe(false)

        await alphaBox.vm.$emit('update:modelValue', [ALPHA])

        expect(wrapper.findAllComponents(VCheckbox)[0].props('disabled')).toBe(true)
        expect(wrapper.findAllComponents(VCheckbox)[1].props('disabled')).toBe(false)
    })

    it('heatmap panel selects the first two parameters of its region', () => {
        const wrapper = mountPanel(HeatmapRegionPanel, {
            region: flatCategoricalRegion,
            showTitle: false,
            heatmapObjective: 'runtime'
        })

        const heatmap = wrapper.findComponent(Heatmap)
        expect(heatmap.props('heatmapParam1')).toBe(N0)
        expect(heatmap.props('heatmapParam2')).toBe(N1)
    })

    it('heatmap panel selects the first two parameters of a new region', async () => {
        const wrapper = mountPanel(HeatmapRegionPanel, {
            region: flatCategoricalRegion,
            showTitle: false,
            heatmapObjective: 'runtime'
        })

        await wrapper.setProps({ region: { ActivationCategory: 'root', Parameters: [o1, n1] } })

        const heatmap = wrapper.findComponent(Heatmap)
        expect(heatmap.props('heatmapParam1')).toBe(O1)
        expect(heatmap.props('heatmapParam2')).toBe(N1)
    })

    it('heatmap panel never offers the parameter chosen for one axis on the other axis', () => {
        const wrapper = mountPanel(HeatmapRegionPanel, {
            region: flatCategoricalRegion,
            showTitle: false,
            heatmapObjective: 'runtime'
        })

        const [axis1, axis2] = wrapper.findAllComponents(VSelect)
        expect(axis1.props('items')).toEqual([N0, O1])
        expect(axis2.props('items')).toEqual([N1, O1])
    })

    it('heatmap panel draws the parameter selected for an axis and offers the other axis the rest', async () => {
        const wrapper = mountPanel(HeatmapRegionPanel, {
            region: flatCategoricalRegion,
            showTitle: false,
            heatmapObjective: 'runtime'
        })

        await wrapper.findAllComponents(VSelect)[0].vm.$emit('update:modelValue', O1)

        const heatmap = wrapper.findComponent(Heatmap)
        expect(heatmap.props('heatmapParam1')).toBe(O1)
        expect(heatmap.props('heatmapParam2')).toBe(N1)
        expect(wrapper.findAllComponents(VSelect)[1].props('items')).toEqual([N0, N1])
    })

    it('heatmap panel gives its region and the objective to the heatmap', () => {
        const wrapper = mountPanel(HeatmapRegionPanel, {
            region: flatCategoricalRegion,
            showTitle: false,
            heatmapObjective: 'runtime'
        })

        const heatmap = wrapper.findComponent(Heatmap)
        expect(heatmap.props('region')).toEqual(flatCategoricalRegion)
        expect(heatmap.props('heatmapObjective')).toBe('runtime')
    })

    it('heatmap panel explains instead of drawing a region with fewer than two parameters', () => {
        const wrapper = mountPanel(HeatmapRegionPanel, {
            region: { ActivationCategory: 'root', Parameters: [n0] },
            showTitle: false,
            heatmapObjective: 'runtime'
        })

        expect(wrapper.findComponent(Heatmap).exists()).toBe(false)
        expect(wrapper.text()).toContain('Not enough categorical parameters in this region for a heatmap.')
    })

    it('heatmap panel offers only the nominal and ordinal parameters with two categories or more', () => {
        // the numeric parameters and the single-category one come first and between, so the defaults skip them
        const wrapper = mountPanel(HeatmapRegionPanel, {
            region: { ActivationCategory: 'root', Parameters: [alpha, n0, beta, flag, n1, o1] },
            showTitle: false,
            heatmapObjective: 'runtime'
        })

        const [axis1, axis2] = wrapper.findAllComponents(VSelect)
        expect(axis1.props('items')).toEqual([N0, O1])
        expect(axis2.props('items')).toEqual([N1, O1])
        const heatmap = wrapper.findComponent(Heatmap)
        expect(heatmap.props('heatmapParam1')).toBe(N0)
        expect(heatmap.props('heatmapParam2')).toBe(N1)
    })

    it('heatmap panel explains instead of drawing a region with fewer than two categorical parameters', () => {
        const wrapper = mountPanel(HeatmapRegionPanel, {
            region: { ActivationCategory: 'root', Parameters: [alpha, n0, beta, flag] },
            showTitle: false,
            heatmapObjective: 'runtime'
        })

        expect(wrapper.findComponent(Heatmap).exists()).toBe(false)
        expect(wrapper.text()).toContain('Not enough categorical parameters in this region for a heatmap.')
    })

    it('heatmap panel shows the region title only when asked to', async () => {
        const wrapper = mountPanel(HeatmapRegionPanel, {
            region: flatCategoricalRegion,
            showTitle: true,
            heatmapObjective: 'runtime'
        })

        expect(wrapper.findComponent(RegionTitle).props('region')).toEqual(flatCategoricalRegion)

        await wrapper.setProps({ showTitle: false })

        expect(wrapper.findComponent(RegionTitle).exists()).toBe(false)
    })
})

describe('Region panels give their chart whether it is active', () => {
    const panels = [
        ['rank', RankRegionPanel, Rank, regionA, { rankObjective: 'runtime' }],
        ['slice', SliceRegionPanel, Slice, regionAB, { sliceObjective: 'runtime' }],
        ['contour', ContourRegionPanel, Contour, regionA, { contourObjective: 'runtime' }],
        ['heatmap', HeatmapRegionPanel, Heatmap, flatCategoricalRegion, { heatmapObjective: 'runtime' }],
        ['parallel coordinates', ParaCoordRegionPanel, ParaCoord, regionA, { paraCoordObjective: 'runtime' }],
        ['hyperparameter importances', HypImpRegionPanel, HypImp, regionA, { hypImpObjective: 'runtime' }]
    ] as const

    it.each(panels)('%s panel: active unless told otherwise, and following its own flag', async (_, panel, chart, region, objective) => {
        const wrapper = mountPanel(panel, { region, showTitle: false, ...objective })
        expect(wrapper.findComponent(chart).props('active')).toBe(true)

        await wrapper.setProps({ active: false })
        expect(wrapper.findComponent(chart).props('active')).toBe(false)

        await wrapper.setProps({ active: true })
        expect(wrapper.findComponent(chart).props('active')).toBe(true)
    })
})
