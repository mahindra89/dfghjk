import js
from pyodide.ffi import create_proxy
from js import document
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.colors as mcolors
import io
import base64
from matplotlib.figure import Figure

# Global variables to store simulation data
processes = []
gantt_data = []
queue_snapshots = []

def setup_simulation(*args):
    num_jobs = int(document.getElementById("num_jobs").value)
    
    # Show the jobs section
    document.getElementById("jobs-section").style.display = "block"
    
    # Generate job input fields
    jobs_container = document.getElementById("jobs-container")
    jobs_container.innerHTML = ""
    
    for i in range(num_jobs):
        job_div = document.createElement("div")
        job_div.className = "job-row"
        job_div.innerHTML = f"""
            <h5>Job J{i+1}</h5>
            <div class="row">
                <div class="col-md-6">
                    <label for="arrival_time_{i}" class="form-label">Arrival Time:</label>
                    <input type="number" id="arrival_time_{i}" class="form-control" value="{i}" min="0" step="0.5">
                </div>
                <div class="col-md-6">
                    <label for="burst_time_{i}" class="form-label">Burst Time:</label>
                    <input type="number" id="burst_time_{i}" class="form-control" value="{i+2}" min="0.1" step="0.5">
                </div>
            </div>
        """
        jobs_container.appendChild(job_div)

def run_simulation(*args):
    global processes, gantt_data, queue_snapshots
    
    # Clear previous results
    processes = []
    gantt_data = []
    queue_snapshots = []
    
    # Get simulation parameters
    num_jobs = int(document.getElementById("num_jobs").value)
    num_cpus = int(document.getElementById("num_cpus").value)
    chunk_unit = float(document.getElementById("chunk_unit").value)
    quantum_time = float(document.getElementById("quantum_time").value)
    
    # Collect job information
    for i in range(num_jobs):
        arrival = float(document.getElementById(f"arrival_time_{i}").value)
        burst = float(document.getElementById(f"burst_time_{i}").value)
        processes.append({'id': f'J{i+1}', 'arrival_time': arrival, 'burst_time': burst})
    
    # Run the simulation
    simulate_scheduler(num_cpus, chunk_unit, quantum_time)
    
    # Display results
    display_results()

def simulate_scheduler(num_cpus, chunk_unit, quantum_time):
    global processes, gantt_data, queue_snapshots
    
    # Setup state
    arrival_time = {p['id']: p['arrival_time'] for p in processes}
    burst_time = {p['id']: p['burst_time'] for p in processes}
    remaining_time = {p['id']: p['burst_time'] for p in processes}
    start_time = {}
    end_time = {}
    job_chunks = {}

    # Break jobs into user-defined chunks
    for job_id, total_time in burst_time.items():
        chunks = []
        remaining = total_time
        while remaining > 0:
            chunk = min(chunk_unit, remaining)
            chunks.append(chunk)
            remaining -= chunk
        job_chunks[job_id] = chunks

    # CPU setup
    cpu_names = [f"CPU{i+1}" for i in range(num_cpus)]
    busy_until = {cpu: 0 for cpu in cpu_names}
    current_jobs = {cpu: None for cpu in cpu_names}
    busy_jobs = set()

    # Simulation state
    current_time = 0
    jobs_completed = 0
    next_scheduling_time = 0  # Track when the next scheduling decision can be made

    # Capture queue state at each scheduling point
    def capture_queue_state(time, available_jobs):
        active_jobs = [j for j in available_jobs if remaining_time[j] > 0]
        queue = sorted(active_jobs, key=lambda job_id: (remaining_time[job_id], arrival_time[job_id]))
        job_info = [(job, round(remaining_time[job], 1)) for job in queue]
        if job_info:
            queue_snapshots.append((time, job_info))

    # Initial queue
    initial_available_jobs = [p['id'] for p in processes if p['arrival_time'] <= current_time]
    capture_queue_state(current_time, initial_available_jobs)

    # Simulation loop
    while jobs_completed < len(processes):
        # Check if CPUs have completed jobs
        for cpu, busy_time in list(busy_until.items()):
            if busy_time <= current_time and current_jobs[cpu] is not None:
                job_id = current_jobs[cpu]
                if job_id in busy_jobs:
                    busy_jobs.remove(job_id)
                current_jobs[cpu] = None

        # Determine if we can schedule jobs now
        can_schedule = current_time >= next_scheduling_time
        
        available_cpus = [cpu for cpu in cpu_names if busy_until[cpu] <= current_time and current_jobs[cpu] is None]
        available_jobs = [job_id for job_id in remaining_time
                        if remaining_time[job_id] > 0 and arrival_time[job_id] <= current_time and job_id not in busy_jobs]

        # Only schedule if we're at a quantum time boundary and there are available CPUs and jobs
        if can_schedule and available_cpus and available_jobs:
            capture_queue_state(current_time, available_jobs)
            
            # Sort available jobs by remaining time (STRF policy)
            available_jobs.sort(key=lambda job_id: (remaining_time[job_id], arrival_time[job_id]))
            
            # Assign jobs to available CPUs
            for cpu in available_cpus:
                if not available_jobs:
                    break

                selected_job = available_jobs.pop(0)
                if selected_job not in start_time:
                    start_time[selected_job] = current_time

                chunk_size = job_chunks[selected_job].pop(0)
                busy_jobs.add(selected_job)
                current_jobs[cpu] = selected_job

                remaining_time[selected_job] -= chunk_size
                busy_until[cpu] = current_time + chunk_size
                gantt_data.append((current_time, cpu, selected_job, chunk_size))

                if abs(remaining_time[selected_job]) < 0.001:
                    end_time[selected_job] = current_time + chunk_size
                    jobs_completed += 1
            
            # Set the next scheduling time
            next_scheduling_time = current_time + quantum_time

        # Determine the next event time
        next_time_events = []
        
        # Include job completions
        next_time_events.extend([busy_until[cpu] for cpu in busy_until if busy_until[cpu] > current_time])
        
        # Include job arrivals
        next_time_events.extend([arrival_time[j] for j in arrival_time if arrival_time[j] > current_time and remaining_time[j] > 0])
        
        # Include next scheduling time
        if next_scheduling_time > current_time:
            next_time_events.append(next_scheduling_time)
        
        # Move time to the next event
        if next_time_events:
            current_time = min(next_time_events)
        else:
            # No more events to process, simulation is complete
            break

    # Calculate results
    for p in processes:
        p['start_time'] = start_time[p['id']]
        p['end_time'] = end_time[p['id']]
        p['turnaround_time'] = p['end_time'] - p['arrival_time']

