<script setup lang="ts">
import { ref } from 'vue'
import { usePlotStore } from '../../../../entities/main/model/plot.store'
import { renderParaCoord } from '../render'
import { storeToRefs } from 'pinia'
import { useMainEventStore } from '../../../../entities/main'
import { trialsOfRegion } from '../../../../entities/experiment/lib/regions'
import type { SearchSpaceRegion } from '../../../../entities/experiment/model/experiment.model'
import { useChartRender, CLIENT_REDRAW_INTERVAL_MS } from '../../model/use-chart-render'

const store = useMainEventStore()
const plotStore = usePlotStore()
const { specsByName, plotlyInstance } = storeToRefs(store)
const { allRes } = storeToRefs(plotStore)
const paraCoord = ref<HTMLElement | null>(null)
const props = withDefaults(defineProps<{
    region: SearchSpaceRegion
    paraCoordParams: string[]
    paraCoordObjective: string
    active?: boolean
}>(), { active: true })

function render() {
    // a trial of the region without a selected parameter is drawn as inactive in it
    const trials = trialsOfRegion(allRes.value, props.region)
    renderParaCoord(plotlyInstance.value!, paraCoord.value!, trials, props.paraCoordParams, props.paraCoordObjective, specsByName.value)
}

useChartRender({
    element: paraCoord,
    plotly: plotlyInstance,
    sources: [
        allRes,
        // the parameters are a prop array: a getter that reads its items, as the watch is not deep
        () => [...props.paraCoordParams],
        () => props.paraCoordObjective
    ],
    render,
    active: () => props.active,
    drawOnlyInView: true,
    minIntervalMs: CLIENT_REDRAW_INTERVAL_MS
})
</script>



<!-- min-height: the height of Plotly's default plot, so a chart that is not drawn (not in view yet, or released) keeps its place -->
<template>
  <div
    ref="paraCoord"
    style="min-height: 450px"
  />
</template>
