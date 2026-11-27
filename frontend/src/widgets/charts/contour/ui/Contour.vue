<script setup lang="ts">
import { ref } from 'vue'
import { usePlotStore } from '../../../../entities/main/model/plot.store'
import { renderContour } from '../render'
import { storeToRefs } from 'pinia'
import { MainClientApi } from '../../../../entities/main/api/main.client.store'
import { useMainEventStore } from '../../../../entities/main'
import { trialsWithParameters } from '../../../../entities/experiment/lib/regions'
import { useChartRender, PLOT_REQUEST_INTERVAL_MS } from '../../model/use-chart-render'

defineOptions({ name: 'ContourChart' })

const plotStore = usePlotStore()
const store = useMainEventStore()
const { allRes } = storeToRefs(plotStore)
const { specsByName, plotlyInstance } = storeToRefs(store)
const contour = ref<HTMLElement | null>(null)

const props = withDefaults(defineProps<{
    contourParam1: string
    contourParam2: string
    contourObjective: string
    active?: boolean
}>(), { active: true })

async function render(isMounted: () => boolean) {
    // Availability of Contour Plot currently not defined correctly by feature model. Therefore checking here if 2 valid HPs are available.
    // This check can be deleted once the constraint is implemented correctly in the feature model.
    if (!props.contourParam1 || !props.contourParam2 || props.contourParam1 === "" || props.contourParam2 === "") {
        return
    }
    const trials = trialsWithParameters(allRes.value, [props.contourParam1, props.contourParam2])
    const result = await MainClientApi.calculatePlot(
        "contour",
        {
            "trials": trials,
            "param1": props.contourParam1,
            "param2": props.contourParam2,
            "objective": props.contourObjective
        }
    )

    // the chart may have been unmounted while the request was in flight
    if (!isMounted()) return
    renderContour(plotlyInstance.value!, contour.value!, result, specsByName.value)
}

useChartRender({
    element: contour,
    plotly: plotlyInstance,
    sources: [
        allRes,
        () => props.contourParam1,
        () => props.contourParam2,
        () => props.contourObjective
    ],
    render,
    active: () => props.active,
    minIntervalMs: PLOT_REQUEST_INTERVAL_MS
})
</script>



<template>
  <div
    ref="contour"
  />
</template>