def display_results():
    global processes, gantt_data, queue_snapshots
    
    # Create results table
    results_div = document.getElementById("results-text")
    
    # Calculate average turnaround time
    avg_turnaround = sum(p['turnaround_time'] for p in processes) / len(processes)
    
    # Create HTML table
    table_html = f"""
    <table class="result-table">
        <tr>
            <th>Job</th>
            <th>Arrival</th>
            <th>Burst</th>
            <th>Start</th>
            <th>End</th>
            <th>Turnaround</th>
        </tr>
    """
    
    for p in processes:
        table_html += f"""
        <tr>
            <td>{p['id']}</td>
            <td>{p['arrival_time']}</td>
            <td>{p['burst_time']}</td>
            <td>{p['start_time']:.1f}</td>
            <td>{p['end_time']:.1f}</td>
            <td>{p['turnaround_time']:.1f}</td>
        </tr>
        """
    
    table_html += f"""
    </table>
    <p><strong>Average Turnaround Time:</strong> {avg_turnaround:.2f}</p>
    """
    
    results_div.innerHTML = table_html
    
    # Create and display Gantt chart
    create_gantt_chart()

def create_gantt_chart():
    global processes, gantt_data, queue_snapshots
    
    # Get simulation parameters
    num_cpus = int(document.getElementById("num_cpus").value)
    quantum_time = float(document.getElementById("quantum_time").value)
    
    # Create figure and axes
    fig = Figure(figsize=(10, 5))
    ax = fig.add_subplot(111)
    
    # Calculate end times for chart scaling
    end_times = [p['end_time'] for p in processes]
    max_time = max(end_times) if end_times else 0
    
    # Generate colors for jobs
    cmap = plt.cm.get_cmap('tab20')
    colors = {f'J{i+1}': mcolors.to_hex(cmap(i / max(len(processes), 1))) for i in range(len(processes))}
    
    # Setup CPU positions
    cpu_ypos = {f"CPU{i+1}": num_cpus - i for i in range(num_cpus)}
    
    # Draw job blocks on the chart
    for start_time, cpu, job, duration in gantt_data:
        y_pos = cpu_ypos[cpu]
        ax.barh(y=y_pos, width=duration, left=start_time,
                color=colors[job], edgecolor='black')
        ax.text(start_time + duration / 2, y_pos, job,
                ha='center', va='center', color='white', fontsize=9)
    
    # Add quantum time markers
    for t in range(0, int(max_time) + 1, int(quantum_time)):
        ax.axvline(x=t, color='red', linestyle='-', alpha=0.5, linewidth=0.5)
    
    # Add regular time markers
    for t in range(int(max_time) + 1):
        if t % int(quantum_time) != 0:  # Skip where we already have quantum markers
            ax.axvline(x=t, color='black', linestyle='--', alpha=0.3)
    
    # Setup axis labels and titles
    ax.set_yticks(list(cpu_ypos.values()))
    ax.set_yticklabels(cpu_ypos.keys())
    ax.set_xlim(0, max_time + 0.5)
    ax.set_xlabel("Time (seconds)")
    ax.set_title(f"Multi-CPU STRF with Quantum Time: {quantum_time}s")
    
    # Add legend for quantum time
    ax.plot([], [], color='red', linestyle='-', alpha=0.5, label=f'Quantum Time ({quantum_time}s)')
    ax.legend(loc='upper right')
    
    # Draw grid lines
    ax.grid(axis='x')
    
    # Save figure to an image
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format='png')
    buf.seek(0)
    
    # Convert to base64 for embedding in HTML
    img_str = base64.b64encode(buf.read()).decode('utf-8')
    
    # Display the image
    gantt_div = document.getElementById("gantt-chart")
    gantt_div.innerHTML = f'<img src="data:image/png;base64,{img_str}" style="width: 100%;" />'

# Register the event handlers (required for PyScript)