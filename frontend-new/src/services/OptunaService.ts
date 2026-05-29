declare global {
  interface Window {
    loadPyodide: any;
  }
}

export class OptunaService {
  pyodide: any;

  constructor() {
    this.pyodide = null;
  }

  // ---------------------------------------------------
  // INIT PYODIDE
  // ---------------------------------------------------
  async init() {
    if (this.pyodide) return

    console.log("🔥 loading Pyodide...")

    this.pyodide = await window.loadPyodide({
    indexURL: "https://cdn.jsdelivr.net/pyodide/v0.25.0/full/"
    })

    console.log("✅ Pyodide loaded")

    await this.pyodide.loadPackage("micropip")

    const micropip = this.pyodide.pyimport("micropip")

    console.log("🔥 installing full ML stack...")

    await micropip.install("scikit-learn")
    await micropip.install("optuna")

    console.log("✅ ML stack ready")
  }

  // ---------------------------------------------------
  // RUN RAW PYTHON
  // ---------------------------------------------------
  async runPython(code: string): Promise<any> {
    if (!this.pyodide) {
      throw new Error("Pyodide not initialized. Call init() first.");
    }

    return await this.pyodide.runPythonAsync(code);
  }

  // ---------------------------------------------------
  // RUN PYTHON WITH PARAMETERS
  // ---------------------------------------------------
  async runPythonWithParams(code: string, params: any): Promise<any> {
    if (!this.pyodide) {
      throw new Error("Pyodide not initialized. Call init() first.");
    }

    // Pass JS object into Python
    //this.pyodide.globals.set("input_data", params);
    this.pyodide.globals.set("input_data", JSON.stringify(params))

    const result = await this.pyodide.runPythonAsync(code);

    // Convert PyProxy → JS
    if (result && typeof result.toJs === "function") {
      return result.toJs();
    }

    return result;
  }
}

