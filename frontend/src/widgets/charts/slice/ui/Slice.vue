<script setup lang="ts">
import { ref } from 'vue'
import { usePlotStore } from '../../../../entities/main/model/plot.store'
import { renderSlice } from '../render'
import { storeToRefs } from 'pinia'
import { useMainEventStore } from '../../../../entities/main'
import { trialsOfRegion } from '../../../../entities/experiment/lib/regions'
import type { SearchSpaceRegion } from '../../../../entities/experiment/model/experiment.model'
import { useChartRender, CLIENT_REDRAW_INTERVAL_MS } from '../../model/use-chart-render'

defineOptions({ name: 'SliceChart' })

const plotStore = usePlotStore()
const store = useMainEventStore()
const { allRes } = storeToRefs(plotStore)
const { specsByName, plotlyInstance } = storeToRefs(store)
const slice = ref<HTMLElement | null>(null)

const props = defineProps<{
    region: SearchSpaceRegion
    sliceParam: string
    sliceObjective: string
}>()

function render() {
    // a trial of the region without the selected parameter is drawn as inactive in it
    const trials = trialsOfRegion(allRes.value, props.region)
    renderSlice(plotlyInstance.value!, slice.value!, trials, props.sliceParam, props.sliceObjective, specsByName.value)
}

useChartRender({
    element: slice,
    plotly: plotlyInstance,
    sources: [
        allRes,
        () => props.sliceParam,
        () => props.sliceObjective
    ],
    render,
    active: () => true,
    minIntervalMs: CLIENT_REDRAW_INTERVAL_MS
})
</script>



<template>
  <div
    ref="slice"
  />
</template>