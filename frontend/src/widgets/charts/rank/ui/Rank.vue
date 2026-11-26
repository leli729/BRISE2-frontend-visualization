<script setup lang="ts">
import { ref } from 'vue'
import { usePlotStore } from '../../../../entities/main/model/plot.store'
import { renderRank } from '../render'
import { storeToRefs } from 'pinia'
import { useMainEventStore } from '../../../../entities/main'
import { trialsOfRegion } from '../../../../entities/experiment/lib/regions'
import type { SearchSpaceRegion } from '../../../../entities/experiment/model/experiment.model'
import { useChartRender, CLIENT_REDRAW_INTERVAL_MS } from '../../model/use-chart-render'

defineOptions({ name: 'RankChart' })

const plotStore = usePlotStore()
const store = useMainEventStore()
const { allRes } = storeToRefs(plotStore)
const { specsByName, plotlyInstance } = storeToRefs(store)
const rank = ref<HTMLElement | null>(null)

const props = defineProps<{
    region: SearchSpaceRegion
    rankParam1: string
    rankParam2: string
    rankObjective: string
}>()

function render() {
    // a trial of the region without a selected parameter is drawn as inactive in it
    const trials = trialsOfRegion(allRes.value, props.region)
    renderRank(plotlyInstance.value!, rank.value!, trials, props.rankParam1, props.rankParam2, props.rankObjective, specsByName.value)
}

useChartRender({
    element: rank,
    plotly: plotlyInstance,
    sources: [
        allRes,
        () => props.rankParam1,
        () => props.rankParam2,
        () => props.rankObjective
    ],
    render,
    active: () => true,
    minIntervalMs: CLIENT_REDRAW_INTERVAL_MS
})
</script>



<template>
  <div
    ref="rank"
  />
</template>