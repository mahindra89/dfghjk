(function(){
let pyodideReady = false;
let pyodide;

async function initializePyodide() {
  pyodide = await loadPyodide();
  await pyodide.loadPackage("matplotlib");
  pyodideReady = true;
}
initializePyodide();

document.getElementById("numJobs").addEventListener("change", generateJobInputs);
document.getElementById("randomBtn").addEventListener("click", randomizeInputs);
document.getElementById("runBtn").addEventListener("click", runScheduler);

function generateJobInputs() {
  const numJobs = parseInt(document.getElementById("numJobs").value);
  const container = document.getElementById("jobInputs");
  container.innerHTML = "";
  for (let i = 0; i < numJobs; i++) {
    container.innerHTML += `
      <div>
        <label>Arrival J${i + 1}: <input type="number" id="arrival${i}" value="${i + 1}" /></label>
        <label>Burst J${i + 1}: <input type="number" step="0.5" id="burst${i}" value="2" /></label>
      </div>
    `;
  }
}

function randomizeInputs() {
  const randInt = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;
  const floatSet = [1, 1.5, 2, 2.5, 3, 3.5, 4.5, 5];
  const randFloat = () => floatSet[Math.floor(Math.random() * floatSet.length)];

  const numJobs = randInt(1, 10);
  const numCPUs = randInt(1, 5);
  const chunkUnit = randFloat();

  document.getElementById("numJobs").value = numJobs;
  document.getElementById("numCPUs").value = numCPUs;
  document.getElementById("chunkUnit").value = chunkUnit;

  generateJobInputs();
  for (let i = 0; i < numJobs; i++) {
    document.getElementById(`arrival${i}`).value = randInt(1, 10);
    document.getElementById(`burst${i}`).value = randFloat();
  }
}

async function runScheduler() {
  if (!pyodideReady) return;

  const numJobs = parseInt(document.getElementById("numJobs").value);
  const numCPUs = parseInt(document.getElementById("numCPUs").value);
  const chunkUnit = parseFloat(document.getElementById("chunkUnit").value);

  let jobData = [];
  for (let i = 0; i < numJobs; i++) {
    const arrival = parseFloat(document.getElementById(`arrival${i}`).value);
    const burst = parseFloat(document.getElementById(`burst${i}`).value);
    jobData.push([arrival, burst]);
  }

  pyodide.globals.set("num_jobs", numJobs);
  pyodide.globals.set("num_cpus", numCPUs);
  pyodide.globals.set("chunk_unit", chunkUnit);
  pyodide.globals.set("job_data", jobData);

  const response = await fetch("main.py");
  const code = await response.text();
  await pyodide.runPythonAsync(code);
  const output = await pyodide.runPythonAsync("sys.stdout.getvalue()");
  document.getElementById("pyOutput").value = output;
}
generateJobInputs();
})();