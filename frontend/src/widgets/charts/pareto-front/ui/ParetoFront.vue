<script setup lang="ts">
import { ref, watch } from 'vue'
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

// the last reply of main-node: the switch redraws from it, as it only chooses which of its points are shown
let lastReply: any = null

async function render(canDraw: () => boolean) {
    const result = await MainClientApi.calculatePlot(
        "pareto_front",
        {
            "trials": allRes.value,
            "objective1": props.paretoObjective1,
            "objective2": props.paretoObjective2
        }
    )

    // the chart may have been unmounted, or stopped being shown, while the request was in flight
    if (!canDraw()) return
    lastReply = result
    renderParetoFront(plotlyInstance.value!, paretofront.value!, result, props.onlyShowParetoFront)
}

useChartRender({
    element: paretofront,
    plotly: plotlyInstance,
    sources: [
        allRes,
        () => props.paretoObjective1,
        () => props.paretoObjective2
    ],
    render,
    active: () => props.active,
    minIntervalMs: PLOT_REQUEST_INTERVAL_MS
})

// the switch is no source of the render, which would send a request: it redraws at once from the last reply, when
// there is one and the chart is shown
watch(() => props.onlyShowParetoFront, () => {
    if (!props.active || !lastReply || !plotlyInstance.value || !paretofront.value) return
    renderParetoFront(plotlyInstance.value, paretofront.value, lastReply, props.onlyShowParetoFront)
})
</script>



<template>
  <div
    ref="paretofront"
  />
</template>