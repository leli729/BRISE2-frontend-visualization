<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { storeToRefs } from 'pinia'


// Plotly
import Plotly from 'plotly.js-dist-min'

import { MainEvent } from '../../../../entities/main'
import type { Solution } from '../../../../entities/task/model/task-data.model';

//service
import { useMainEventStore } from '../../../../entities/main'

interface Trial {
    parameters: Array<any>;
    objectives: Array<any>;
}

const isVisible = ref(false)

const trials = ref<Trial[]>([])
const store = useMainEventStore()
const { experiment_description } = storeToRefs(store)
const hypimp = ref<HTMLElement | null>(null)

onMounted(() => {
    initMainEvents()
})
/*
async function calculateImportances() {
    this.importances = await this.optunaService.runPythonWithParams(
      `
      # wie genau kann ein neuer trial erstellt werden?
      # wie kann ich diese hinzufügen?
      import optuna 

      def getImportances(trials):
          study = optuna.create_study()
          study.add_trials(trials)
          # Returns a dict where the keys are parameter names and the values are assessed importances.
          # Return type: dict[str, float]
          result = optuna.importance.get_param_importances(study)
          return result

      getImportances(input_data)
      `,
      this.trials);
  }*/

function initMainEvents() {
    watch(experiment_description, () => {
        trials.value = []
        // pointer to dom element 
        const element = hypimp.value
        isVisible.value = false
        if (element)
            Plotly.purge(element)
    }, {
        deep: true,
        immediate: true
    })

    // add start point
    store.onEvent(MainEvent.DEFAULT)?.subscribe((message: any) => {
        if (message.headers['message_subtype'] === 'configuration') {
            const configs = JSON.parse(message.body)
            configs.forEach((configuration: any) => {
                const first_trial: Trial = {
                    parameters: Object.values(configuration.configurations),
                    objectives: Object.values(configuration.results)
                };
               trials.value.push(first_trial);
            })
            //render() // render chart when all points got
        }
    })

    // add last point
    store.onEvent(MainEvent.FINAL)?.subscribe((message: any) => {
        if (message.headers['message_subtype'] === 'configuration') {
            const configs = JSON.parse(message.body);
            configs.forEach((configuration: any) => {
                const first_trial: Trial = {
                    parameters: Object.values(configuration.configurations),
                    objectives: Object.values(configuration.results)
                };
               trials.value.push(first_trial); 
            });
        }
        render(); // Render chart when all points got
    })

    // add new point
    store.onEvent(MainEvent.NEW)?.subscribe((message: any) => {
        if (message.headers['message_subtype'] === 'configuration') {
            const configs = JSON.parse(message.body);
            configs.forEach((configuration: any) => {
                const new_trial: Trial = {
                    parameters: Object.values(configuration.configurations),
                    objectives: Object.values(configuration.results)
                };
               trials.value.push(new_trial);
            })
        }

    })
}

function render() {
    // DOM element. Render point

    const element = hypimp.value

    isVisible.value = true
    console.log("Inside HypImp render(): ");
    console.log("Trials in hypimp:", JSON.stringify(trials.value, null, 2));
}
</script>

<template>
    <div v-show="isVisible" ref="hypimp"></div>
</template>