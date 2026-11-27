<script setup lang="ts">
import { ref } from 'vue'
import { usePlotStore } from '../../../../entities/main/model/plot.store'
import { renderParetoFront } from '../render'
import { storeToRefs } from 'pinia'
import { MainClientApi } from '../../../../entities/main/api/main.client.store'
import { useMainEventStore } from '../../../../entities/main'
import { useChartRender, PLOT_REQUEST_INTERVAL_MS } from '../../model/use-chart-render'

const plotStore = usePlotStore()
const store = useMainEventStore()
const { allRes } = storeToRefs(plotStore)
const { plotlyInstance } = storeToRefs(store)
const paretofront = ref<HTMLElement | null>(null)

const props = withDefaults(defineProps<{
    paretoObjective1: string
    paretoObjective2: string
    onlyShowParetoFront: boolean
    active?: boolean
}>(), { active: true })

async function render(isMounted: () => boolean) {
    const result = await MainClientApi.calculatePlot(
        "pareto_front",
        {
            "trials": allRes.value,
            "objective1": props.paretoObjective1,
            "objective2": props.paretoObjective2
        }
    )

    // the chart may have been unmounted while the request was in flight
    if (!isMounted()) return
    renderParetoFront(plotlyInstance.value!, paretofront.value!, result, props.onlyShowParetoFront)
}

useChartRender({
    element: paretofront,
    plotly: plotlyInstance,
    sources: [
        allRes,
        () => props.paretoObjective1,
        () => props.paretoObjective2,
        () => props.onlyShowParetoFront
    ],
    render,
    active: () => props.active,
    minIntervalMs: PLOT_REQUEST_INTERVAL_MS
})
</script>



<template>
  <div
    ref="paretofront"
  />
</template>