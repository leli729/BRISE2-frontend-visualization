<script setup lang="ts">
import { ref } from 'vue'
import { usePlotStore } from '../../../../entities/main/model/plot.store'
import { renderOptHist } from '../render'
import { storeToRefs } from 'pinia'
import { useMainEventStore } from '../../../../entities/main'
import { useChartRender, CLIENT_REDRAW_INTERVAL_MS } from '../../model/use-chart-render'

const store = useMainEventStore()
const plotStore = usePlotStore()
const { experiment_description, plotlyInstance } = storeToRefs(store)
const { allRes, solution } = storeToRefs(plotStore)
const optHist = ref<HTMLElement | null>(null)
const props = withDefaults(defineProps<{
    optHistObjective: string
    active?: boolean
}>(), { active: true })

function render() {
    if (!experiment_description.value) 
        return
    renderOptHist(plotlyInstance.value!, optHist.value!, allRes.value, experiment_description.value, props.optHistObjective, solution.value)
}

useChartRender({
    element: optHist,
    plotly: plotlyInstance,
    sources: [
        allRes,
        solution,
        () => props.optHistObjective
    ],
    render,
    active: () => props.active,
    minIntervalMs: CLIENT_REDRAW_INTERVAL_MS
})
</script>



<template>
  <div
    ref="optHist"
  />
</template>