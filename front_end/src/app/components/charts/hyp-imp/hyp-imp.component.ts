import { Component, OnInit, ViewChild, ElementRef } from '@angular/core';

// Service
import {MainEventService} from '../../../core/services/main.event.service';

//import { Solution } from '../../../data/taskData.model';
import { MainEvent } from '../../../data/client-enums';

//import { ExperimentDescription } from '../../../data/experimentDescription.model';

@Component({
  selector: 'hyp-imp',
  templateUrl: './hyp-imp.component.html',
  styleUrls: ['./hyp-imp.component.scss']
})
export class HypImpComponent implements OnInit {

  //@ViewChild('importance') importance: ElementRef;

  constructor(private ioMain: MainEventService) {
  }

  ngOnInit() {
    //this.initMainEvents();
  }
  /*
  private initMainEvents(): void {
      this.ioMain.onEvent(MainEvent.EXPERIMENT)
        .subscribe((message: any) => {
          if (message.headers['message_subtype'] === 'description') {
            null;
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
  }*/
}
