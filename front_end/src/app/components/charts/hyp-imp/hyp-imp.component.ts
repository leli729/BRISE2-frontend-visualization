import { Component, OnInit, ViewChild, ElementRef } from '@angular/core';

// Service
import {MainEventService} from '../../../core/services/main.event.service';

//import { Solution } from '../../../data/taskData.model';
import { MainEvent } from '../../../data/client-enums';

//import { ExperimentDescription } from '../../../data/experimentDescription.model';

import { OptunaService } from '../../../core/services/optuna-service.service';

@Component({
  selector: 'hyp-imp',
  templateUrl: './hyp-imp.component.html',
  styleUrls: ['./hyp-imp.component.scss']
})
export class HypImpComponent implements OnInit {

  importances: any;
  trials: any;

  @ViewChild('importance') importance: ElementRef;

  constructor(private ioMain: MainEventService, private optunaService: OptunaService) {
  }

  async ngOnInit() {
    this.initMainEvents();
    await this.optunaService.init();
  }

  async calculateImportances() {
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
  }
  
  private initMainEvents(): void {
      this.ioMain.onEvent(MainEvent.EXPERIMENT)
        .subscribe((message: any) => {
          if (message.headers['message_subtype'] === 'description') {
            this.trials.clear();
            this.importances.clear();
          }
        });
  
      this.ioMain.onEvent(MainEvent.FINAL)
        .subscribe((message: any) => {
          if (message.headers['message_subtype'] === 'configuration') {
            const configs = JSON.parse(message.body);
            configs.forEach(configuration => {
              null;
            });
          }
          this.render(); // Render chart when all points got
        });
  
      this.ioMain.onEvent(MainEvent.DEFAULT).subscribe((message: any) => {
        if (message.headers['message_subtype'] === 'configuration') {
          const configs = JSON.parse(message.body);
          configs.forEach(configuration => {
            null;
          });
          this.render(); // Render chart when all points got
        }
      });
  
      this.ioMain.onEvent(MainEvent.NEW)
        .subscribe((message: any) => {
          if (message.headers['message_subtype'] === 'configuration') {
            const configs = JSON.parse(message.body);
            configs.forEach(configuration => {
              null;
            });
          }
        });
    }

  render() {
    // DOM element. Render point
    const element = this.importance.nativeElement;
    element.style.display = 'block';
    
    var data = [
      {
        x: ['giraffes', 'orangutans', 'monkeys'],
        y: [20, 14, 23],
        type: 'bar'
      } 
    ];

    Plotly.react(element, data);
  }
}
