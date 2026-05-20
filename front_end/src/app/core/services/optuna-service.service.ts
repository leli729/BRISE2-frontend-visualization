import { Injectable } from '@angular/core';

declare var loadPyodide: any;

@Injectable({
  providedIn: 'root'
})
export class OptunaService {

  pyodide: any;
  constructor() { }

  async init() {

    this.pyodide = await loadPyodide({
      indexURL: "https://cdn.jsdelivr.net/pyodide/v0.25.0/full/"
    });

  }

  async runPython(code: string): Promise<any> {
    return await this.pyodide.runPythonAsync(code);
  }

  async runPythonWithParams(
    code: string,
    params: any
  ): Promise<any> {

    // Übergabe an Python
    this.pyodide.globals.set("input_data", params);

    // Python ausführen
    const result = await this.pyodide.runPythonAsync(code);

    // Rückgabe konvertieren
    /*if (result?.toJs) {
      return result.toJs();
    }*/

    return result;
  }
}
